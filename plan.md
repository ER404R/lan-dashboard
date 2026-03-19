# Plan: Fix Database Persistence (Issue #1)

## Root Cause Analysis

### Primary Bug — `.env.example` puts DB outside the Docker volume

The `.env.example` file sets:
```
DATABASE_URL=sqlite:///./lan_dashboard.db
```

This relative path resolves to `/app/lan_dashboard.db` inside the container (WORKDIR is `/app`).

The Docker volume in `docker-compose.yml` mounts only `/app/data/`:
```yaml
volumes:
  - app-data:/app/data
```

The Dockerfile sets the correct default:
```dockerfile
ENV DATABASE_URL="sqlite:///./data/lan_dashboard.db"
```
But `docker-compose.yml` loads `.env` via `env_file`, which **overrides** the Dockerfile ENV. So any user who copies `.env.example` → `.env` immediately breaks persistence — the DB lands at `/app/lan_dashboard.db`, which is inside the image layer, not the volume. Every image update wipes it.

### Secondary Issue — SQLite is fragile in Docker

SQLite is a single file. Any path confusion, volume misconfiguration, or accidental `docker-compose down -v` destroys all data. A proper client-server database (PostgreSQL) is isolated in its own container with its own named volume, completely decoupled from the application image lifecycle.

### Tertiary Issue — No DB readiness check at startup

The startup command is:
```sh
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
```
When PostgreSQL is added, the `web` container may start before Postgres is accepting connections, causing Alembic to fail and the app to not start.

---

## Solution Overview

1. **Switch to PostgreSQL** — adds a `postgres` service to docker-compose with its own persistent named volume, completely decoupled from the app image.
2. **Add a startup wait script** — retries DB connection before running Alembic.
3. **Update all config files** — Dockerfile, docker-compose.yml, .env.example, requirements.txt, alembic/env.py.
4. **Fix migration 0002** — replace `op.batch_alter_table` (SQLite-only idiom) with direct `op.alter_column` calls for PostgreSQL compatibility.

---

## Step-by-Step Implementation

### Step 1 — Add `psycopg2-binary` to `requirements.txt`

Append to the end of `requirements.txt`:
```
psycopg2-binary>=2.9
```

No other dependency changes needed. SQLAlchemy already supports PostgreSQL.

---

### Step 2 — Rewrite `docker-compose.yml`

Replace the file entirely with:

```yaml
services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    env_file:
      - .env
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10

  web:
    image: ghcr.io/er404r/lan-dashboard:latest
    restart: unless-stopped
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
    expose:
      - "8000"

  nginx:
    image: nginx:stable-alpine
    depends_on:
      - web
    volumes:
      - ./nginx/conf.d:/etc/nginx/conf.d
      - /etc/letsencrypt:/etc/letsencrypt
    ports:
      - "80:80"
      - "443:443"

volumes:
  postgres-data:
```

Key changes:
- Added `db` service (PostgreSQL 16 Alpine) with health check
- `web` service has `depends_on: db: condition: service_healthy` — waits for DB
- Removed `app-data` SQLite volume
- Removed `volumes: - app-data:/app/data` from web service
- Both `db` and `web` use `env_file: - .env`

---

### Step 3 — Update `.env.example`

Replace the file entirely:

```
SECRET_KEY=change-me-to-a-random-string
DATABASE_URL=postgresql://lan_user:lan_password@db:5432/lan_dashboard
REGISTRATION_ENABLED=true
ADMIN_INVITE_TOKEN=your-admin-token
SEED_INVITE_TOKENS=

POSTGRES_DB=lan_dashboard
POSTGRES_USER=lan_user
POSTGRES_PASSWORD=lan_password
```

Notes:
- `DATABASE_URL` now points to the `db` service hostname (as defined in docker-compose)
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` are used by the `postgres` Docker image to create the DB on first run
- These must match the credentials in `DATABASE_URL`

---

### Step 4 — Update `Dockerfile`

Replace the file entirely:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

Changes vs original:
- Remove `RUN mkdir -p /app/data` (no longer storing SQLite in the image)
- Remove `ENV DATABASE_URL="sqlite:///./data/lan_dashboard.db"` (DATABASE_URL comes from `.env` via docker-compose)
- CMD stays the same — `depends_on: condition: service_healthy` in docker-compose already ensures PostgreSQL is up

---

### Step 5 — Update `alembic/env.py`

Make `render_as_batch` conditional on the dialect. This prevents Alembic autogenerate from wrapping new PostgreSQL migrations in unnecessary batch contexts.

Change both `run_migrations_offline()` and `run_migrations_online()`:

In `run_migrations_offline()`, change:
```python
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
```
To:
```python
    _use_batch = url.startswith("sqlite")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_use_batch,
    )
