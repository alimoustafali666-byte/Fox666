"""Import this FIRST, before anything else in this package that
transitively imports `app.*` -- `app.core.config.Settings()` is
constructed at import time and requires JWT_SECRET_KEY with no default
(deliberately, per Step 1: an accidentally-deployed default signing
secret would be a real vulnerability). The evaluation harness never
issues real tokens anyone relies on, so a fresh random secret per run is
correct and safe -- this is the same reasoning tests/conftest.py's own
JWT_SECRET_KEY env var (set by the test runner invocation) already
relies on, just generated in-process here instead of by the caller.

evaluation/run.py imports this module first, before any other import;
every other evaluation/ module assumes this has already run by the time
it imports anything from `app`.
"""

import os
import secrets

os.environ.setdefault("JWT_SECRET_KEY", secrets.token_hex(32))
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("APP_ENV", "evaluation")

