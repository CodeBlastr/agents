# Agent Admin Dashboard (Docker-first)

A local admin dashboard with a Python FastAPI backend, Postgres, and a React+Vite frontend.

Current shipped bot: `Tax Bot v0`.

## Install

```bash
cp .env.example .env
docker compose up -d --build
```

Dashboard URL:

- `http://localhost:${DASHBOARD_PORT}` (defaults to `http://localhost:3000`)

## Run the app

```bash
docker compose up -d --build
```

To watch logs:

```bash
docker compose logs -f backend frontend
```

## Quick smoke test

1. Open `http://localhost:${DASHBOARD_PORT}`.
2. Confirm the index page shows a `Tax Bot v0` card.
3. Click `Refresh Data`.
4. Confirm live events stream in.
5. Confirm latest per-property rows appear after `db_committed` / `run_finished`.

API smoke check:

```bash
curl http://localhost:${DASHBOARD_PORT:-3000}/api/health
```

Expected JSON keys: `status`, `llm_provider`, `llm_model`.

## Tests (inside Docker)

```bash
docker compose run --rm -e DATABASE_URL=sqlite+pysqlite:////tmp/test.db backend pytest
```

## API endpoints

- `GET /api/health`
- `GET /api/bots`
- `GET /api/bots/{slug}`
- `GET /api/bots/{slug}/properties/latest`
- `GET /api/bots/{slug}/properties/{property_address}/history?limit=20`
- `POST /api/bots/{slug}/refresh`
- `GET /api/bots/{slug}/runs/{run_id}`
- `GET /api/bots/{slug}/runs/{run_id}/events`

## Syracuse source URLs (hard-coded in v1)

- `https://syracuse.go2gov.net/faces/accounts?number=0562001300&src=SDG`
- `https://syracuse.go2gov.net/faces/accounts?number=1626103200&src=SDG`
- `https://syracuse.go2gov.net/faces/accounts?number=0716100700&src=SDG`

The scraper waits for redirect completion and table visibility, captures per-URL artifacts, and fails the run if structured table data is missing for any URL.
