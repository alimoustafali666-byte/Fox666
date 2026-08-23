"""document_chunks embedding columns

Adds vector storage to document_chunks for the Step 10 retrieval engine.
No ANN index (ivfflat/hnsw) is added -- at pilot scale, an exact
sequential scan ordered by pgvector's `<=>` operator is simple, correct,
and fast enough; an approximate index is premature optimization until
real chunk volume justifies it (see the Step 10 report).

The `vector` Postgres extension is a prerequisite this migration does
NOT attempt to create itself: CREATE EXTENSION requires either
superuser or a database where it's already been installed (e.g. via
template1, so every future CREATE DATABASE inherits it) -- the
migration role (uae_app) deliberately has neither, the same reasoning
that already keeps it non-superuser everywhere else in this project
(see the Step 2 design notes on testing RLS as a genuine non-superuser
role). A clear, actionable error is raised up front instead of letting
this fail confusingly partway through an ALTER TABLE, or -- worse --
appear to succeed while silently storing something incompatible.

embedding_model is stored per chunk (not assumed from current config)
so a future model change is detectable rather than silently mixing
vector spaces -- see app.modules.documents.models.EMBEDDING_VECTOR_DIMENSION
and the retrieval service, which only ever compares chunks whose
embedding_model matches the currently configured one.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-21

"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Must match app.modules.documents.models.EMBEDDING_VECTOR_DIMENSION --
# the fixed schema-level dimension every configured embedding provider's
# `dimension` is validated against before any indexing is attempted.
# voyage-3's native output dimension, the Step 10 default provider/model.
EMBEDDING_VECTOR_DIMENSION = 1024


def upgrade() -> None:
    conn = op.get_bind()
    has_extension = conn.execute(
        sa.text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
    ).scalar()
    if not has_extension:
        raise RuntimeError(
            "The Postgres 'vector' extension (pgvector) is not installed in "
            "this database. A superuser must run `CREATE EXTENSION vector;` "
            "once (directly against this database, or against template1 so "
            "every future database inherits it) before this migration can "
            "proceed -- the migration role intentionally cannot do this "
            "itself. See README.md's Database setup section."
        )

    op.add_column(
        "document_chunks",
        sa.Column("embedding", Vector(EMBEDDING_VECTOR_DIMENSION), nullable=True),
    )
    op.add_column("document_chunks", sa.Column("embedding_model", sa.Text(), nullable=True))
    op.add_column(
        "document_chunks",
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_chunks", "embedded_at")
    op.drop_column("document_chunks", "embedding_model")
    op.drop_column("document_chunks", "embedding")

