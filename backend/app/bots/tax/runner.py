from sqlalchemy.orm import Session

from app import crud
from app.bots.tax.parser import parse_tax_data
from app.bots.tax.scraper import scrape_tax_data
from app.models import Bot


def run_tax_bot(db: Session, bot: Bot) -> dict:
    run = crud.create_run(db, bot.id)
    try:
        scraped = scrape_tax_data()
        parsed = parse_tax_data(scraped)

        previous = crud.latest_previous_snapshot(db, bot.id, parsed["parcel_id"], parsed["portal_url"])
        snapshot = crud.create_snapshot(db, bot.id, parsed)

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
        return {
            "bot_slug": bot.slug,
            "status": "success",
            "run_id": run.id,
            "snapshot_id": snapshot.id,
            "changed": changed,
            "message": "Tax bot completed",
            "current_balance_due": snapshot.balance_due,
            "previous_balance_due": previous_balance,
        }
    except Exception as exc:
        crud.finalize_run(db, run, "error", str(exc))
        return {
            "bot_slug": bot.slug,
            "status": "error",
            "run_id": run.id,
            "snapshot_id": None,
            "changed": False,
            "message": str(exc),
            "current_balance_due": None,
            "previous_balance_due": None,
        }
