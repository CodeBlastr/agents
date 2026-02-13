from datetime import datetime, timezone
from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.models import Bot, BotRun, Notification, TaxSnapshot


def seed_tax_bot(db: Session) -> Bot:
    bot = db.query(Bot).filter(Bot.slug == "tax").first()
    if bot:
        return bot
    bot = Bot(slug="tax", name="Tax Bot v0")
    db.add(bot)
    db.commit()
    db.refresh(bot)
    return bot


def list_bot_summaries(db: Session) -> list[dict]:
    bots = db.query(Bot).all()
    summaries = []
    for bot in bots:
        last_run = db.query(BotRun).filter(BotRun.bot_id == bot.id).order_by(desc(BotRun.started_at)).first()
        latest = db.query(TaxSnapshot).filter(TaxSnapshot.bot_id == bot.id).order_by(desc(TaxSnapshot.created_at)).first()
        previous = None
        changed = False
        if latest:
            previous = (
                db.query(TaxSnapshot)
                .filter(
                    and_(
                        TaxSnapshot.bot_id == bot.id,
                        TaxSnapshot.parcel_id == latest.parcel_id,
                        TaxSnapshot.portal_url == latest.portal_url,
                        TaxSnapshot.id != latest.id,
                    )
                )
                .order_by(desc(TaxSnapshot.created_at))
                .first()
            )
            if previous:
                changed = any(
                    [
                        latest.balance_due != previous.balance_due,
                        latest.paid_status != previous.paid_status,
                        latest.due_date != previous.due_date,
                    ]
                )

        summaries.append(
            {
                "slug": bot.slug,
                "name": bot.name,
                "last_run": last_run.started_at if last_run else None,
                "last_status": last_run.status if last_run else None,
                "current_balance_due": latest.balance_due if latest else None,
                "previous_balance_due": previous.balance_due if previous else None,
                "changed": changed,
            }
        )
    return summaries


def create_run(db: Session, bot_id: int) -> BotRun:
    run = BotRun(bot_id=bot_id, started_at=datetime.now(timezone.utc), status="running")
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def finalize_run(db: Session, run: BotRun, status: str, error: str | None = None) -> BotRun:
    run.status = status
    run.error = error
    run.finished_at = datetime.now(timezone.utc)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def latest_previous_snapshot(db: Session, bot_id: int, parcel_id: str, portal_url: str) -> TaxSnapshot | None:
    return (
        db.query(TaxSnapshot)
        .filter(
            and_(
                TaxSnapshot.bot_id == bot_id,
                TaxSnapshot.parcel_id == parcel_id,
                TaxSnapshot.portal_url == portal_url,
            )
        )
        .order_by(desc(TaxSnapshot.created_at))
        .first()
    )


def create_snapshot(db: Session, bot_id: int, data: dict) -> TaxSnapshot:
    snapshot = TaxSnapshot(bot_id=bot_id, **data)
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def create_notification(db: Session, bot_id: int, message: str, channel: str = "in_app") -> Notification:
    notification = Notification(bot_id=bot_id, channel=channel, message=message)
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification
