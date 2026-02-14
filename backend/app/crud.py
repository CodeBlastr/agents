from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.models import Bot, BotConfig, BotRun, Notification, TaxPropertyDetail, TaxSnapshot

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
        "scraper_mode": "real",
        "results_row_selector": "table tr:has(td)",
        "row_first_link_selector": "td a",
        "detail_table_selector": "table",
        "max_properties": 0,
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
            latest_raw = latest.raw_json or {}
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
                "mode": latest_raw.get("mode") if latest else None,
                "run_type": latest_raw.get("run_type") if latest else None,
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




def create_tax_property_details(db: Session, bot_id: int, run_id: int, properties: list[dict]) -> list[TaxPropertyDetail]:
    records: list[TaxPropertyDetail] = []
    for item in properties:
        address = item.get("property_address") or "Unknown"
        total_due = Decimal(str(item.get("total_due") or "0.00"))
        record = TaxPropertyDetail(
            run_id=run_id,
            bot_id=bot_id,
            property_number=item.get("property_number"),
            tax_map=item.get("tax_map"),
            property_address=address,
            total_due=total_due,
            detail_json=item,
        )
        db.add(record)
        records.append(record)
    db.commit()
    for record in records:
        db.refresh(record)
    return records
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


def get_tax_run_details(db: Session, bot_id: int, run_id: int) -> dict | None:
    run = db.query(BotRun).filter(BotRun.id == run_id, BotRun.bot_id == bot_id).first()
    if not run:
        return None

    snapshot_query = db.query(TaxSnapshot).filter(TaxSnapshot.bot_id == bot_id)
    if run.finished_at is not None:
        snapshot_query = snapshot_query.filter(
            TaxSnapshot.created_at >= run.started_at,
            TaxSnapshot.created_at <= run.finished_at,
        )
    snapshot = snapshot_query.order_by(desc(TaxSnapshot.created_at)).first()
    previous = None
    if snapshot:
        previous = (
            db.query(TaxSnapshot)
            .filter(
                and_(
                    TaxSnapshot.bot_id == bot_id,
                    TaxSnapshot.parcel_id == snapshot.parcel_id,
                    TaxSnapshot.portal_url == snapshot.portal_url,
                    TaxSnapshot.id != snapshot.id,
                )
            )
            .order_by(desc(TaxSnapshot.created_at))
            .first()
        )

    raw = (snapshot.raw_json if snapshot else {}) or {}
    property_rows = (
        db.query(TaxPropertyDetail)
        .filter(TaxPropertyDetail.run_id == run.id, TaxPropertyDetail.bot_id == bot_id)
        .order_by(TaxPropertyDetail.id.asc())
        .all()
    )

    return {
        "run_id": run.id,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "error": run.error,
        "snapshot_id": snapshot.id if snapshot else None,
        "mode": raw.get("mode"),
        "run_type": raw.get("run_type"),
        "current_balance_due": snapshot.balance_due if snapshot else None,
        "previous_balance_due": previous.balance_due if previous else None,
        "details": raw,
        "property_details": [
            {
                "id": row.id,
                "property_number": row.property_number,
                "tax_map": row.tax_map,
                "property_address": row.property_address,
                "total_due": row.total_due,
                "detail_json": row.detail_json,
            }
            for row in property_rows
        ],
    }
