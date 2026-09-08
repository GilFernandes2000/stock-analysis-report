import logging
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

_ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _sql_literal(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _reconcile_columns() -> None:
    """Add columns that the models declare but an existing table is missing.

    A lightweight forward-only migration for the single-file SQLite database:
    ``create_all`` only creates missing *tables*, never alters existing ones, so
    a database created by an earlier schema keeps its old columns. This walks
    every mapped table and issues ``ALTER TABLE ... ADD COLUMN`` for anything
    absent. Idempotent and safe to run on every startup.
    """
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            present = {c["name"] for c in insp.get_columns(table.name)}
            for column in table.columns:
                if column.name in present:
                    continue
                coltype = column.type.compile(dialect=engine.dialect)
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {coltype}'
                # SQLite requires a default when adding a NOT NULL column; fall
                # back to a nullable column if we cannot derive a constant one.
                default = getattr(column.default, "arg", None)
                is_scalar_default = default is not None and not callable(default)
                if not column.nullable and is_scalar_default:
                    ddl += f" NOT NULL DEFAULT {_sql_literal(default)}"
                conn.execute(text(ddl))
                logger.info("Added missing column %s.%s", table.name, column.name)


def init_db() -> None:
    from app.models import (  # noqa: F401
        ApiCache,
        AuthSession,
        Favorite,
        Portfolio,
        Report,
        Transaction,
        User,
    )

    Base.metadata.create_all(bind=engine)
    _reconcile_columns()


def _alembic_config():
    from alembic.config import Config

    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def upgrade_database() -> None:
    """Bring the database schema up to date (run on app startup).

    - Fresh / empty database: ``alembic upgrade head`` builds everything.
    - Database that predates Alembic (has tables, no ``alembic_version``):
      adopt it with the legacy ``create_all`` + column reconcile, then stamp it
      at ``head`` so future migrations apply normally.
    - Already under Alembic: ``alembic upgrade head`` applies any new revisions.
    """
    from alembic import command

    cfg = _alembic_config()
    tables = set(inspect(engine).get_table_names())
    try:
        if tables and "alembic_version" not in tables:
            logger.info("Adopting pre-Alembic database; stamping at head")
            init_db()
            command.stamp(cfg, "head")
        else:
            command.upgrade(cfg, "head")
    except Exception:
        logger.exception("Alembic migration failed; falling back to create_all")
        init_db()
