import asyncio
import os
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import async_engine_from_config, create_async_engine
from sqlalchemy import pool

from alembic import context

# Import all models BEFORE setting target_metadata.
# Without these imports, Alembic sees no tables and generates an empty migration. (Pitfall 5)
import app.models  # noqa: F401 — registers all 6 models with Base.metadata
from app.models.base import Base

# Alembic Config object — provides access to alembic.ini values
config = context.config

# Interpret the config file for Python logging (if present)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata — Alembic diffs against this to generate migrations
target_metadata = Base.metadata

# Override sqlalchemy.url from environment variable (DATABASE_URL).
# asyncpg does not accept sslmode=require as a URL query param — strip it and
# pass ssl=True via connect_args instead. (Pitfall: asyncpg SSL handling)
database_url = os.environ.get("DATABASE_URL")
if database_url:
    # Strip ?sslmode=require (or &sslmode=require) — asyncpg uses ssl kwarg instead
    database_url = database_url.replace("?sslmode=require", "").replace("&sslmode=require", "")
    config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL without a DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using an async engine."""
    # Pass ssl=True via connect_args for Neon (asyncpg does not support sslmode= in URL)
    connect_args = {}
    if os.environ.get("DATABASE_URL", "").find("neon.tech") != -1:
        connect_args["ssl"] = True

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Entry point for online migration mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
