# AI-Driven Job Hunter

Automated job-hunting pipeline that collects vacancies from multiple sources, deduplicates and pre-filters them, scores relevance against a candidate profile using Gemini (Structured Output), and sends high-match alerts to Telegram with a FastAPI + HTMX management dashboard.

> **Status:** Early development (Phase 0 / infrastructure & core setup).

## Architecture

The system runs as two decoupled processes sharing a single service/repository layer and a PostgreSQL database (Supabase):

1. **Batch Worker (GitHub Actions Cron):** Hourly ingestion from RSS/API feeds and IMAP email alerts, deterministic pre-filtering, batch AI scoring, and Telegram push notifications.
2. **Web & Webhook Service (FastAPI + HTMX):** Protected dashboard for reviewing vacancies, managing candidate profile/calibration examples, and handling Telegram inline button callbacks (`Applied` / `Skip`).

## Tech Stack

- **Language & Tooling:** Python 3.12, `uv`, `ruff`, `mypy` (`strict`), `pytest`
- **Database:** PostgreSQL (Supabase), SQLAlchemy 2.0 (async), `asyncpg`, Alembic
- **Web & API:** FastAPI, Jinja2, HTMX
- **AI & Integrations:** Google Gemini API (Structured Outputs), Telegram Bot API, `httpx`
- **CI/CD & Security:** GitHub Actions (`ruff`, `mypy`, `semgrep`), Docker

## Project Structure

```text
src/job_hunter/
├── ai/             # Gemini client, prompts, structured output schemas
├── core/           # Configuration (pydantic-settings), security, logging
├── db/             # Async session, ORM models, repositories
├── notifications/  # Telegram bot sender
├── services/       # Shared business logic (pipeline, calibration, vacancies)
├── sources/        # Job source adapters (RSS, API, IMAP email)
├── web/            # FastAPI app, routers, HTMX templates
└── worker/         # CLI entrypoint for scheduled runs
```
