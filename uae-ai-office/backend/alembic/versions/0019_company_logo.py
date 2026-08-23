"""add optional company logo columns

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-22

Step 20 -- company/tenant branding. Two nullable columns on `companies`:
`logo_storage_key` (the object-storage key, built exclusively by
app.core.storage.keys.build_company_logo_object_key -- never a raw
client-supplied path) and `logo_content_type` (the validated MIME type,
needed to serve the bytes back with a correct Content-Type). No RLS
change needed: `companies` has no RLS policy of its own (it's the tenant
root, not tenant-owned -- see tenancy/repository.py's
get_company_by_id docstring), and access to these two columns is gated
the same way every other company-root read already is: the caller must
already be an authenticated member of the company (get_tenant_context).
"""

from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("logo_storage_key", sa.Text(), nullable=True))
    op.add_column("companies", sa.Column("logo_content_type", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "logo_content_type")
    op.drop_column("companies", "logo_storage_key")

