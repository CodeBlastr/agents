from contextlib import asynccontextmanager
import json
import os
import queue
import threading
import time
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import crud, schemas
from app.bots.tax.runner import run_tax_bot
from app.db import get_db
from app.models import Bot


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
        for event in history:
            q.put(event)
        return q

    def unsubscribe(self, run_id: int, q: queue.Queue):
        with self._lock:
            subscribers = self._subscribers.get(run_id, [])
            if q in subscribers:
                subscribers.remove(q)
            if not subscribers:
                self._subscribers.pop(run_id, None)


run_event_hub = RunEventHub()


@asynccontextmanager
async def lifespan(_: FastAPI):
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        os.makedirs("/artifacts", exist_ok=True)
        crud.seed_tax_bot(db)
    finally:
        db.close()
    yield


app = FastAPI(title="Agents Dashboard API", lifespan=lifespan)
os.makedirs("/artifacts", exist_ok=True)
app.mount("/api/artifacts", StaticFiles(directory="/artifacts"), name="artifacts")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_tax_bot_or_404(db: Session) -> Bot:
    bot = db.query(Bot).filter(Bot.slug == "tax").first()
    if not bot:
        raise HTTPException(status_code=404, detail="Tax bot not found")
    return bot


def _run_tax_in_background(run_id: int):
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        bot = get_tax_bot_or_404(db)
        config = crud.get_tax_config(db, bot)

        def callback(event: dict):
            run_event_hub.publish(run_id, event)

        run_tax_bot(db, bot, config, run_id=run_id, event_callback=callback)
    except Exception as exc:
        run_event_hub.publish(run_id, {"type": "run_finished", "status": "error", "error": str(exc)})
    finally:
        db.close()


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/api/bots", response_model=list[schemas.BotSummary])
def list_bots(db: Session = Depends(get_db)):
    return crud.list_bot_summaries(db)


@app.get("/api/bots/tax/config", response_model=schemas.TaxConfig)
def get_tax_config(db: Session = Depends(get_db)):
    bot = get_tax_bot_or_404(db)
    return crud.get_tax_config(db, bot)


@app.put("/api/bots/tax/config", response_model=schemas.TaxConfig)
def put_tax_config(payload: schemas.TaxConfig, db: Session = Depends(get_db)):
    bot = get_tax_bot_or_404(db)
    return crud.upsert_tax_config(db, bot, payload.model_dump(mode="json"))


@app.post("/api/bots/tax/run", response_model=schemas.TaxRunResult)
def run_tax(db: Session = Depends(get_db)):
    bot = get_tax_bot_or_404(db)
    config = crud.get_tax_config(db, bot)
    result = run_tax_bot(db, bot, config)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@app.post("/api/bots/tax/run/start")
def start_tax_run(db: Session = Depends(get_db)):
    bot = get_tax_bot_or_404(db)
    run = crud.create_run(db, bot.id)
    thread = threading.Thread(target=_run_tax_in_background, args=(run.id,), daemon=True)
    thread.start()
    return {"run_id": run.id, "status": "running"}


@app.get("/api/bots/tax/runs/{run_id}/events")
def stream_tax_run_events(run_id: int):
    subscriber = run_event_hub.subscribe(run_id)

    def event_generator():
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

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/bots/tax/runs/{run_id}", response_model=schemas.TaxRunDetails)
def get_tax_run_details(run_id: int, db: Session = Depends(get_db)):
    bot = get_tax_bot_or_404(db)
    details = crud.get_tax_run_details(db, bot.id, run_id)
    if not details:
        raise HTTPException(status_code=404, detail="Run not found")
    return details


@app.get("/api/notifications", response_model=list[schemas.NotificationItem])
def get_notifications(
    bot: str = Query("tax"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return crud.list_notifications(db, bot_slug=bot, limit=limit)
