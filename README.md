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

## Trigger Tax Bot run

```bash
curl -X POST http://localhost:8000/api/bots/tax/run
```

## API

- `GET /api/health`
- `GET /api/bots`
- `POST /api/bots/tax/run`

The backend seeds `Tax Bot v0` (`slug=tax`) on startup if missing.
