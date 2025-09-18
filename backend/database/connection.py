"""Database connection and session management."""

import asyncio
from typing import Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
import logging

from config.settings import settings
from config.logging import get_logger

logger = get_logger(__name__)

# Create the declarative base
Base = declarative_base()

# Global engine and session maker
engine: Optional[create_async_engine] = None
AsyncSessionLocal: Optional[async_sessionmaker] = None


async def init_db():
    """Initialize database connection and create tables."""
    global engine, AsyncSessionLocal

    try:
        # Convert SQLite URL for async support if needed
        db_url = settings.DATABASE_URL
        if db_url.startswith("sqlite:///"):
            db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")

        # Create async engine
        engine = create_async_engine(
            db_url,
            echo=settings.DATABASE_ECHO,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args={"check_same_thread": False} if "sqlite" in db_url else {}
        )

        # Create session maker
        AsyncSessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Create tables
        async with engine.begin() as conn:
            # Import all models to ensure they're registered
            from .models import review_table, review_issue_table, webhook_delivery_table

            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialized successfully", database_url=db_url.split("@")[-1])

    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise


async def close_db():
    """Close database connection."""
    global engine

    if engine:
        await engine.dispose()
        logger.info("Database connection closed")


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for dependency injection."""
    if not AsyncSessionLocal:
        raise RuntimeError("Database not initialized")

    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_health() -> bool:
    """Check database health."""
    try:
        if not engine:
            return False

        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            return result.scalar() == 1

    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return False


class DatabaseManager:
    """Database manager for handling connections and sessions."""

    def __init__(self):
        self.engine = None
        self.session_maker = None

    async def connect(self, database_url: str = None):
        """Connect to database."""
        url = database_url or settings.DATABASE_URL

        # Convert SQLite URL for async support
        if url.startswith("sqlite:///"):
            url = url.replace("sqlite:///", "sqlite+aiosqlite:///")

        self.engine = create_async_engine(
            url,
            echo=settings.DATABASE_ECHO,
            pool_pre_ping=True
        )

        self.session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Test connection
        async with self.engine.begin() as conn:
            await conn.execute(text("SELECT 1"))

        logger.info("Database connected", url=url.split("@")[-1])

    async def disconnect(self):
        """Disconnect from database."""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.session_maker = None
            logger.info("Database disconnected")

    async def create_tables(self):
        """Create all database tables."""
        if not self.engine:
            raise RuntimeError("Database not connected")

        async with self.engine.begin() as conn:
            # Import models to register them
            from .models import review_table, review_issue_table, webhook_delivery_table

            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database tables created")

    async def drop_tables(self):
        """Drop all database tables (for testing)."""
        if not self.engine:
            raise RuntimeError("Database not connected")

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        logger.warning("Database tables dropped")

    async def get_session(self) -> AsyncSession:
        """Get a database session."""
        if not self.session_maker:
            raise RuntimeError("Database not connected")

        return self.session_maker()

    async def execute_raw_sql(self, sql: str, params: dict = None):
        """Execute raw SQL query."""
        if not self.engine:
            raise RuntimeError("Database not connected")

        async with self.engine.begin() as conn:
            result = await conn.execute(text(sql), params or {})
            return result


# Global database manager instance
db_manager = DatabaseManager()


# Migration support
class DatabaseMigrator:
    """Handle database migrations."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    async def get_current_version(self) -> int:
        """Get current database schema version."""
        try:
            async with self.db_manager.engine.begin() as conn:
                result = await conn.execute(
                    text("SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1")
                )
                row = result.fetchone()
                return row[0] if row else 0
        except Exception:
            # Schema version table doesn't exist, assume version 0
            return 0

    async def apply_migration(self, version: int, sql: str):
        """Apply a database migration."""
        async with self.db_manager.engine.begin() as conn:
            # Execute migration SQL
            await conn.execute(text(sql))

            # Record migration
            await conn.execute(
                text("""
                    INSERT INTO schema_version (version, applied_at)
                    VALUES (:version, :applied_at)
                """),
                {
                    "version": version,
                    "applied_at": "datetime('now')"
                }
            )

        logger.info(f"Applied database migration version {version}")

    async def run_migrations(self):
        """Run all pending migrations."""
        current_version = await self.get_current_version()
        migrations = self._get_migrations()

        for version, sql in migrations:
            if version > current_version:
                await self.apply_migration(version, sql)

    def _get_migrations(self) -> list:
        """Get list of migrations to apply."""
        return [
            (1, """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """),
            (2, """
                CREATE INDEX IF NOT EXISTS idx_reviews_repository ON reviews(repository);
                CREATE INDEX IF NOT EXISTS idx_reviews_status ON reviews(status);
                CREATE INDEX IF NOT EXISTS idx_reviews_created_at ON reviews(created_at);
            """),
            (3, """
                CREATE INDEX IF NOT EXISTS idx_review_issues_review_id ON review_issues(review_id);
                CREATE INDEX IF NOT EXISTS idx_review_issues_severity ON review_issues(severity);
                CREATE INDEX IF NOT EXISTS idx_review_issues_category ON review_issues(category);
            """),
        ]


# Utility functions
async def ensure_database_exists():
    """Ensure database and tables exist."""
    try:
        await init_db()
        return True
    except Exception as e:
        logger.error(f"Failed to ensure database exists: {str(e)}")
        return False


async def reset_database():
    """Reset database (for testing)."""
    if not settings.DEBUG:
        raise RuntimeError("Database reset only allowed in debug mode")

    global engine
    if engine:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    logger.warning("Database reset completed")


async def get_database_info() -> dict:
    """Get database information."""
    try:
        if not engine:
            return {"status": "not_connected"}

        async with engine.begin() as conn:
            # Get database version/info
            if "sqlite" in settings.DATABASE_URL:
                result = await conn.execute(text("SELECT sqlite_version()"))
                version = result.scalar()
                db_type = "SQLite"
            elif "postgresql" in settings.DATABASE_URL:
                result = await conn.execute(text("SELECT version()"))
                version = result.scalar()
                db_type = "PostgreSQL"
            else:
                version = "Unknown"
                db_type = "Unknown"

            # Get table count
            if "sqlite" in settings.DATABASE_URL:
                result = await conn.execute(
                    text("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                )
            else:
                result = await conn.execute(
                    text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")
                )

            table_count = result.scalar()

            return {
                "status": "connected",
                "type": db_type,
                "version": version,
                "table_count": table_count,
                "url": settings.DATABASE_URL.split("@")[-1]  # Hide credentials
            }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }