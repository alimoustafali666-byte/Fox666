"""documents processing prep

Adds what document_chunks (the next migration) needs to reference
documents safely, plus a place to record a safe, bounded processing
failure reason:

- uq_documents_id_company: a composite UNIQUE(id, company_id), mirroring
  uq_projects_id_company. Postgres requires the referenced side of a
  composite foreign key to be backed by a unique constraint on exactly
  those columns; document_chunks(document_id, company_id) will reference
  this one, the same way documents(project_id, company_id) already
  references uq_projects_id_company.
- processing_error_code / processing_error_message: nullable, bounded
  text. Never a raw parser/vendor stack trace -- see
  app.modules.documents.processing_errors for the closed set of codes
  and the length cap applied before anything is written here.

document_type/status stay exactly as they are: status is already plain
TEXT (Step 2's design note: new values like 'processing'/'failed' need
no migration), so only the two new nullable columns and the unique
constraint are added here.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-21

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint("uq_documents_id_company", "documents", ["id", "company_id"])
    op.add_column("documents", sa.Column("processing_error_code", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("processing_error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "processing_error_message")
    op.drop_column("documents", "processing_error_code")
    op.drop_constraint("uq_documents_id_company", "documents", type_="unique")

