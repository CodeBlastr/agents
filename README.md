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

## Real scraper mode (best-effort)

By default, Tax Bot runs in deterministic stub mode.

To enable Playwright-backed scraping mode, set `USE_REAL_SCRAPER=1` for backend (already wired in compose):

```bash
USE_REAL_SCRAPER=1 docker compose up -d --build
```

Real scraping is best-effort; many portals need custom selectors and regex in Tax Bot config.

## Configure + run Tax Bot

Set config:

```bash
curl -X PUT http://localhost:8000/api/bots/tax/config \
  -H 'Content-Type: application/json' \
  -d '{
    "parcel_id":"TEST1",
    "portal_url":"https://example.com",
    "portal_profile":{
      "parcel_selector":null,
      "search_button_selector":null,
      "results_container_selector":null,
      "balance_regex":"\\$?\\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\\.[0-9]{2})?)"
    }
  }'
```

Run bot:

```bash
curl -X POST http://localhost:8000/api/bots/tax/run
```

## API

- `GET /api/health`
- `GET /api/bots`
- `GET /api/bots/tax/config`
- `PUT /api/bots/tax/config`
- `POST /api/bots/tax/run`
- `GET /api/notifications?bot=tax&limit=20`

The backend seeds `Tax Bot v0` (`slug=tax`) on startup if missing and ensures default config at key `tax.default`.
