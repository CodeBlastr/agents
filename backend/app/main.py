from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
        crud.seed_tax_bot(db)
    finally:
        db.close()
    yield


app = FastAPI(title="Agents Dashboard API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/api/bots", response_model=list[schemas.BotSummary])
def list_bots(db: Session = Depends(get_db)):
    return crud.list_bot_summaries(db)


@app.post("/api/bots/tax/run", response_model=schemas.TaxRunResult)
def run_tax(db: Session = Depends(get_db)):
    bot = db.query(Bot).filter(Bot.slug == "tax").first()
    if not bot:
        raise HTTPException(status_code=404, detail="Tax bot not found")
    result = run_tax_bot(db, bot)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result
