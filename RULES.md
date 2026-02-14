# RULES.md — Agent Admin Dashboard

These rules define the non-negotiable boundaries for building and evolving the **Agent Admin Dashboard** app.
If any instruction conflicts with this file, **this file wins**.

---

## 0) Authority & Immutability

1. **This file (RULES.md) is immutable to the AI.**
   - The AI must not modify it, rewrite it, or propose edits by default.
   - If changes are truly necessary, the AI may *suggest* edits in chat, but must not commit them.

2. **PLAN.md is the source of truth for what to do next.**
   - All work should map to a step in PLAN.md.
   - Any plan changes must be written back into PLAN.md (append a dated note; don’t silently rewrite history).

3. **UI-first, bot-by-bot.**
   - Ship useful bots one at a time (ex: “Tax Bot v0”) before adding abstractions.
   - No generalized “agent framework” until at least **2–3 real bots** exist and the shared patterns are obvious.

---

## 1) Runtime & Environment (Docker-First)

4. The entire app must run **inside Docker** and be bootable with:

   `docker compose up -d --build`

5. **No host dependencies** besides Docker / Docker Compose.
   - No “install Python/Node locally” steps.
   - Any tooling (linters, formatters, tests, migrations) must run inside containers.

6. The app must be accessible at a stable local URL:

   `http://localhost:${DASHBOARD_PORT}`

   - `DASHBOARD_PORT` must default to a sensible value (ex: `3000`), configurable via `.env`.

7. **Bind mounts are required.**
   - All source files must be mounted into the containers so changes on the host reflect immediately in the running app.
   - Generated/runtime-only artifacts may live in container volumes, but anything a human needs to inspect should be persisted to the repo (or a mounted `./artifacts` directory).

---

## 2) Repo Structure & Conventions

8. Use a simple, obvious structure (example):

   - `backend/` (Python API)
   - `frontend/` (UI)
   - `docker/` (optional helpers)
   - `compose.yml` (or `docker-compose.yml`)
   - `PLAN.md`, `RULES.md`, `README.md`, `CHANGELOG.md`
   - `artifacts/` (mounted; request logs, scrape evidence, change snapshots, etc.)

9. Prefer boring, debuggable architecture over cleverness.
   - Minimal moving parts.
   - Clear boundaries: UI ↔ API ↔ storage.

10. Every feature must include:
   - Where it lives (files/modules)
   - How to run it (compose / commands)
   - How it’s tested (even if lightweight)

---

## 3) Backend Rules (Python)

11. The backend must be written in **Python**.

12. The backend must expose a stable HTTP API for the dashboard and bots.
   - Favor explicit endpoints and predictable JSON shapes.
   - If schemas exist, validate inputs/outputs.

13. Data persistence must be explicit.
   - Use a real persistence mechanism (ex: SQLite/Postgres) rather than “memory-only.”
   - Database data must persist across container restarts (volume) unless intentionally ephemeral.

14. Observability is not optional.
   - Structured logs (request id, bot id, run id).
   - Errors must be actionable (stack traces available in dev).
   - Store bot-run evidence to `./artifacts` (mounted) when it matters (scrape results, diffs, notifications sent, etc.).

---

## 4) LLM Provider Rules (Environment-Driven, Not Hard-Coded)

15. The application must support LLM usage through environment configuration only.

16. The following environment variables must be read from the root `.env` file:

   - `OPENAI_API_KEY`
   - `LLM_PROVIDER`
   - `LLM_MODEL`
   - `DASHBOARD_PORT`
   - `NOTIFICATION_TEXT_PHONE`

17. Expected `.env` pattern:

```
OPENAI_API_KEY=...
LLM_PROVIDER=openai
LLM_MODEL=gpt-5.2
DASHBOARD_PORT=3000
NOTIFICATION_TEXT_PHONE=""
```


18. The LLM provider must **not** be hard-coded anywhere in the codebase.
- The system must dynamically select the provider based on `LLM_PROVIDER`.
- If `LLM_PROVIDER=openai`, use `OPENAI_API_KEY` and `LLM_MODEL`.
- If additional providers are added later, they must follow the same environment-driven pattern.

19. Secrets must never be logged, committed, or written to artifacts.
- `OPENAI_API_KEY` must never appear in logs.
- No keys in screenshots, commits, or test fixtures.

20. The application must fail clearly and explicitly if required LLM environment variables are missing.
- No silent fallback behavior.
- Error message must clearly state which variable is missing.

---

## 5) Frontend Rules (AI May Choose Stack)

21. The AI may choose the frontend framework and styling approach, but must optimize for:
- Speed of iteration inside Docker
- Reliability and maintainability
- Clear UI for bot status, runs, logs/evidence, and config

22. The frontend must not contain “secret business logic.”
- If logic affects correctness or authority (ex: scheduling, state transitions, persistence), it belongs in the backend.

---

## 6) Documentation Discipline

23. `README.md` must always be kept up to date.
- It must be updated immediately before commits if behavior changes.
- It must contain:
  - Install instructions
  - How to run the app
  - How to perform a quick smoke test to confirm installation worked

24. `README.md` must **not** become a full knowledge base or deep documentation.
- Keep it concise.
- Detailed design rationale belongs in PLAN.md or code comments.

25. `CHANGELOG.md` must be updated before updating the README.
- Add concise bullet points describing what changed.
- One logical entry per completed task/step.

---

## 7) Commit & Change Discipline

26. Every step/task must have its own commit.
- No batching unrelated work into one commit.
- Commit immediately upon task completion.

27. Every commit must include a detailed, descriptive message explaining:
- What changed
- Why it changed
- Any architectural impact

28. Commits must be pushed to the `master` branch immediately upon completion.
- The master branch serves as the canonical change history.

29. Work must be incremental and traceable.
- If a task spans multiple concerns, split it.
- History must clearly tell the story of how the system evolved.

---

## 8) “No Fake Shipping” Rule

30. No fake/demo data in the default experience once real wiring exists.
- It’s fine to scaffold UI placeholders, but as soon as endpoints exist, the UI must read real data.
- If mock mode exists, it must be explicit (ex: `MOCK_MODE=1`) and off by default.

---

## 9) Testing & Determinism

31. Tests must run inside Docker.
- Provide at least: a smoke test and a minimal happy-path run for the first bot.

32. Prefer deterministic tests.
- If a bot scrapes external sites, include a test mode with fixtures/snapshots.
- Avoid flaky tests that depend on live websites unless explicitly marked as “manual/integration.”

---

## 10) Security & Secrets

33. Secrets must never be committed.
- Use `.env` (gitignored) and documented `.env.example`.
- No keys/tokens in logs, artifacts, or screenshots.

34. If the app touches external services (email/SMS/webhooks), ensure:
- Explicit configuration
- Safe defaults (no accidental spam)
- Rate limiting / retry discipline

---

## 11) Default Ports & Naming (Consistency)

35. Standardize defaults:
- `DASHBOARD_PORT=3000` (or similar)
- Backend port internal-only unless needed externally
- Consistent container names and service names (`frontend`, `backend`, `db`)

36. Keep names stable once chosen (service names, env vars, routes) to reduce churn.

---

## 12) Prime Directive

37. Optimize for: **fast iteration, clear evidence, and real bots shipped one-by-one**.
- Build what’s needed now.
- Generalize only after patterns are proven in production-like usage.
