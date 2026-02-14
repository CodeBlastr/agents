from __future__ import annotations

from typing import Any, Callable

from sqlalchemy.orm import Session

from app import crud
from app.bots.tax.scraper import scrape_tax_data
from app.models import Bot, BotRun
from app.settings import get_settings

EventCallback = Callable[[dict[str, Any]], None]


def run_tax_refresh(
    db: Session,
    bot: Bot,
    run: BotRun,
    event_callback: EventCallback | None = None,
    scraper_func: Callable[..., dict[str, Any]] = scrape_tax_data,
) -> dict[str, Any]:
    settings = get_settings()
    config = crud.get_bot_config(db, bot.id)
    table_selector = str(config.get("table_selector") or "table")

    if event_callback:
        event_callback({"type": "run_started", "run_id": run.id, "bot_slug": bot.slug})

    try:
        scrape_result = scraper_func(
            run_id=run.id,
            source_urls=list(settings.tax_source_urls),
            artifacts_dir=settings.artifacts_dir,
            table_selector=table_selector,
            event_callback=event_callback,
        )

        url_results = scrape_result.get("url_results") or []
        snapshots = scrape_result.get("snapshots") or []
        failures = [item for item in url_results if item.get("status") != "success"]

        details_json = {
            "artifacts_root": scrape_result.get("artifacts_root"),
            "source_urls": list(settings.tax_source_urls),
            "url_results": url_results,
        }

        if failures:
            error_summary = (
                f"Run failed: {len(failures)} of {len(url_results)} source URL(s) did not return structured table data"
            )
            crud.finalize_run(
                db,
                run,
                status="failed",
                error_summary=error_summary,
                details_json=details_json,
            )
            result = {
                "status": "failed",
                "run_id": run.id,
                "bot_slug": bot.slug,
                "error_summary": error_summary,
                "details_json": details_json,
                "snapshot_count": 0,
            }
            if event_callback:
                event_callback({"type": "run_finished", **result})
            return result

        created = crud.create_tax_property_snapshots(db, bot.id, run.id, snapshots)
        details_json["saved_snapshot_ids"] = [row.id for row in created]

        crud.finalize_run(
            db,
            run,
            status="success",
            error_summary=None,
            details_json=details_json,
        )

        if event_callback:
            event_callback(
                {
                    "type": "db_committed",
                    "run_id": run.id,
                    "bot_slug": bot.slug,
                    "snapshot_count": len(created),
                }
            )

        result = {
            "status": "success",
            "run_id": run.id,
            "bot_slug": bot.slug,
            "error_summary": None,
            "details_json": details_json,
            "snapshot_count": len(created),
        }
        if event_callback:
            event_callback({"type": "run_finished", **result})
        return result

    except Exception as exc:
        details_json = {"fatal_error": str(exc)}
        crud.finalize_run(
            db,
            run,
            status="failed",
            error_summary=str(exc),
            details_json=details_json,
        )
        result = {
            "status": "failed",
            "run_id": run.id,
            "bot_slug": bot.slug,
            "error_summary": str(exc),
            "details_json": details_json,
            "snapshot_count": 0,
        }
        if event_callback:
            event_callback({"type": "run_finished", **result})
        return result
