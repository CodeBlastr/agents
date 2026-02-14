# Agents Dashboard (Docker-first)

Minimal local dashboard with a FastAPI backend, Postgres, and React+Vite frontend.

## Quickstart

```bash
cp .env.example .env
docker compose up -d --build
```

## URLs

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- Health: http://localhost:8000/api/health

1. Open http://localhost:3000
2. Expand **Tax Bot v0** → **Edit Config**.
3. Use **Scraper Mode** dropdown:
   - **Use Real Scraper** (default)
   - **Use Stub Scraper**
4. Click **Save**.

## Onondaga multi-property tax due flow

The real scraper can now run through property results and collect taxes due per property:

1. Configure portal and pre-steps.
2. Configure selectors:
   - **Results Row Selector** (default `table tr`)
   - **Row First Link Selector** (default `td:first-child a`)
   - **Detail Table Selector** (default `table`)
   - **Max Properties** (default `3`)
3. Click **Run Now**.
4. During run, the left column updates in real time with:
   - **Property Address | Total Due**
5. Right column continues streaming screenshots of each step.

## Database migration for property tax details

A new table stores per-property scraped table JSON + derived totals:

- Table: `tax_property_details`
- Migration: `backend/alembic/versions/0003_tax_property_details.py`

Run migrations:

```bash
cd backend
alembic upgrade head
```

When using Docker, migrations are also applied automatically at backend start via container command.

## API

- `GET /api/health`
- `GET /api/bots`
- `GET /api/bots/tax/config`
- `PUT /api/bots/tax/config`
- `POST /api/bots/tax/run`
- `POST /api/bots/tax/run/start`
- `GET /api/bots/tax/runs/{run_id}`
- `GET /api/bots/tax/runs/{run_id}/events`
- `GET /api/notifications?bot=tax&limit=20`

The backend seeds `Tax Bot v0` (`slug=tax`) on startup if missing and ensures default config at key `tax.default`.

## Syracuse direct page scraper

For one-off scraping of direct Syracuse account pages (including the three provided account URLs), use:

```bash
python backend/app/bots/tax/syracuse_scraper.py
```

This prints JSON with one record per page including:

- `account_number`
- `as_of_date`
- `tax_information_available`
- `tax_status_message`

You can also pass custom URLs and save output:

```bash
python backend/app/bots/tax/syracuse_scraper.py \
  'https://syracuse.go2gov.net/faces/accounts?number=0562001300&src=SDG' \
  'https://syracuse.go2gov.net/faces/accounts?number=1626103200&src=SDG' \
  'https://syracuse.go2gov.net/faces/accounts?number=0716100700&src=SDG' \
  --output syracuse_tax_data.json
```
