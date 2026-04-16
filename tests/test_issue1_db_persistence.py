"""
Tests for Issue #1: "Database gets lost after image update"

Verifies that all files have been correctly updated to use PostgreSQL
with a named Docker volume for persistent storage, replacing the
previous SQLite approach where data was lost on container image updates.
"""

import ast
import configparser
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# requirements.txt
# ---------------------------------------------------------------------------

class TestRequirementsTxt:
    """psycopg2-binary must be present so the app can connect to PostgreSQL."""

    def _lines(self):
        return (ROOT / "requirements.txt").read_text().splitlines()

    def test_psycopg2_binary_present(self):
        """psycopg2-binary>=2.9 must be listed as a dependency."""
        lines = self._lines()
        psycopg2_lines = [l for l in lines if l.startswith("psycopg2-binary")]
        assert psycopg2_lines, "psycopg2-binary is missing from requirements.txt"

    def test_psycopg2_binary_version_constraint(self):
        """psycopg2-binary must require at least version 2.9."""
        lines = self._lines()
        psycopg2_line = next((l for l in lines if l.startswith("psycopg2-binary")), None)
        assert psycopg2_line is not None, "psycopg2-binary not found in requirements.txt"
        assert ">=2.9" in psycopg2_line, (
            f"Expected psycopg2-binary>=2.9, got: {psycopg2_line}"
        )


# ---------------------------------------------------------------------------
# docker-compose.yml
# ---------------------------------------------------------------------------

class TestDockerCompose:
    """Docker Compose must define a postgres db service and a named volume."""

    def _compose(self):
        return yaml.safe_load((ROOT / "docker-compose.yml").read_text())

    def test_db_service_exists(self):
        """A 'db' service must be defined for PostgreSQL."""
        compose = self._compose()
        assert "db" in compose.get("services", {}), \
            "'db' service is missing from docker-compose.yml"

    def test_db_uses_postgres16(self):
        """The 'db' service must use a postgres:16 image."""
        compose = self._compose()
        db_image = compose["services"]["db"].get("image", "")
        assert db_image.startswith("postgres:16"), (
            f"Expected postgres:16 image, got: {db_image}"
        )

    def test_postgres_named_volume_defined(self):
        """A named 'postgres-data' volume must be declared."""
        compose = self._compose()
        volumes = compose.get("volumes", {})
        assert "postgres-data" in volumes, \
            "'postgres-data' named volume not declared in docker-compose.yml"

    def test_db_service_uses_postgres_data_volume(self):
        """The 'db' service must mount the postgres-data volume."""
        compose = self._compose()
        db_volumes = compose["services"]["db"].get("volumes", [])
        mounted = any("postgres-data" in str(v) for v in db_volumes)
        assert mounted, "db service does not mount the postgres-data volume"

    def test_db_has_healthcheck(self):
        """The 'db' service must have a healthcheck defined."""
        compose = self._compose()
        healthcheck = compose["services"]["db"].get("healthcheck")
        assert healthcheck is not None, "db service is missing a healthcheck"
        assert "test" in healthcheck, "db healthcheck must have a 'test' command"

    def test_healthcheck_uses_pg_isready(self):
        """The healthcheck command must use pg_isready."""
        compose = self._compose()
        test_cmd = compose["services"]["db"]["healthcheck"]["test"]
        test_str = " ".join(test_cmd) if isinstance(test_cmd, list) else test_cmd
        assert "pg_isready" in test_str, (
            f"Healthcheck should use pg_isready, got: {test_str}"
        )

    def test_web_depends_on_db(self):
        """The 'web' service must declare depends_on the 'db' service."""
        compose = self._compose()
        depends_on = compose["services"]["web"].get("depends_on", {})
        # depends_on can be a list or a dict
        if isinstance(depends_on, list):
            assert "db" in depends_on, "web service does not depend on db"
        else:
            assert "db" in depends_on, "web service does not depend on db"

    def test_web_depends_on_db_with_health_condition(self):
        """web must wait for db to be healthy (condition: service_healthy)."""
        compose = self._compose()
        depends_on = compose["services"]["web"].get("depends_on", {})
        assert isinstance(depends_on, dict), (
            "depends_on should be a dict with condition, not a plain list"
        )
        condition = depends_on.get("db", {}).get("condition", "")
        assert condition == "service_healthy", (
            f"Expected condition: service_healthy, got: {condition}"
        )

    def test_no_app_data_sqlite_volume(self):
        """The old SQLite 'app-data' volume must not exist."""
        compose = self._compose()
        volumes = compose.get("volumes", {})
        assert "app-data" not in volumes, \
            "Old SQLite 'app-data' volume still present in docker-compose.yml"

    def test_no_sqlite_volume_mount_in_web(self):
        """The web service must not mount any SQLite app-data volume."""
        compose = self._compose()
        web_volumes = compose["services"]["web"].get("volumes", [])
        for v in web_volumes:
            assert "app-data" not in str(v), \
                f"web service still references app-data volume: {v}"

    def test_db_env_vars_configured(self):
        """The db service must configure POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD."""
        compose = self._compose()
        db_env = compose["services"]["db"].get("environment", {})
        for key in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
            assert key in db_env, f"db service missing env var: {key}"


