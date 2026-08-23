"""The approved Phase 1 role set, most to least privileged.

Documented here as a fact any future code can reference (e.g. "is X more
senior than Y"). require_roles() in app.modules.auth.dependencies
deliberately does NOT use this to auto-expand a role into everything
below it -- every endpoint states its own explicit allowed-role list, so
a new sensitive action never silently inherits access just because a
role happens to outrank another in this ordering.
"""

ROLE_HIERARCHY: tuple[str, ...] = ("owner", "admin", "manager", "member")

