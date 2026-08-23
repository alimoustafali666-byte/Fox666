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
config.set_main_option("sqlalchemy.url", settings.database_url)

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