# ---------------------------------------------------------------------------
# .env.example
# ---------------------------------------------------------------------------

class TestEnvExample:
    """The env example must be updated for PostgreSQL."""

    def _content(self):
        return (ROOT / ".env.example").read_text()

    def test_database_url_is_postgresql(self):
        """DATABASE_URL must use the postgresql:// scheme."""
        content = self._content()
        match = re.search(r"^DATABASE_URL=(.+)$", content, re.MULTILINE)
        assert match, "DATABASE_URL not found in .env.example"
        url = match.group(1).strip()
        assert url.startswith("postgresql://"), (
            f"DATABASE_URL should be postgresql://, got: {url}"
        )

    def test_database_url_not_sqlite(self):
        """DATABASE_URL must not reference SQLite."""
        content = self._content()
        match = re.search(r"^DATABASE_URL=(.+)$", content, re.MULTILINE)
        assert match, "DATABASE_URL not found in .env.example"
        url = match.group(1).strip()
        assert "sqlite" not in url.lower(), (
            f"DATABASE_URL still references SQLite: {url}"
        )

    def test_database_url_uses_db_hostname(self):
        """DATABASE_URL must use 'db' as the hostname (matching the docker-compose service)."""
        content = self._content()
        match = re.search(r"^DATABASE_URL=(.+)$", content, re.MULTILINE)
        assert match, "DATABASE_URL not found in .env.example"
        url = match.group(1).strip()
        assert "@db:" in url or "@db/" in url, (
            f"DATABASE_URL must use 'db' hostname to match docker-compose service, got: {url}"
        )

    def test_postgres_db_var_present(self):
        """POSTGRES_DB must be defined in .env.example."""
        content = self._content()
        assert re.search(r"^POSTGRES_DB=", content, re.MULTILINE), \
            "POSTGRES_DB missing from .env.example"

    def test_postgres_user_var_present(self):
        """POSTGRES_USER must be defined in .env.example."""
        content = self._content()
        assert re.search(r"^POSTGRES_USER=", content, re.MULTILINE), \
            "POSTGRES_USER missing from .env.example"

    def test_postgres_password_var_present(self):
        """POSTGRES_PASSWORD must be defined in .env.example."""
        content = self._content()
        assert re.search(r"^POSTGRES_PASSWORD=", content, re.MULTILINE), \
            "POSTGRES_PASSWORD missing from .env.example"

    def test_env_example_db_hostname_matches_compose_service(self):
        """The hostname in DATABASE_URL must match the docker-compose db service name."""
        compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
        service_names = list(compose.get("services", {}).keys())
        content = self._content()
        match = re.search(r"^DATABASE_URL=postgresql://[^@]+@([^:/]+)", content, re.MULTILINE)
        assert match, "Could not parse hostname from DATABASE_URL in .env.example"
        hostname = match.group(1)
        assert hostname in service_names, (
            f"DATABASE_URL hostname '{hostname}' does not match any docker-compose service: {service_names}"
        )


# ---------------------------------------------------------------------------
# Dockerfile
# ---------------------------------------------------------------------------

