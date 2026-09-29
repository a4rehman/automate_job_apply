import os
import ssl
from typing import AsyncGenerator, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.core.config import settings
from app.core.logging_config import logger


def get_effective_database_url() -> str:
    """
    Constructs the effective async database URL.
    Prefers explicit TiDB settings if provided, otherwise falls back to DATABASE_URL.
    """
    if settings.TIDB_HOST and settings.TIDB_USER:
        user = settings.TIDB_USER
        password = settings.TIDB_PASSWORD
        host = settings.TIDB_HOST
        port = settings.TIDB_PORT or 4000
        database = settings.TIDB_DATABASE or "job_automation"
        return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{database}"

    url = settings.DATABASE_URL
    if url.startswith("mysql://"):
        return url.replace("mysql://", "mysql+aiomysql://", 1)
    if url.startswith("mysql+pymysql://"):
        return url.replace("mysql+pymysql://", "mysql+aiomysql://", 1)
    # Supabase/Postgres: the dashboard and pooler hand out a plain
    # postgresql:// URL, but our async engine needs the asyncpg driver.
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


db_url = get_effective_database_url()
engine_kwargs: Dict[str, Any] = {
    "echo": False,
    "future": True,
}

connect_args: Dict[str, Any] = {}

if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    engine_kwargs["connect_args"] = connect_args
elif db_url.startswith("postgresql"):
    # Supabase / PostgreSQL. pool_pre_ping avoids handing out connections that
    # the pooler already closed; pool_recycle stays under the pooler idle limit.
    engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
    engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
    engine_kwargs["pool_recycle"] = settings.DB_POOL_RECYCLE
    engine_kwargs["pool_pre_ping"] = True
    if settings.DB_SSL_MODE:
        # asyncpg honours sslmode; "require" is Supabase's default posture.
        engine_kwargs["connect_args"] = {"ssl": settings.DB_SSL_MODE}
else:
    # TiDB / MySQL connection tuning
    engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
    engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
    engine_kwargs["pool_recycle"] = settings.DB_POOL_RECYCLE
    engine_kwargs["pool_pre_ping"] = True

    # TiDB Cloud SSL context setup
    ssl_context = ssl.create_default_context()
    if settings.TIDB_CA_PATH and os.path.exists(settings.TIDB_CA_PATH):
        ssl_context.load_verify_locations(cafile=settings.TIDB_CA_PATH)
    connect_args["ssl"] = ssl_context
    engine_kwargs["connect_args"] = connect_args

engine = create_async_engine(db_url, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    """Initializes database schema and verifies connectivity."""
    # Models must be imported before create_all, otherwise Base.metadata is
    # empty and create_all silently creates NO tables at all.
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info(f"Database schema initialized on engine: {engine.url.drivername}")


# -----------------------------------------------------------------------------
# Schema migrations
# -----------------------------------------------------------------------------
# `create_all` only creates tables that do not exist yet; it can never add a
# column to a table that was created by an earlier release. On a hosted
# Postgres (Supabase) database that means new columns silently never appear.
#
# Each migration is idempotent and recorded in schema_migrations so it is
# applied exactly once. Column additions are introspected first rather than
# relying on `ADD COLUMN IF NOT EXISTS`, which SQLite does not support.
COLUMN_MIGRATIONS = [
    ("0001_job_matches_match_reasons", "job_matches", "match_reasons", "JSON"),
    ("0002_job_matches_confidence", "job_matches", "confidence", "FLOAT DEFAULT 0"),
]

INDEX_MIGRATIONS = [
    (
        "0003_scheduler_runs_run_id_unique",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_scheduler_runs_run_id ON scheduler_runs (run_id)",
    ),
    (
        "0004_applications_user_job_unique",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_applications_user_job ON applications (user_id, job_id)",
    ),
    (
        "0005_job_matches_job_user_unique",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_job_matches_job_user ON job_matches (job_id, user_id)",
    ),
    (
        "0006_jobs_description_hash_unique",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_jobs_description_hash ON jobs (description_hash)",
    ),
    (
        "0007_jobs_source_external_partial_unique",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_jobs_source_external "
        "ON jobs (source_name, external_job_id) WHERE external_job_id != ''",
    ),
]


async def run_migrations() -> int:
    """Apply pending schema migrations. Returns the number applied."""
    from sqlalchemy import inspect

    applied = 0
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "  version VARCHAR(255) PRIMARY KEY,"
                "  applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
        )
        result = await conn.execute(text("SELECT version FROM schema_migrations"))
        done = {row[0] for row in result.fetchall()}

        async def mark(version: str) -> None:
            await conn.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:v)"),
                {"v": version},
            )

        try:
            for version, table, column, coltype in COLUMN_MIGRATIONS:
                if version in done:
                    continue
                existing = await conn.run_sync(
                    lambda c: {col["name"] for col in inspect(c).get_columns(table)}
                )
                if column in existing:
                    await mark(version)
                    continue
                await conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
                )
                await mark(version)
                applied += 1
                logger.info(f"Applied migration {version} (added {table}.{column})")

            for version, sql in INDEX_MIGRATIONS:
                if version in done:
                    continue
                await conn.execute(text(sql))
                await mark(version)
                applied += 1
                logger.info(f"Applied migration {version}")
        except Exception as e:
            # A failed migration must abort rather than leave a half-applied
            # schema; the surrounding transaction rolls back.
            logger.error(f"Migration failed: {e}")
            raise
    if applied:
        logger.info(f"Applied {applied} schema migration(s)")
    return applied


async def init_db_with_migrations():
    """Production entry point: create tables, then bring them up to date."""
    await init_db()
    await run_migrations()


async def ping_database() -> bool:
    """Verifies that the persistent database connection is active."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database ping failed: {e}")
        return False

