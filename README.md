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

## Test the Onondaga public-access flow step by step

This project now supports a configurable pre-navigation flow so you can validate portals that require agreement clicks before search.

### 1) Start services in real scraper mode

```bash
USE_REAL_SCRAPER=1 docker compose up -d --build
```

### 2) Open the dashboard

- Frontend: http://localhost:3000
- Expand **Tax Bot v0** → **Edit Config**.

### 3) Set config values for your target flow

Use these values:

- **Parcel ID**: `Yazara`
- **Portal URL**: `https://ocfintax.ongov.net/Imate/viewlist.aspx?sort=printkey&swis=all&ownernamel=Yazara`
- **Pre-steps JSON**:

```json
[
  { "action": "click", "text": "Click Here for Public Access", "timeout_ms": 20000 },
  { "action": "check", "selector": "input[type='checkbox']", "timeout_ms": 20000 },
  { "action": "click", "text": "Continue", "timeout_ms": 20000 }
]
```

- **Checkpoint Selector**: selector matching each property row on the list page. Start with:
  - `table tr` (broad fallback)
  - or a more specific selector from browser dev tools once inspected.
- **Checkpoint Min Count**: `3`
- **Stop after checkpoint proof**: checked (`true`)

Leave parcel/search selectors empty while validating this agreement flow.

### 4) Save and run

1. Click **Save**.
2. Click **Run Now**.

If successful, the bot proves checkpoint success by asserting at least 3 matches for your checkpoint selector after the pre-steps complete.

### 5) If it fails, tune selectors

- Error output includes a text excerpt and screenshot path (`/tmp/taxbot_last_error.png`).
- Most common fixes:
  - Make the pre-step click/check selectors more specific.
  - Increase `timeout_ms` for slower redirects.
  - Refine `Checkpoint Selector` so it matches one row per property.

### Supported pre-step actions

`pre_steps` accepts an array of actions executed in order:

- `click` (`selector` or `text`)
- `check` (`selector` or `text`)
- `fill` (`selector` or `text`, plus `value`)
- `wait_for_selector` (`selector` or `text`)
- `wait_for_url` (`url`)
- `wait_for_timeout` (`ms`)

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