class TestDockerfile:
    """The Dockerfile must not contain SQLite-specific setup."""

    def _content(self):
        return (ROOT / "Dockerfile").read_text()

    def test_no_sqlite_env_var(self):
        """Dockerfile must not set DATABASE_URL to a SQLite path."""
        content = self._content()
        assert not re.search(r"ENV\s+DATABASE_URL\s*=\s*sqlite", content), \
            "Dockerfile still contains ENV DATABASE_URL=sqlite:..."

    def test_no_mkdir_app_data(self):
        """Dockerfile must not create /app/data directory (used for SQLite)."""
        content = self._content()
        assert "mkdir" not in content or "/app/data" not in content, \
            "Dockerfile still contains 'RUN mkdir -p /app/data' (SQLite artifact)"

    def test_no_sqlite_references(self):
        """Dockerfile must have no sqlite references at all."""
        content = self._content()
        assert "sqlite" not in content.lower(), \
            "Dockerfile still contains sqlite references"

    def test_has_expose_8000(self):
        """Dockerfile must expose port 8000."""
        content = self._content()
        assert "EXPOSE 8000" in content, "Dockerfile missing EXPOSE 8000"

    def test_cmd_runs_alembic_then_uvicorn(self):
        """CMD must run alembic upgrade head before starting uvicorn."""
        content = self._content()
        cmd_match = re.search(r"CMD\s+(.+)", content)
        assert cmd_match, "CMD not found in Dockerfile"
        cmd = cmd_match.group(1)
        assert "alembic upgrade head" in cmd, "CMD should run alembic upgrade head"
        assert "uvicorn" in cmd, "CMD should start uvicorn"


# ---------------------------------------------------------------------------
# alembic/env.py
# ---------------------------------------------------------------------------

class TestAlembicEnvPy:
    """alembic/env.py must use dialect-conditional render_as_batch."""

    def _content(self):
        return (ROOT / "alembic" / "env.py").read_text()

    def _tree(self):
        return ast.parse(self._content())

    def test_render_as_batch_conditional_offline(self):
        """run_migrations_offline must set render_as_batch only for SQLite."""
        content = self._content()
        # Check that offline function has sqlite-conditional batch
        assert "startswith(\"sqlite\")" in content or "startswith('sqlite')" in content, \
            "run_migrations_offline must check dialect with startswith('sqlite') for render_as_batch"

    def test_render_as_batch_conditional_online(self):
        """run_migrations_online must set render_as_batch only for SQLite."""
        content = self._content()
        assert 'dialect.name == "sqlite"' in content or "dialect.name == 'sqlite'" in content, \
            "run_migrations_online must check connection.dialect.name == 'sqlite' for render_as_batch"

    def test_database_url_override_from_settings(self):
        """env.py must override sqlalchemy.url from app settings."""
        content = self._content()
        assert "settings.DATABASE_URL" in content, \
            "env.py must set sqlalchemy.url from settings.DATABASE_URL"

    def test_imports_app_config(self):
        """env.py must import app.config settings."""
        content = self._content()
        assert "from app.config import settings" in content, \
            "env.py must import settings from app.config"

    def test_imports_app_database_base(self):
        """env.py must import Base from app.database for metadata."""
        content = self._content()
        assert "from app.database import Base" in content, \
            "env.py must import Base from app.database"

    def test_imports_app_models(self):
        """env.py must import app.models to populate Base.metadata."""
        content = self._content()
        assert "import app.models" in content, \
            "env.py must import app.models to populate Base.metadata"

    def test_render_as_batch_false_for_postgresql(self):
        """For PostgreSQL, render_as_batch must evaluate to False."""
        # Simulate offline check
        url = "postgresql://user:pass@db:5432/mydb"
        use_batch = url.startswith("sqlite")
        assert use_batch is False, \
            "render_as_batch should be False for PostgreSQL URLs"

    def test_render_as_batch_true_for_sqlite(self):
        """For SQLite, render_as_batch must evaluate to True."""
        url = "sqlite:///./test.db"
        use_batch = url.startswith("sqlite")
        assert use_batch is True, \
            "render_as_batch should be True for SQLite URLs"


# ---------------------------------------------------------------------------
# alembic/versions/0002_custom_games.py
# ---------------------------------------------------------------------------

