# CODEBASE.md — LAN Dashboard File Map

## Files to Modify (Issue #1 — PostgreSQL Migration)

- `requirements.txt` — Python dependencies; add `psycopg2-binary>=2.9`
- `docker-compose.yml` — Orchestration config; full rewrite to add `db` (PostgreSQL 16) service, `postgres-data` named volume, health check, `depends_on` for `web`; remove `app-data` SQLite volume
- `.env.example` — Env var template; update `DATABASE_URL` to PostgreSQL format; add `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `Dockerfile` — Image build; remove `RUN mkdir -p /app/data` and `ENV DATABASE_URL=sqlite:...`; no other changes
- `alembic/env.py` — Alembic runtime config; make `render_as_batch` conditional on dialect (`sqlite` vs `postgresql`) in both `run_migrations_offline()` and `run_migrations_online()`
- `alembic/versions/0002_custom_games.py` — Migration 0002; replace `op.batch_alter_table` context manager with dialect-conditional logic (batch for SQLite, direct `op.alter_column` for PostgreSQL)
- `alembic.ini` — Alembic static config; update `sqlalchemy.url` to a placeholder comment (it's overridden at runtime by `env.py`)

## Files to Verify Only (no changes expected)

- `app/database.py` — SQLAlchemy engine setup; already dialect-conditional (`check_same_thread` only for SQLite); no changes needed
- `app/config.py` — Pydantic settings; reads `DATABASE_URL` from env; no changes needed
- `app/main.py` — FastAPI app + lifespan; seeds invite tokens; no changes needed
- `.github/workflows/docker.yml` — CI/CD pipeline; verify no SQLite-specific steps; update if any references to `app-data` or SQLite ENV exist
- `alembic/versions/0001_initial_schema.py` — Initial schema migration; uses `if table not in existing` guards — idempotent and works for both dialects; no changes needed

## Files Not Touched

- `app/models.py` — SQLAlchemy ORM models (User, Game, Score, InviteToken, FeatureRequest, FeatureComment, GameOwnership)
- `app/auth.py` — bcrypt password hashing/verification
- `app/dependencies.py` — FastAPI DB session and auth dependencies
- `app/schemas.py` — Pydantic request/response schemas
- `app/routers/auth_routes.py` — Login/register/logout routes
- `app/routers/scoreboard.py` — Game scoring endpoints
- `app/routers/admin.py` — Admin token and user management
- `app/routers/feature_requests.py` — Feature request routes
- `app/steam.py` — Steam API integration (httpx)
- `app/limiter.py` — slowapi rate limiter
- `app/static/style.css` — Frontend CSS
- `app/templates/*.html` — Jinja2 HTML templates

## Key Dependencies Between Modified Files

- `docker-compose.yml` adds `db` service → `.env.example` must have `POSTGRES_DB/USER/PASSWORD` to match
- `.env.example` `DATABASE_URL` uses hostname `db` → matches the service name in `docker-compose.yml`
- `alembic/env.py` reads `settings.DATABASE_URL` → `app/config.py` → env var `DATABASE_URL`
- `Dockerfile` no longer sets `DATABASE_URL` ENV → `docker-compose.yml` `env_file: .env` is now the sole source of `DATABASE_URL`
- `0002_custom_games.py` revision chains: `down_revision = "0001"` → runs after `0001_initial_schema.py`
