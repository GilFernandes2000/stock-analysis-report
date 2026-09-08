"""The Alembic setup must build a schema from scratch and adopt a legacy DB."""

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text

import app.database as db
from app import models  # noqa: F401  (register models on Base.metadata)

EXPECTED_TABLES = {
    "api_cache",
    "users",
    "auth_sessions",
    "favorites",
    "portfolios",
    "reports",
    "transactions",
}


@pytest.fixture()
def sqlite_db(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'app.db'}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr("app.config.settings.database_url", url)
    return engine


def test_upgrade_head_builds_full_schema(sqlite_db):
    command.upgrade(db._alembic_config(), "head")

    insp = inspect(sqlite_db)
    tables = set(insp.get_table_names())
    assert EXPECTED_TABLES <= tables
    assert "alembic_version" in tables
    idx = {i["name"] for i in insp.get_indexes("transactions")}
    assert "ix_txn_portfolio_date" in idx


def test_upgrade_database_on_empty_db(sqlite_db):
    db.upgrade_database()
    assert EXPECTED_TABLES <= set(inspect(sqlite_db).get_table_names())


def test_upgrade_database_adopts_pre_alembic_db(sqlite_db):
    # A database created the old way: real tables, no alembic_version, and
    # (simulating an older schema) no favorites table.
    db.Base.metadata.create_all(bind=sqlite_db)
    with sqlite_db.begin() as conn:
        conn.execute(text("DROP TABLE favorites"))

    db.upgrade_database()

    tables = set(inspect(sqlite_db).get_table_names())
    assert "favorites" in tables  # re-created during adoption
    with sqlite_db.begin() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version is not None  # stamped at head

    # Idempotent: a second run is a no-op.
    db.upgrade_database()
