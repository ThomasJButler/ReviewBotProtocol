"""Async SQLAlchemy engine and session factory."""

from pathlib import Path
from typing import AsyncGenerator, List, Optional

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from config.logging import get_logger
from config.settings import settings

logger = get_logger(__name__)
Base = declarative_base()

engine = None
AsyncSessionLocal: Optional[async_sessionmaker] = None


BACKEND_DIR = Path(__file__).resolve().parents[1]


def _async_url(url: str) -> str:
    """Use the async SQLite driver and resolve a relative file path against
    the backend directory rather than whatever the working directory is."""
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////") and ":memory:" not in url:
        rel = url[len("sqlite:///"):]
        if rel.startswith("./"):
            rel = rel[2:]
        return f"sqlite+aiosqlite:///{(BACKEND_DIR / rel).resolve()}"
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return url


def database_path(database_url: Optional[str] = None) -> Optional[Path]:
    """The SQLite file the settings point at, or None for a non-file database."""
    url = _async_url(database_url or settings.DATABASE_URL)
    if url.startswith("sqlite+aiosqlite:///") and ":memory:" not in url:
        return Path(url[len("sqlite+aiosqlite:///"):])
    return None


async def init_db(database_url: Optional[str] = None) -> async_sessionmaker:
    global engine, AsyncSessionLocal
    url = _async_url(database_url or settings.DATABASE_URL)
    engine = create_async_engine(url, echo=settings.DATABASE_ECHO, pool_pre_ping=True,
                                 connect_args={"check_same_thread": False} if "sqlite" in url else {})
    if "sqlite" in url:
        @event.listens_for(engine.sync_engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _record):  # one writer at a time, readers never block
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=15000")
            cursor.close()
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        from . import models  # noqa: F401  registers tables
        await conn.run_sync(Base.metadata.create_all)
        added = await conn.run_sync(add_missing_columns)
        indexed = await conn.run_sync(add_missing_indexes)
    if added:
        logger.info("database columns added", columns=added)
    if indexed:
        logger.info("database indexes added", indexes=indexed)
    logger.info("database ready", url=url.split("@")[-1])
    return AsyncSessionLocal


def add_missing_columns(sync_conn) -> List[str]:
    """Columns the models declare that an existing database lacks are added in
    place (ALTER TABLE ADD COLUMN), so a schema that grows a column does not
    force anyone to delete their reviews.db. A scalar default travels with the
    column; a Python-side default (a callable) is applied by the ORM on insert,
    so such a column is added without NOT NULL, which SQLite could not add
    anyway. Existing rows read NULL there, which every reader treats as empty."""
    from sqlalchemy import inspect, text

    inspector = inspect(sync_conn)
    added: List[str] = []
    for table in Base.metadata.sorted_tables:
        if table.name not in inspector.get_table_names():
            continue
        present = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in present:
                continue
            quote = sync_conn.dialect.identifier_preparer.quote  # names come from the models, quoted anyway
            ddl = f"ALTER TABLE {quote(table.name)} ADD COLUMN {quote(column.name)} {column.type.compile(sync_conn.dialect)}"
            if column.default is not None and getattr(column.default, "is_scalar", False):
                value = column.default.arg
                ddl += f" DEFAULT {int(value) if isinstance(value, bool) else value!r}"
            sync_conn.execute(text(ddl))
            added.append(f"{table.name}.{column.name}")
    return added


def add_missing_indexes(sync_conn) -> List[str]:
    """Indexes the models declare that an existing table lacks are created in
    place; create_all only builds them with a new table. A unique index is
    skipped, with a warning naming the count, when the table already holds
    duplicate values, so a strange database still boots."""
    from sqlalchemy import inspect, text

    inspector = inspect(sync_conn)
    quote = sync_conn.dialect.identifier_preparer.quote
    created: List[str] = []
    for table in Base.metadata.sorted_tables:
        if table.name not in inspector.get_table_names():
            continue
        present = {ix["name"] for ix in inspector.get_indexes(table.name)}
        have = {c["name"] for c in inspector.get_columns(table.name)}
        for index in table.indexes:
            if index.name in present:
                continue
            columns = [c.name for c in index.columns]
            if not set(columns) <= have:
                continue  # add_missing_columns runs first; a column still missing has no index yet
            if index.unique:
                cols = ", ".join(quote(c) for c in columns)
                not_null = " AND ".join(f"{quote(c)} IS NOT NULL" for c in columns)
                dupes = sync_conn.execute(text(
                    f"SELECT COUNT(*) FROM (SELECT {cols} FROM {quote(table.name)} WHERE {not_null} "
                    f"GROUP BY {cols} HAVING COUNT(*) > 1)")).scalar_one()
                if dupes:
                    logger.warning("unique index skipped: the table holds duplicate values", table=table.name,
                                   index=index.name, duplicate_groups=dupes)
                    continue
            ddl = (f"CREATE {'UNIQUE ' if index.unique else ''}INDEX IF NOT EXISTS {quote(index.name)} "
                   f"ON {quote(table.name)} ({', '.join(quote(c) for c in columns)})")
            sync_conn.execute(text(ddl))
            created.append(index.name)
    return created


async def close_db() -> None:
    global engine
    if engine is not None:
        await engine.dispose()
        engine = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    if AsyncSessionLocal is None:
        raise RuntimeError("database not initialised")
    async with AsyncSessionLocal() as session:
        yield session


async def db_healthy() -> bool:
    if engine is None:
        return False
    try:
        async with engine.begin() as conn:
            return (await conn.execute(text("SELECT 1"))).scalar() == 1
    except Exception:
        return False