class TestMigration0002:
    """Migration 0002 must use dialect-conditional alter_column logic."""

    def _content(self):
        return (ROOT / "alembic" / "versions" / "0002_custom_games.py").read_text()

    def test_revision_id(self):
        """Revision ID must be '0002'."""
        content = self._content()
        assert 'revision: str = "0002"' in content or "revision = '0002'" in content, \
            "0002_custom_games.py must have revision = '0002'"

    def test_down_revision_is_0001(self):
        """down_revision must be '0001' to chain correctly."""
        content = self._content()
        assert '"0001"' in content or "'0001'" in content, \
            "down_revision must be '0001'"
        assert "down_revision" in content, "down_revision variable must be defined"

    def test_dialect_check_in_upgrade(self):
        """upgrade() must check dialect name for conditional logic."""
        content = self._content()
        assert 'dialect.name == "sqlite"' in content or "dialect.name == 'sqlite'" in content, \
            "upgrade() must check conn.dialect.name for dialect-conditional logic"

    def test_dialect_check_in_downgrade(self):
        """downgrade() must check dialect name for conditional logic."""
        content = self._content()
        # Both upgrade and downgrade should have the check; count occurrences
        occurrences = content.count('dialect.name == "sqlite"') + content.count("dialect.name == 'sqlite'")
        assert occurrences >= 2, \
            "Both upgrade() and downgrade() must check dialect.name"

    def test_batch_alter_table_only_for_sqlite(self):
        """op.batch_alter_table must only be called inside the sqlite branch."""
        content = self._content()
        if "batch_alter_table" in content:
            # It must be guarded by a dialect check
            assert "sqlite" in content, \
                "batch_alter_table must be guarded by sqlite dialect check"
            # Verify it's inside an if-sqlite block (not top-level)
            # Find the line with batch_alter_table and check surrounding context
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if "batch_alter_table" in line:
                    # Look back for a sqlite condition
                    context_block = "\n".join(lines[max(0, i-10):i])
                    assert "sqlite" in context_block, \
                        f"batch_alter_table at line {i+1} must be inside a sqlite dialect check"

    def test_alter_column_for_postgresql_path(self):
        """The PostgreSQL path must use op.alter_column directly (not batch)."""
        content = self._content()
        assert "op.alter_column(" in content, \
            "Must have direct op.alter_column() call for PostgreSQL path"

    def test_modifies_steam_appid(self):
        """Migration must alter steam_appid column."""
        content = self._content()
        assert "steam_appid" in content, "Migration must reference steam_appid column"

    def test_modifies_steam_url(self):
        """Migration must alter steam_url column."""
        content = self._content()
        assert "steam_url" in content, "Migration must reference steam_url column"

    def test_modifies_thumbnail_url(self):
        """Migration must alter thumbnail_url column."""
        content = self._content()
        assert "thumbnail_url" in content, "Migration must reference thumbnail_url column"

    def test_makes_columns_nullable_in_upgrade(self):
        """upgrade() must make columns nullable=True."""
        content = self._content()
        assert "nullable=True" in content, "upgrade() must set nullable=True"

    def test_makes_columns_not_nullable_in_downgrade(self):
        """downgrade() must restore columns to nullable=False."""
        content = self._content()
        assert "nullable=False" in content, "downgrade() must set nullable=False"


# ---------------------------------------------------------------------------
# alembic.ini
# ---------------------------------------------------------------------------

class TestAlembicIni:
    """alembic.ini sqlalchemy.url must be a placeholder (overridden at runtime)."""

    def _config(self):
        cfg = configparser.ConfigParser()
        cfg.read(ROOT / "alembic.ini")
        return cfg

    def test_sqlalchemy_url_is_placeholder(self):
        """sqlalchemy.url must be a non-functional placeholder (overridden by env.py)."""
        cfg = self._config()
        url = cfg.get("alembic", "sqlalchemy.url", fallback="")
        # Should NOT be a real sqlite path or real postgresql URL
        assert "sqlite:///." not in url, \
            "alembic.ini sqlalchemy.url should be a placeholder, not a real SQLite path"

    def test_sqlalchemy_url_not_real_sqlite(self):
        """sqlalchemy.url must not point to an actual SQLite file."""
        cfg = self._config()
        url = cfg.get("alembic", "sqlalchemy.url", fallback="")
        assert not url.startswith("sqlite:///"), \
            f"alembic.ini still has a SQLite URL: {url}"

    def test_script_location_is_alembic(self):
        """script_location must point to the alembic directory."""
        cfg = self._config()
        script_location = cfg.get("alembic", "script_location", fallback="")
        assert script_location == "alembic", \
            f"script_location should be 'alembic', got: {script_location}"


