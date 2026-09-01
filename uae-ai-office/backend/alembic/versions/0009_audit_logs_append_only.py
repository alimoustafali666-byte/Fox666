"""audit_logs: append-only enforcement

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-21

Two changes, both in service of "audit records are immutable through
normal application access":

1. audit_logs.company_id's foreign key changes from ON DELETE CASCADE to
   the default (RESTRICT-like NO ACTION). CASCADE was a quiet way for
   audit history to be destroyed as a *side effect* of an unrelated
   operation (deleting a company) rather than a deliberate action against
   audit_logs itself -- exactly the kind of indirect deletion path an
   append-only design should not have. There is no company-delete
   feature in Phase 1; if one is ever added, it will need to decide
   explicitly what happens to that company's audit trail rather than
   silently losing it.

2. REVOKE UPDATE, DELETE, TRUNCATE on audit_logs from the app role. There
   is no UPDATE/DELETE endpoint for audit logs and there never should be
   -- this makes that a database-enforced fact, not just an absence of
   routes.

   uae_app is both the table's owner and the role every migration runs
   as, so this is an accident-guard against normal application code (a
   stray UPDATE/DELETE statement, a future endpoint added carelessly),
   not a hard boundary against a fully compromised uae_app credential: as
   owner, it retains the right to grant the privilege back to itself at
   any time. A harder boundary would mean a second, non-owning "runtime"
   role distinct from the migration-owning role -- a real infrastructure
   change, deliberately not made here (see the Step 5 report for why: it
   would complicate every environment's setup for a guarantee this step
   doesn't require yet).

   Table ownership (and therefore the ability to run DDL migrations, e.g.
   ALTER TABLE) is unaffected: DDL rights come from ownership, not from
   GRANT-based DML privileges like UPDATE/DELETE/TRUNCATE. Only ordinary
   row-level UPDATE/DELETE statements (and TRUNCATE) are blocked.

   Discovered while implementing this: Postgres enforces a FOREIGN KEY's
   ON DELETE CASCADE action using the REFERENCING table's own grants, not
   the privileges of whoever issued the original DELETE on the
   referenced table (even a superuser) -- so leaving the CASCADE in place
   after the REVOKE below would have made deleting a company fail with a
   confusing "permission denied for table audit_logs" instead of a clear
   foreign-key error, for a statement that never mentions audit_logs at
   all. Change 1 above avoids that entirely rather than working around it.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("fk_audit_logs_company_id_companies", "audit_logs", type_="foreignkey")
    op.create_foreign_key(
        "fk_audit_logs_company_id_companies",
        "audit_logs",
        "companies",
        ["company_id"],
        ["id"],
    )

    # CURRENT_USER, not a hardcoded role name: the app role is `uae_app`
    # only in the local/dev setup this project's README describes. On a
    # managed provider it is whatever role the connection string uses
    # (`neondb_owner` on Neon, etc.). Naming a role that doesn't exist
    # makes the migration fail outright; skipping the REVOKE when it
    # doesn't exist silently drops the append-only guarantee this
    # migration exists to create. Revoking from CURRENT_USER -- which is
    # both the migration role and the runtime role by design, see the
    # module docstring -- is correct in every environment.
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON audit_logs FROM CURRENT_USER")


def downgrade() -> None:
    op.execute("GRANT UPDATE, DELETE, TRUNCATE ON audit_logs TO CURRENT_USER")

    op.drop_constraint("fk_audit_logs_company_id_companies", "audit_logs", type_="foreignkey")
    op.create_foreign_key(
        "fk_audit_logs_company_id_companies",
        "audit_logs",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="CASCADE",
    )

