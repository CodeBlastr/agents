from contextlib import asynccontextmanager
import os

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import crud, schemas
from app.bots.tax.runner import run_tax_bot
from app.db import get_db
from app.models import Bot


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
