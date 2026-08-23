"""add self-lookup RLS policy to company_members

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-21

Login/signup need to discover "which companies does this user belong to"
*before* an active company (and therefore a company context) has been
chosen -- that's exactly the question this query answers, so it can't
already know the company_id to scope by. The existing tenant_isolation
policy can't help here: with no company context set, it hides every row,
including the user's own.

This adds a second, narrow PERMISSIVE policy: a user may always see their
own company_members rows, identified by a separate app.current_user_id
session variable (set explicitly by the auth module right after password
verification -- see app/db/session.py:set_user_context). PERMISSIVE
policies on the same table/command combine with OR, so a row is visible
if EITHER the normal company-scoped check passes OR this self-lookup
check does. It's scoped to SELECT only, so it grants no ability to
insert/update/delete membership rows outside the existing tenant-scoped
policy, and it only affects company_members -- projects, documents, and
audit_logs are untouched.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SELF_LOOKUP_EXPR = "user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid"


def upgrade() -> None:
    op.execute(
        f"CREATE POLICY self_membership_lookup ON company_members "
        f"FOR SELECT USING ({SELF_LOOKUP_EXPR})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY self_membership_lookup ON company_members")

