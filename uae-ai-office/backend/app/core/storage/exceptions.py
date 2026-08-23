"""Typed storage exceptions. Deliberately NOT app.core.exceptions.AppError
subclasses -- that base is for exceptions a FastAPI router raises directly
to produce an HTTP response. These are a lower-level infrastructure
concern: the future Documents service (Step 8) will catch these and
decide what, if anything, becomes an HTTP error, in the same way it
decides what a SQLAlchemy error becomes.

Messages are always fixed and generic, never built from a raw vendor
SDK exception's string representation -- botocore error text can
legitimately include request identifiers and bucket/key names, and
while it should never include credentials themselves (those are sent as
a signature, not echoed back), the discipline here is "don't take the
risk": construct our own safe message, chain the original exception via
`from exc` for server-side debugging only, never surface it further.
"""


class StorageError(Exception):
    pass


class StorageUnavailable(StorageError):
    """Transient: connection/timeout/5xx-shaped failure. The caller may
    reasonably retry the whole operation later.
    """


class ObjectNotFoundError(StorageError):
    pass


class StorageConfigurationError(StorageError):
    """Required configuration is missing or invalid for the selected
    provider. Raised eagerly, at provider-construction time, rather than
    surfacing as a confusing failure on first use.
    """


class StorageOperationError(StorageError):
    """Catch-all for a provider-reported failure that isn't one of the
    more specific categories above (e.g. an unexpected 4xx that isn't
    "not found").
    """


class InvalidObjectKeyError(StorageError):
    """A requested object key/key component doesn't meet the safety
    requirements enforced by app.core.storage.keys -- see that module.
    """

