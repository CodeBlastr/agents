from sqlalchemy.orm import Session

from app import crud
from app.bots.tax.parser import parse_tax_data
from app.bots.tax.scraper import scrape_tax_data
from app.models import Bot, BotRun


def run_tax_bot(db: Session, bot: Bot, config: dict, run_id: int | None = None, event_callback=None) -> dict:
    run = db.query(BotRun).filter(BotRun.id == run_id).first() if run_id else None
    if run is None:
        run = crud.create_run(db, bot.id)
    try:
        if event_callback:
            event_callback({"type": "run_started", "run_id": run.id})
        scraped = scrape_tax_data(
            parcel_id=config["parcel_id"],
            portal_url=config["portal_url"],
            portal_profile=config.get("portal_profile") or {},
            run_id=run.id,
            event_callback=event_callback,
        )
        parsed = parse_tax_data(scraped)

        previous = crud.latest_previous_snapshot(db, bot.id, parsed["parcel_id"], parsed["portal_url"])
        snapshot = crud.create_snapshot(db, bot.id, parsed)

        property_details = (parsed.get("raw_json") or {}).get("property_details") or []
        if property_details:
            crud.create_tax_property_details(db, bot.id, run.id, property_details)

        changed = False
        previous_balance = None
        if previous:
            previous_balance = previous.balance_due
            changed = any(
                [
                    snapshot.balance_due != previous.balance_due,
                    snapshot.paid_status != previous.paid_status,
                    snapshot.due_date != previous.due_date,
                ]
            )

        if changed:
            crud.create_notification(
                db,
                bot.id,
                (
                    f"Tax change detected for {snapshot.parcel_id}: "
                    f"balance={snapshot.balance_due}, paid_status={snapshot.paid_status}, due_date={snapshot.due_date}"
                ),
            )

        crud.finalize_run(db, run, "success")
        result = {
            "bot_slug": bot.slug,
            "status": "success",
            "run_id": run.id,
            "snapshot_id": snapshot.id,
            "changed": changed,
            "message": "Tax bot completed",
            "mode": scraped.get("mode") or "unknown",
            "run_type": scraped.get("run_type") or "full_extract",
            "current_balance_due": snapshot.balance_due,
            "previous_balance_due": previous_balance,
            "details": snapshot.raw_json,
            "property_details": [
                {
                    "property_number": item.get("property_number"),
                    "tax_map": item.get("tax_map"),
                    "property_address": item.get("property_address") or "Unknown",
                    "total_due": item.get("total_due") or "0.00",
                    "detail_json": item,
                }
                for item in property_details
            ],
        }
        if event_callback:
            event_callback({"type": "run_finished", "run_id": run.id, "status": "success", "result": result})
        return result
    except Exception as exc:
        crud.finalize_run(db, run, "error", str(exc))
        result = {
            "bot_slug": bot.slug,
            "status": "error",
            "run_id": run.id,
            "snapshot_id": None,
            "changed": False,
            "message": str(exc),
            "mode": "real" if "Real scrape failed:" in str(exc) else "unknown",
            "run_type": "failed",
            "current_balance_due": None,
            "previous_balance_due": None,
            "details": {"error": str(exc)},
            "property_details": [],
        }
        if event_callback:
            event_callback({"type": "run_finished", "run_id": run.id, "status": "error", "result": result})
        return result
