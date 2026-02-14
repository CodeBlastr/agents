from __future__ import annotations

import json
import os
import queue
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import crud, schemas
from app.bots.tax.runner import run_tax_refresh
from app.db import SessionLocal, get_db
from app.models import Bot, BotRun
from app.settings import get_settings


class RunEventHub:
    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers: dict[int, list[queue.Queue]] = {}
        self._history: dict[int, list[dict]] = {}

    def publish(self, run_id: int, event: dict):
        payload = {
            **event,
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._history.setdefault(run_id, []).append(payload)
            subscribers = list(self._subscribers.get(run_id, []))
        for subscriber in subscribers:
            subscriber.put(payload)

    def subscribe(self, run_id: int) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._subscribers.setdefault(run_id, []).append(q)
            history = list(self._history.get(run_id, []))
        for item in history:
            q.put(item)
        return q

    def unsubscribe(self, run_id: int, q: queue.Queue):
        with self._lock:
            subscribers = self._subscribers.get(run_id, [])
            if q in subscribers:
                subscribers.remove(q)
            if not subscribers:
                self._subscribers.pop(run_id, None)


run_event_hub = RunEventHub()
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    os.makedirs(settings.artifacts_dir, exist_ok=True)

    db = SessionLocal()
    try:
        crud.seed_tax_bot(db)
    finally:
        db.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Agent Admin Dashboard API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/api/artifacts", StaticFiles(directory=settings.artifacts_dir), name="artifacts")

    @app.get("/api/health", response_model=schemas.HealthResponse)
    def health(db: Session = Depends(get_db)):
        db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "llm_provider": settings.llm_provider,
            "llm_model": settings.llm_model,
        }

    @app.get("/api/bots", response_model=list[schemas.BotSummary])
    def list_bots(db: Session = Depends(get_db)):
        return crud.list_bot_summaries(db)

    @app.get("/api/bots/{slug}", response_model=schemas.BotDetail)
    def get_bot(slug: str, db: Session = Depends(get_db)):
        bot = crud.get_bot_by_slug(db, slug)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        return {
            "slug": bot.slug,
            "name": bot.name,
            "source_urls": list(settings.tax_source_urls) if slug == "tax" else [],
            "config": crud.get_bot_config(db, bot.id),
            "recent_runs": crud.list_recent_runs_for_bot(db, bot.id, limit=20),
        }

    @app.get(
        "/api/bots/{slug}/properties/latest",
        response_model=list[schemas.PropertySnapshotItem],
    )
    def get_latest_properties(slug: str, db: Session = Depends(get_db)):
        bot = crud.get_bot_by_slug(db, slug)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        return crud.list_latest_properties_for_bot(db, bot.id)

    @app.get(
        "/api/bots/{slug}/properties/{property_address}/history",
        response_model=list[schemas.PropertySnapshotItem],
    )
    def get_property_history(
        slug: str,
        property_address: str,
        limit: int = Query(20, ge=1, le=200),
        db: Session = Depends(get_db),
    ):
        bot = crud.get_bot_by_slug(db, slug)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        return crud.list_property_history(db, bot.id, property_address, limit)

    @app.post("/api/bots/{slug}/refresh", response_model=schemas.RefreshResponse)
    def refresh_bot(slug: str, db: Session = Depends(get_db)):
        bot = crud.get_bot_by_slug(db, slug)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        run = crud.create_run(db, bot.id)
        thread = threading.Thread(
            target=_run_refresh_in_background,
            args=(slug, run.id),
            daemon=True,
        )
        thread.start()
        return {"run_id": run.id, "status": "running"}

    @app.get("/api/bots/{slug}/runs/{run_id}", response_model=schemas.RunDetails)
    def get_run_details(slug: str, run_id: int, db: Session = Depends(get_db)):
        bot = crud.get_bot_by_slug(db, slug)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        details = crud.get_run_details(db, bot.slug, bot.id, run_id)
        if not details:
            raise HTTPException(status_code=404, detail="Run not found")
        return details

    @app.get("/api/bots/{slug}/runs/{run_id}/events")
    def stream_run_events(slug: str, run_id: int):
        subscriber = run_event_hub.subscribe(run_id)

        def stream():
            try:
                while True:
                    try:
                        payload = subscriber.get(timeout=15)
                        yield f"data: {json.dumps(payload)}\n\n"
                        if payload.get("type") == "run_finished":
                            return
                    except queue.Empty:
                        yield f": keepalive {int(time.time())}\n\n"
            finally:
                run_event_hub.unsubscribe(run_id, subscriber)

        return StreamingResponse(stream(), media_type="text/event-stream")

    return app


def _run_refresh_in_background(slug: str, run_id: int):
    db = SessionLocal()
    try:
        bot = crud.get_bot_by_slug(db, slug)
        if not bot:
            run_event_hub.publish(run_id, {"type": "run_finished", "status": "failed", "error_summary": "Bot not found"})
            return

        run = crud.get_run_by_id(db, bot.id, run_id)
        if not run:
            run_event_hub.publish(run_id, {"type": "run_finished", "status": "failed", "error_summary": "Run not found"})
            return

        def event_callback(event: dict):
            run_event_hub.publish(run_id, event)

        run_tax_refresh(db, bot, run, event_callback=event_callback)
    except Exception as exc:
        run_event_hub.publish(
            run_id,
            {
                "type": "run_finished",
                "status": "failed",
                "error_summary": str(exc),
            },
        )
    finally:
        db.close()


app = create_app()
