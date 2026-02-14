from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import crud
from app.bots.tax.runner import run_tax_refresh
from app.models import Base, TaxPropertySnapshot


def _test_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)
    return factory()


def test_runner_commits_snapshots_only_on_success() -> None:
    db = _test_session()
    try:
        bot = crud.seed_tax_bot(db)
        run = crud.create_run(db, bot.id)
        events = []

        def fake_scraper(**_: dict):
            return {
                "artifacts_root": "/artifacts/runs/run_1",
                "url_results": [
                    {
                        "status": "success",
                        "source_url": "https://example.com/1",
                        "final_url": "https://example.com/final/1",
                        "property_address": "104 MOONEY AVE.",
                        "total_due": "100.00",
                    },
                    {
                        "status": "success",
                        "source_url": "https://example.com/2",
                        "final_url": "https://example.com/final/2",
                        "property_address": "200 MAIN ST.",
                        "total_due": "250.00",
                    },
                ],
                "snapshots": [
                    {
                        "source_url": "https://example.com/1",
                        "source_account_number": "111",
                        "final_url": "https://example.com/final/1",
                        "property_address": "104 MOONEY AVE.",
                        "total_due": "100.00",
                        "tables_json": [{"rows": [["TOTAL", "$100.00"]]}],
                        "metadata_json": {},
                        "scraped_at": datetime.now(timezone.utc),
                    },
                    {
                        "source_url": "https://example.com/2",
                        "source_account_number": "222",
                        "final_url": "https://example.com/final/2",
                        "property_address": "200 MAIN ST.",
                        "total_due": "250.00",
                        "tables_json": [{"rows": [["TOTAL", "$250.00"]]}],
                        "metadata_json": {},
                        "scraped_at": datetime.now(timezone.utc),
                    },
                ],
            }

        result = run_tax_refresh(db, bot, run, event_callback=events.append, scraper_func=fake_scraper)

        assert result["status"] == "success"
        assert result["snapshot_count"] == 2
        assert db.query(TaxPropertySnapshot).count() == 2
        assert any(event.get("type") == "db_committed" for event in events)
    finally:
        db.close()


def test_runner_keeps_database_unchanged_on_partial_failure() -> None:
    db = _test_session()
    try:
        bot = crud.seed_tax_bot(db)
        run = crud.create_run(db, bot.id)

        def fake_scraper(**_: dict):
            return {
                "artifacts_root": "/artifacts/runs/run_2",
                "url_results": [
                    {
                        "status": "success",
                        "source_url": "https://example.com/1",
                        "final_url": "https://example.com/final/1",
                        "property_address": "104 MOONEY AVE.",
                        "total_due": "100.00",
                    },
                    {
                        "status": "failed",
                        "source_url": "https://example.com/2",
                        "final_url": "https://example.com/final/2",
                        "error": "Structured table data not found on page",
                    },
                ],
                "snapshots": [
                    {
                        "source_url": "https://example.com/1",
                        "source_account_number": "111",
                        "final_url": "https://example.com/final/1",
                        "property_address": "104 MOONEY AVE.",
                        "total_due": "100.00",
                        "tables_json": [{"rows": [["TOTAL", "$100.00"]]}],
                        "metadata_json": {},
                        "scraped_at": datetime.now(timezone.utc),
                    }
                ],
            }

        result = run_tax_refresh(db, bot, run, scraper_func=fake_scraper)

        assert result["status"] == "failed"
        assert db.query(TaxPropertySnapshot).count() == 0
    finally:
        db.close()
