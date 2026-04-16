"""Tests for Alembic migration chain: upgrade, downgrade, and idempotency."""
import logging

import sqlalchemy as sa
from alembic import command
from alembic.config import Config


def _alembic_cfg(db_url: str) -> Config:
    """Return an Alembic Config pointing at a given DB URL."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    logging.getLogger("alembic").setLevel(logging.WARNING)
    return cfg


def _table_names(db_url: str) -> set:
    """Connect to the DB and return the set of table names, then dispose."""
    engine = sa.create_engine(db_url)
    try:
        with engine.connect() as conn:
            inspector = sa.inspect(conn)
            return set(inspector.get_table_names())
    finally:
        engine.dispose()


def _sqlite_url(tmp_path) -> str:
    """Build a valid SQLite URL from a pytest tmp_path (forward-slash safe on Windows)."""
    posix = (tmp_path / "test.db").as_posix()
    return f"sqlite:///{posix}"


_EXPECTED_TABLES = {
    "users",
    "games",
    "scores",
    "invite_tokens",
    "feature_requests",
    "feature_comments",
    "game_ownerships",
    "alembic_version",
}


class TestMigrations:
    """Migration tests use real file-based SQLite so each run is independent.

    env.py unconditionally sets sqlalchemy.url from settings.DATABASE_URL, so
    we temporarily patch settings before every migration command.
    """

    @staticmethod
    def _run_upgrade(db_url: str) -> None:
        import app.config as _cfg_mod
        original = _cfg_mod.settings.DATABASE_URL
        _cfg_mod.settings.DATABASE_URL = db_url
        try:
            command.upgrade(_alembic_cfg(db_url), "head")
        finally:
            _cfg_mod.settings.DATABASE_URL = original

    @staticmethod
    def _run_downgrade(db_url: str) -> None:
        import app.config as _cfg_mod
        original = _cfg_mod.settings.DATABASE_URL
        _cfg_mod.settings.DATABASE_URL = db_url
        try:
            command.downgrade(_alembic_cfg(db_url), "base")
        finally:
            _cfg_mod.settings.DATABASE_URL = original

    def test_migration_chain_runs_clean(self, tmp_path):
        """Fresh DB: upgrade head creates all expected tables."""
        db_url = _sqlite_url(tmp_path)
        self._run_upgrade(db_url)
        tables = _table_names(db_url)
        assert _EXPECTED_TABLES.issubset(tables), (
            f"Missing tables: {_EXPECTED_TABLES - tables}"
        )

    def test_migration_downgrade(self, tmp_path):
        """Upgrade then downgrade base: all user tables should be removed."""
        db_url = _sqlite_url(tmp_path)
        self._run_upgrade(db_url)
        self._run_downgrade(db_url)
        tables = _table_names(db_url)
        user_tables = _EXPECTED_TABLES - {"alembic_version"}
        remaining = user_tables & tables
        assert not remaining, f"Tables still present after downgrade: {remaining}"

    def test_migration_idempotent(self, tmp_path):
        """Running upgrade twice should not re-apply migrations (no-op second time)."""
        db_url = _sqlite_url(tmp_path)
        self._run_upgrade(db_url)
        self._run_upgrade(db_url)  # must be a no-op
        tables = _table_names(db_url)
        assert _EXPECTED_TABLES.issubset(tables)