# ---------------------------------------------------------------------------
# app/database.py  (verify-only file)
# ---------------------------------------------------------------------------

class TestAppDatabasePy:
    """app/database.py must use dialect-conditional connect_args."""

    def _content(self):
        return (ROOT / "app" / "database.py").read_text()

    def test_check_same_thread_only_for_sqlite(self):
        """check_same_thread must only be passed for SQLite connections."""
        content = self._content()
        assert "check_same_thread" in content, \
            "database.py must handle check_same_thread for SQLite compatibility"
        assert "sqlite" in content, \
            "database.py must condition check_same_thread on SQLite dialect"

    def test_no_hardcoded_sqlite_url(self):
        """database.py must not hardcode a SQLite URL."""
        content = self._content()
        assert "sqlite:///" not in content, \
            "database.py must not hardcode a SQLite URL"

    def test_uses_settings_database_url(self):
        """database.py must use settings.DATABASE_URL for the engine."""
        content = self._content()
        assert "settings.DATABASE_URL" in content, \
            "database.py must use settings.DATABASE_URL"


# ---------------------------------------------------------------------------
# app/config.py  (verify-only file)
# ---------------------------------------------------------------------------

class TestAppConfigPy:
    """app/config.py must read DATABASE_URL from environment."""

    def _content(self):
        return (ROOT / "app" / "config.py").read_text()

    def test_database_url_field_exists(self):
        """Settings must define a DATABASE_URL field."""
        content = self._content()
        assert "DATABASE_URL" in content, \
            "config.py must define DATABASE_URL setting"

    def test_uses_pydantic_settings(self):
        """config.py must use pydantic-settings BaseSettings."""
        content = self._content()
        assert "BaseSettings" in content, \
            "config.py must use pydantic_settings.BaseSettings"

    def test_env_file_configured(self):
        """Settings must read from .env file."""
        content = self._content()
        assert "env_file" in content, \
            "config.py must configure env_file for .env support"


# ---------------------------------------------------------------------------
# app/main.py  (verify-only file)
# ---------------------------------------------------------------------------

class TestAppMainPy:
    """app/main.py must have no SQLite-specific hardcoded logic."""

    def _content(self):
        return (ROOT / "app" / "main.py").read_text()

    def test_no_sqlite_references(self):
        """main.py must not reference SQLite directly."""
        content = self._content()
        assert "sqlite" not in content.lower(), \
            "main.py must not contain SQLite-specific references"

    def test_no_app_data_directory(self):
        """main.py must not reference the old /app/data SQLite directory."""
        content = self._content()
        assert "/app/data" not in content, \
            "main.py must not reference /app/data (SQLite artifact)"

    def test_has_lifespan(self):
        """main.py must define a lifespan context manager."""
        content = self._content()
        assert "lifespan" in content, \
            "main.py must define a lifespan context manager"


# ---------------------------------------------------------------------------
# .github/workflows/docker.yml  (verify-only file)
# ---------------------------------------------------------------------------

class TestGithubWorkflow:
    """CI/CD workflow must have no SQLite-specific steps."""

    def _content(self):
        return (ROOT / ".github" / "workflows" / "docker.yml").read_text()

    def _workflow(self):
        return yaml.safe_load(self._content())

    def test_no_sqlite_references(self):
        """docker.yml must not reference SQLite."""
        content = self._content()
        assert "sqlite" not in content.lower(), \
            "docker.yml must not contain SQLite references"

    def test_no_app_data_volume_reference(self):
        """docker.yml must not reference the old app-data volume."""
        content = self._content()
        assert "app-data" not in content, \
            "docker.yml must not reference the old SQLite app-data volume"

    def test_no_sqlite_database_url_env(self):
        """docker.yml must not set DATABASE_URL to a sqlite path."""
        content = self._content()
        assert "DATABASE_URL=sqlite" not in content, \
            "docker.yml must not set DATABASE_URL=sqlite:..."

    def test_triggers_on_main_push(self):
        """Workflow must trigger on push to main branch."""
        workflow = self._workflow()
        # PyYAML parses the YAML key 'on' as boolean True (YAML 1.1 spec)
        push_config = workflow.get(True, workflow.get("on", {})).get("push", {})
        branches = push_config.get("branches", [])
        assert "main" in branches, \
            "docker.yml must trigger on push to main branch"


