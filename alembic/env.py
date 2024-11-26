from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

import os
import sys


sys.path.append(os.path.join(sys.path[0], 'app'))

from alembic import context
from app.config import PG_USER, PG_PASSWORD, PG_DB, DB_PORT, DB_HOST
from app.models.models import Base as models_base
from app.models.users import Base as users_base
config = context.config

section = config.config_ini_section
config.set_section_option(section, "PG_DB", str(PG_DB))
config.set_section_option(section, "DB_PORT", str(DB_PORT))
config.set_section_option(section, "PG_USER", str(PG_USER))
config.set_section_option(section, "PG_PASSWORD", str(PG_PASSWORD))
config.set_section_option(section, "DB_HOST", str(DB_HOST))





# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = [models_base.metadata, users_base.metadata]

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
