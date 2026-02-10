# AGENTS.md

## Project overview
- Backend service on FastAPI.
- Python 3.12+, Poetry, PostgreSQL, Redis, Celery.

## Setup commands
- Install: `poetry install`
- Run app: `poetry run uvicorn app.main:app --reload`
- Run worker: `poetry run celery -A worker.celery_app:celery_app worker -l INFO`

## Quality gates (must pass before final)
- Lint: `poetry run ruff check .`
- Format check: `poetry run ruff format --check .`
<!-- - Types: `poetry run mypy app` -->
- Tests: `poetry run pytest -q`

## Code style
- Prefer small pure functions and explicit typing.
- Do not introduce new dependencies without explicit justification.
- Keep API changes backward-compatible unless task explicitly says otherwise.
- Treat `app/constants.py` as compatibility-only; add/update constants in domain modules
  (`app/constants_auth.py`, `app/constants_blog.py`, `app/constants_media.py`,
  `app/constants_api.py`, `app/constants_system.py`).

## Safety / boundaries
- Never modify `.env*`, secrets, CI credentials.
- For destructive DB ops, ask for approval first.
- Avoid network calls in tests unless explicitly marked integration.

## Output expectations
- Return: changed files, rationale, commands run, and exact test results.
