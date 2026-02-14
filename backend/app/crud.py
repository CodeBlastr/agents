from datetime import datetime, timezone

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.models import Bot, BotConfig, BotRun, Notification, TaxSnapshot

DEFAULT_TAX_CONFIG = {
    "parcel_id": "DEMO",
    "portal_url": "https://example.com",
    "portal_profile": {
        "parcel_selector": None,
        "search_button_selector": None,
        "results_container_selector": None,
        "balance_regex": r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)",
        "pre_steps": [],
        "checkpoint_selector": None,
        "checkpoint_min_count": None,
        "stop_after_checkpoint": False,
    },
}


def seed_tax_bot(db: Session) -> Bot:
    bot = db.query(Bot).filter(Bot.slug == "tax").first()
    if not bot:
        bot = Bot(slug="tax", name="Tax Bot v0")
        db.add(bot)
        db.commit()
        db.refresh(bot)

    ensure_tax_config(db, bot)
    return bot


def ensure_tax_config(db: Session, bot: Bot) -> BotConfig:
    config = db.query(BotConfig).filter(BotConfig.bot_id == bot.id, BotConfig.key == "tax.default").first()
    if config:
        return config

    config = BotConfig(bot_id=bot.id, key="tax.default", config_json=DEFAULT_TAX_CONFIG)
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def get_tax_config(db: Session, bot: Bot) -> dict:
    config = ensure_tax_config(db, bot)
    return config.config_json


def upsert_tax_config(db: Session, bot: Bot, config_json: dict) -> dict:
    config = ensure_tax_config(db, bot)
    config.config_json = config_json
    config.updated_at = datetime.now(timezone.utc)
    db.add(config)
    db.commit()
    db.refresh(config)
    return config.config_json


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


def list_notifications(db: Session, bot_slug: str, limit: int) -> list[Notification]:
    return (
        db.query(Notification)
        .join(Bot, Notification.bot_id == Bot.id)
        .filter(Bot.slug == bot_slug)
        .order_by(desc(Notification.created_at))
        .limit(limit)
        .all()
    )


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
