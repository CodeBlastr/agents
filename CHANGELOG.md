# CHANGELOG

## 2026-02-14
- Rebuilt the project as a Docker-first Agent Admin Dashboard v2 with backend/frontend bind mounts and stable `DASHBOARD_PORT` frontend access.
- Implemented a Python FastAPI backend with Postgres persistence, Alembic migration, seeded `tax` bot, and SSE run-event streaming.
- Implemented redirect-aware Playwright scraping for the three fixed Syracuse URLs and hard-fail semantics when structured table data is missing.
- Added persistent `tax_property_snapshots` storage keyed by property address with timestamps and run-linked diagnostics.
- Implemented index and bot-detail dashboard pages with real-time refresh status, latest DB-backed property data, and run diagnostics.
- Removed notification/email/texting APIs, models, and UI paths from the application scope.
- Added deterministic backend tests (smoke, runner success/failure behavior, scraper helper parsing).
