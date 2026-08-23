"""documents indexing state

A separate lifecycle from documents.status (processing): a document can
be fully `processed` (text extracted, chunked) while still being
`not_indexed` (no embeddings yet, not retrievable). Kept as its own set
of columns rather than overloading `status`/`processing_error_*` -- the
two lifecycles fail independently (a processed document's chunks might
embed fine while its extraction had nothing to do with indexing, and
vice versa is meaningless but the reverse failure mode -- reprocessing
invalidating existing embeddings -- is exactly why these need to be
distinguishable states; see processing_orchestrator.py's post-Step-10
reset-on-reprocess behavior).

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-21

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("indexing_status", sa.Text(), nullable=False, server_default="not_indexed"),
    )
    op.add_column("documents", sa.Column("indexing_error_code", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("indexing_error_message", sa.Text(), nullable=True))
    op.add_column(
        "documents", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("documents", "indexed_at")
    op.drop_column("documents", "indexing_error_message")
    op.drop_column("documents", "indexing_error_code")
    op.drop_column("documents", "indexing_status")