```

In `run_migrations_online()`, change:
```python
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
```
To:
```python
        _use_batch = connection.dialect.name == "sqlite"
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=_use_batch,
        )
```

---

### Step 6 — Update `alembic/versions/0002_custom_games.py`

`op.batch_alter_table` works for both SQLite and PostgreSQL (Alembic handles it), but for PostgreSQL it is cleaner and more explicit to use direct `op.alter_column` calls. Replace the migration to work correctly on both databases:

Replace upgrade() and downgrade():

```python
def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("games") as batch_op:
            batch_op.alter_column("steam_appid", existing_type=sa.Integer(), nullable=True)
            batch_op.alter_column("steam_url", existing_type=sa.String(512), nullable=True)
            batch_op.alter_column("thumbnail_url", existing_type=sa.String(512), nullable=True)
    else:
        op.alter_column("games", "steam_appid", existing_type=sa.Integer(), nullable=True)
        op.alter_column("games", "steam_url", existing_type=sa.String(512), nullable=True)
        op.alter_column("games", "thumbnail_url", existing_type=sa.String(512), nullable=True)


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("games") as batch_op:
            batch_op.alter_column("steam_appid", existing_type=sa.Integer(), nullable=False)
            batch_op.alter_column("steam_url", existing_type=sa.String(512), nullable=False)
            batch_op.alter_column("thumbnail_url", existing_type=sa.String(512), nullable=False)
    else:
        op.alter_column("games", "steam_appid", existing_type=sa.Integer(), nullable=False)
        op.alter_column("games", "steam_url", existing_type=sa.String(512), nullable=False)
        op.alter_column("games", "thumbnail_url", existing_type=sa.String(512), nullable=False)
```

---

### Step 7 — Update `alembic.ini`

The `sqlalchemy.url` in `alembic.ini` is overridden at runtime by `env.py` (via `settings.DATABASE_URL`), so its value doesn't matter for execution. Update it to a clear placeholder so it's not confusing:

Change line 6 from:
```ini
sqlalchemy.url = sqlite:///./data/lan_dashboard.db
```
To:
```ini
# Overridden at runtime by alembic/env.py via DATABASE_URL env var
sqlalchemy.url = driver://user:pass@localhost/dbname
```

---

### Step 8 — Verify `app/database.py` (no changes needed)

The file already handles both SQLite and PostgreSQL correctly:
```python
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)
```
No changes required.

---

### Step 9 — Update GitHub Actions workflow (`.github/workflows/docker.yml`)

Read the existing workflow file. If it references any SQLite-specific build steps, environment variables, or the `app-data` volume, update those references. The workflow likely just builds and pushes the Docker image — no changes may be needed, but verify.

---

## Deployment Migration Notes

For anyone running the existing SQLite-based deployment who wants to preserve data:

1. Export data from the old SQLite DB (manual SQL export or `sqlite3 lan_dashboard.db .dump`)
2. Stand up the new PostgreSQL-based stack
3. Re-import data using `psql` against the new DB container

Since the issue states data is already being lost regularly, there is likely no data worth migrating. The new setup starts fresh.

**Deployment steps for a clean start:**
```sh
# Pull the updated stack
docker-compose pull

# Stop old containers (data already lost, so -v is safe here)
docker-compose down -v

# Start new stack — PostgreSQL initializes automatically
docker-compose up -d
```

---

## Files Modified

| File | Change |
|------|--------|
| `requirements.txt` | Add `psycopg2-binary>=2.9` |
| `docker-compose.yml` | Full rewrite: add `db` service, remove SQLite volume |
| `.env.example` | Update DATABASE_URL + add POSTGRES_* vars |
| `Dockerfile` | Remove SQLite mkdir and ENV |
| `alembic/env.py` | Make `render_as_batch` dialect-conditional |
| `alembic/versions/0002_custom_games.py` | Handle both SQLite and PostgreSQL in ALTER COLUMN |
| `alembic.ini` | Update placeholder URL comment |
| `app/database.py` | No changes (already correct) |
| `.github/workflows/docker.yml` | Verify and update if SQLite-specific references exist |
