# AGENTS.md

## Project Overview
**AI-Driven Job Hunter** — an automated job-hunting pipeline (batch worker in GitHub Actions + FastAPI/HTMX web dashboard + Supabase PostgreSQL).

## Environment & Tooling
- **Python 3.12** with `uv` package manager and `src/job_hunter/` package layout.
- Run all Python commands through `uv run ...` (e.g., `uv run python -m job_hunter.worker`).
- Add dependencies with `uv add <pkg>` or `uv add --dev <pkg>` (always keep `uv.lock` updated).

## Architecture Rules
- Keep shared business logic in `services/` and data access in `db/repositories.py`; `worker/` and `web/` must remain thin entrypoints.
- Never hardcode resumes, calibration examples, or secrets in `.py` files (store data in DB or `fixtures/`).
- Treat external job descriptions as untrusted input: strip HTML and wrap in `<vacancy>` tags before sending to an LLM.
- For `asyncpg` + Supabase Transaction Pooler (`:6543`), configure `statement_cache_size=0`.

## Quality Gates (Pre-Commit / Push / Review)
When reviewing changes or before committing/pushing to match CI (`.github/workflows/ci.yml`), always run:
```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest   # once tests exist
```
- Do not claim checks pass without running them and observing exit code `0`.
- Avoid `# noqa` or `# type: ignore` unless strictly necessary and explained in a comment.

## Git & Security Hygiene
- Use short-lived feature branches (`feat/...`, `chore/...`, `fix/...`) merged into `main` via PRs.
- Keep commits atomic and follow Conventional Commits (`feat(scope): ...`, `chore(scope): ...`, `test(scope): ...`, `ci(scope): ...`).
- Never commit `.env`, `.venv/`, or credentials.