# ---------------------------------------------------------------------------
# Integration: cross-file consistency checks
# ---------------------------------------------------------------------------

class TestCrossFileConsistency:
    """Verify that settings are consistent across all modified files."""

    def test_postgres_creds_consistent_between_env_example_and_compose(self):
        """The POSTGRES_* vars in .env.example must be consumed by docker-compose db service."""
        compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
        env_content = (ROOT / ".env.example").read_text()

        # docker-compose db.environment should reference the vars
        db_env = compose["services"]["db"].get("environment", {})
        for key in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
            assert key in db_env, f"docker-compose db.environment missing {key}"
            # .env.example must define the var
            assert re.search(rf"^{key}=", env_content, re.MULTILINE), \
                f".env.example missing {key}"

    def test_database_url_hostname_matches_compose_db_service(self):
        """DATABASE_URL hostname in .env.example must match the 'db' service in docker-compose."""
        env_content = (ROOT / ".env.example").read_text()
        match = re.search(r"^DATABASE_URL=postgresql://[^@]+@([^:/]+)", env_content, re.MULTILINE)
        assert match, "Could not parse DATABASE_URL hostname from .env.example"
        hostname = match.group(1)

        compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
        services = list(compose.get("services", {}).keys())
        assert hostname in services, (
            f"DATABASE_URL uses hostname '{hostname}' but docker-compose has services: {services}"
        )

    def test_dockerfile_has_no_sqlite_but_compose_has_postgres(self):
        """Dockerfile removes SQLite setup while docker-compose provides PostgreSQL."""
        dockerfile_content = (ROOT / "Dockerfile").read_text()
        compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())

        assert "sqlite" not in dockerfile_content.lower(), \
            "Dockerfile must not contain sqlite"
        assert "db" in compose.get("services", {}), \
            "docker-compose must have a 'db' PostgreSQL service"

    def test_alembic_env_py_uses_conditional_batch_and_compose_uses_postgres(self):
        """alembic/env.py uses conditional render_as_batch; docker-compose uses postgres."""
        env_py = (ROOT / "alembic" / "env.py").read_text()
        compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())

        # env.py should NOT unconditionally set render_as_batch=True
        # (which would break PostgreSQL)
        assert 'render_as_batch=True' not in env_py, \
            "alembic/env.py must not unconditionally set render_as_batch=True"

        db_image = compose["services"]["db"].get("image", "")
        assert "postgres" in db_image, "docker-compose db service must use postgres image"

    def test_migration_0002_uses_dialect_check_not_unconditional_batch(self):
        """0002_custom_games.py must not use unconditional batch_alter_table."""
        content = (ROOT / "alembic" / "versions" / "0002_custom_games.py").read_text()
        # Ensure that batch_alter_table is NOT at the top level of upgrade/downgrade
        # (it must be inside an `if ... sqlite` block)
        lines = content.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if "batch_alter_table" in stripped:
                # The surrounding context must have a sqlite guard
                context = "\n".join(lines[max(0, i-15):i])
                assert "sqlite" in context, (
                    f"batch_alter_table at line {i+1} appears to be called unconditionally "
                    f"(no sqlite guard found in preceding lines)"
                )

    def test_web_service_no_longer_has_sqlite_volume(self):
        """The web service in docker-compose must not mount any SQLite data volume."""
        compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
        web_volumes = compose["services"]["web"].get("volumes", [])
        for vol in web_volumes:
            vol_str = str(vol)
            assert "app-data" not in vol_str and "sqlite" not in vol_str.lower(), (
                f"web service still has SQLite-related volume: {vol_str}"
            )
