from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from app.models import Bot, BotConfig, BotRun, TaxPropertySnapshot

DEFAULT_TAX_CONFIG = {
    "version": "v1",
    "table_selector": "table",
    "source_urls_mode": "hard_coded",
}


def seed_tax_bot(db: Session) -> Bot:
    bot = db.query(Bot).filter(Bot.slug == "tax").first()
    if not bot:
        bot = Bot(slug="tax", name="Tax Bot v0")
        db.add(bot)
        db.commit()
        db.refresh(bot)

    config = (
        db.query(BotConfig)
        .filter(BotConfig.bot_id == bot.id, BotConfig.key == "tax.default")
        .first()
    )
    if not config:
        config = BotConfig(bot_id=bot.id, key="tax.default", config_json=DEFAULT_TAX_CONFIG)
        db.add(config)
        db.commit()
    return bot


def get_bot_by_slug(db: Session, slug: str) -> Bot | None:
    return db.query(Bot).filter(Bot.slug == slug).first()


def get_bot_config(db: Session, bot_id: int, key: str = "tax.default") -> dict:
    config = db.query(BotConfig).filter(BotConfig.bot_id == bot_id, BotConfig.key == key).first()
    if not config:
        return DEFAULT_TAX_CONFIG
    return config.config_json or DEFAULT_TAX_CONFIG


def list_bot_summaries(db: Session) -> list[dict]:
    bots = db.query(Bot).order_by(Bot.id.asc()).all()
    summaries: list[dict] = []

    for bot in bots:
        last_run = (
            db.query(BotRun)
            .filter(BotRun.bot_id == bot.id)
            .order_by(desc(BotRun.started_at), desc(BotRun.id))
            .first()
        )
        latest_property_count = len(list_latest_properties_for_bot(db, bot.id))
        summaries.append(
            {
                "slug": bot.slug,
                "name": bot.name,
                "last_run_id": last_run.id if last_run else None,
                "last_run_status": last_run.status if last_run else None,
                "last_run_at": last_run.started_at if last_run else None,
                "last_error_summary": last_run.error_summary if last_run else None,
                "latest_property_count": latest_property_count,
            }
        )

    return summaries


def list_recent_runs_for_bot(db: Session, bot_id: int, limit: int = 20) -> list[BotRun]:
    return (
        db.query(BotRun)
        .filter(BotRun.bot_id == bot_id)
        .order_by(desc(BotRun.started_at), desc(BotRun.id))
        .limit(limit)
        .all()
    )


def create_run(db: Session, bot_id: int) -> BotRun:
    run = BotRun(
        bot_id=bot_id,
        status="running",
        started_at=datetime.now(timezone.utc),
        details_json={},
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def finalize_run(
    db: Session,
    run: BotRun,
    status: str,
    error_summary: str | None = None,
    details_json: dict | None = None,
) -> BotRun:
    run.status = status
    run.finished_at = datetime.now(timezone.utc)
    run.error_summary = error_summary
    if details_json is not None:
        run.details_json = details_json
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def create_tax_property_snapshots(
    db: Session,
    bot_id: int,
    run_id: int,
    snapshots: list[dict],
) -> list[TaxPropertySnapshot]:
    rows: list[TaxPropertySnapshot] = []
    for item in snapshots:
        row = TaxPropertySnapshot(
            bot_id=bot_id,
            run_id=run_id,
            source_url=item["source_url"],
            source_account_number=item.get("source_account_number"),
            final_url=item["final_url"],
            property_address=item["property_address"],
            total_due=Decimal(str(item["total_due"])),
            tables_json=item["tables_json"],
            metadata_json=item.get("metadata_json") or {},
            scraped_at=item["scraped_at"],
        )
        db.add(row)
        rows.append(row)

    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def list_latest_properties_for_bot(db: Session, bot_id: int) -> list[TaxPropertySnapshot]:
    invalid_addresses = {"", "Property Number", "Property Address"}
    ranked = (
        select(
            TaxPropertySnapshot.id.label("snapshot_id"),
            func.row_number()
            .over(
                partition_by=TaxPropertySnapshot.property_address,
                order_by=(TaxPropertySnapshot.scraped_at.desc(), TaxPropertySnapshot.id.desc()),
            )
            .label("rn"),
        )
        .where(
            TaxPropertySnapshot.bot_id == bot_id,
            ~TaxPropertySnapshot.property_address.in_(invalid_addresses),
        )
        .subquery()
    )

    return (
        db.query(TaxPropertySnapshot)
        .join(ranked, TaxPropertySnapshot.id == ranked.c.snapshot_id)
        .filter(ranked.c.rn == 1)
        .order_by(TaxPropertySnapshot.property_address.asc())
        .all()
    )


def list_property_history(
    db: Session,
    bot_id: int,
    property_address: str,
    limit: int,
) -> list[TaxPropertySnapshot]:
    return (
        db.query(TaxPropertySnapshot)
        .filter(
            and_(
                TaxPropertySnapshot.bot_id == bot_id,
                TaxPropertySnapshot.property_address == property_address,
            )
        )
        .order_by(desc(TaxPropertySnapshot.scraped_at), desc(TaxPropertySnapshot.id))
        .limit(limit)
        .all()
    )


def get_run_by_id(db: Session, bot_id: int, run_id: int) -> BotRun | None:
    return db.query(BotRun).filter(BotRun.bot_id == bot_id, BotRun.id == run_id).first()


def get_run_details(db: Session, bot_slug: str, bot_id: int, run_id: int) -> dict | None:
    run = get_run_by_id(db, bot_id, run_id)
    if not run:
        return None

    rows = (
        db.query(TaxPropertySnapshot)
        .filter(TaxPropertySnapshot.bot_id == bot_id, TaxPropertySnapshot.run_id == run.id)
        .order_by(TaxPropertySnapshot.property_address.asc(), TaxPropertySnapshot.id.asc())
        .all()
    )

    return {
        "run_id": run.id,
        "bot_slug": bot_slug,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "error_summary": run.error_summary,
        "details_json": run.details_json or {},
        "property_snapshots": rows,
    }
