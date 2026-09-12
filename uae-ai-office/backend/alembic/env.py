import re
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import settings

# Import every module's models so Base.metadata is fully populated (used
# only if autogenerate is ever run; Phase 1 migrations are hand-written).
from app.db.base import Base
from app.modules.audit_log import models as audit_log_models  # noqa: F401
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.collaboration import models as collaboration_models  # noqa: F401
from app.modules.documents import models as documents_models  # noqa: F401
from app.modules.projects import models as projects_models  # noqa: F401
from app.modules.support import models as support_models  # noqa: F401
from app.modules.tasks import models as tasks_models  # noqa: F401
from app.modules.tenancy import models as tenancy_models  # noqa: F401

config = context.config
# Migrations deliberately use settings.migration_database_url, not
# settings.database_url: on a provider with a connection pooler in front
# of the database (Neon, Supabase, RDS Proxy) the runtime DSN points at
# the POOLED endpoint, and transaction-mode pooling does not guarantee
# the session continuity that transactional DDL, advisory locks and
# SET LOCAL depend on. With DATABASE_DIRECT_URL unset this resolves back
# to database_url, which is correct for a single-endpoint Postgres.
_migration_url = settings.migration_database_url
config.set_main_option("sqlalchemy.url", _migration_url)

# Announce the target before doing anything to it. A migration run that
# silently picks the wrong database is the most expensive mistake this
# file can make -- the tests that exercise Alembic scrub their
# environment, and an omitted variable there falls through to whatever
# backend/.env holds rather than being unset. Printing the resolved host
# and database (never the credentials) makes a mistargeted run obvious in
# the output instead of something you reconstruct afterwards from damage.
_masked = re.sub(r"://[^@/]*@", "://***@", _migration_url)
print(f"alembic: migrating {_masked}", file=sys.stderr)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
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
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

