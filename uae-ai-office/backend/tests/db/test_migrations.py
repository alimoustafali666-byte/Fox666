import subprocess
import sys
import uuid
from pathlib import Path

from sqlalchemy import create_engine, text

ADMIN_DATABASE_URL = "postgresql+psycopg://uae_app:uae_app@localhost:5432/postgres"
BACKEND_DIR = Path(__file__).resolve().parents[2]

EXPECTED_TABLES = {
    "companies",
    "users",
    "company_members",
    "projects",
    "documents",
    "audit_logs",
    "document_chunks",
    "conversations",
    "messages",
    "message_citations",
    "daily_briefs",
    "brief_items",
}


def _run_alembic(*args: str, database_url: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        # DATABASE_DIRECT_URL is pinned to the SAME scratch database, not
        # left out. alembic/env.py migrates settings.migration_database_url,
        # which prefers DATABASE_DIRECT_URL -- and because this env is
        # scrubbed, an omitted variable is not "unset", it falls through to
        # whatever backend/.env holds. On a machine whose .env points at a
        # managed database that silently retargets every migration in this
        # test at production, where "upgrade head" is a no-op and the
        # following "downgrade base" would drop every table. Both variables
        # must name the scratch database for the target to be unambiguous.
        env={
            "PATH": "/usr/bin:/bin",
            "DATABASE_URL": database_url,
            "DATABASE_DIRECT_URL": database_url,
        },
        capture_output=True,
        text=True,
        check=False,
    )


def _table_names(db_url: str) -> set[str]:
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                )
            )
            return {row[0] for row in rows}
    finally:
        engine.dispose()


def test_migrations_apply_and_roll_back_cleanly() -> None:
    """Requirement 1 + 2: migrations apply from an empty database, and roll
    back cleanly, using a scratch database created and dropped just for
    this test so it never touches the shared dev/test database.
    """
    scratch_db = f"uae_ai_office_migtest_{uuid.uuid4().hex[:12]}"
    admin_engine = create_engine(ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{scratch_db}"'))

        scratch_url = (
            f"postgresql+psycopg://uae_app:uae_app@localhost:5432/{scratch_db}"
        )

        # 1. apply from empty
        result = _run_alembic("upgrade", "head", database_url=scratch_url)
        assert result.returncode == 0, result.stderr
        tables = _table_names(scratch_url)
        assert EXPECTED_TABLES.issubset(tables), tables

        # 2. roll back cleanly to base
        result = _run_alembic("downgrade", "base", database_url=scratch_url)
        assert result.returncode == 0, result.stderr
        tables_after_downgrade = _table_names(scratch_url)
        assert tables_after_downgrade.isdisjoint(EXPECTED_TABLES), tables_after_downgrade

        # re-upgrade proves the downgrade left the database in a state the
        # same migrations can cleanly re-apply to, not just an empty one
        result = _run_alembic("upgrade", "head", database_url=scratch_url)
        assert result.returncode == 0, result.stderr
        tables_after_reupgrade = _table_names(scratch_url)
        assert EXPECTED_TABLES.issubset(tables_after_reupgrade)
    finally:
        with admin_engine.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": scratch_db},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch_db}"'))
        admin_engine.dispose()

