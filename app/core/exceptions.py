"""Application exception hierarchy.

All custom exceptions inherit from :class:`AppError`.  Each exception carries
an HTTP status code and a human-readable message; the central exception
handler in :mod:`app.core.exception_handlers` converts them to the JSON
envelope expected by the mobile application:

::

    {
        "success": false,
        "message": "<error message>",
        "code": <http status>
    }

Using dedicated exception classes (instead of raising ``HTTPException``) keeps
the business logic decoupled from the web layer.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for every application-defined exception.

    Attributes:
        status_code: HTTP status code returned to the client.
        message: Human-readable error description.
    """

    #: Default HTTP status code (overridden by subclasses).
    status_code: int = 500

    #: Default error message.
    default_message: str = "Internal server error."

    def __init__(self, message: str | None = None, *, status_code: int | None = None) -> None:
        """Initialise the exception.

        Args:
            message: Optional override for :attr:`default_message`.
            status_code: Optional override for :attr:`status_code`.
        """
        self.message = message or self.default_message
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)

    def __repr__(self) -> str:  # pragma: no cover — debugging convenience
        return f"{type(self).__name__}(status_code={self.status_code}, message={self.message!r})"


# --------------------------------------------------------------------------- #
# Auth errors
# --------------------------------------------------------------------------- #
class AuthenticationError(AppError):
    """Raised when authentication credentials are missing or invalid."""

    status_code = 401
    default_message = "Authentication required."


class InvalidCredentialsError(AuthenticationError):
    """Raised when username / password do not match."""

    default_message = "incorrect username or password"


class UserNotFoundError(AuthenticationError):
    """Raised when the username cannot be located."""

    default_message = "username is not found"


class IncorrectUsernameError(AuthenticationError):
    """Raised when the username does not match the expected format."""

    default_message = "incorrect username"


class InvalidTokenError(AppError):
    """Raised when a JWT is missing, malformed or fails validation."""

    status_code = 401
    default_message = "not valid token"


# --------------------------------------------------------------------------- #
# Authorisation errors
# --------------------------------------------------------------------------- #
class AuthorizationError(AppError):
    """Raised when an authenticated user is not allowed to access a resource."""

    status_code = 403
    default_message = "forbidden"


# --------------------------------------------------------------------------- #
# Domain (business) errors — mirror the original ``App/Exception`` classes.
# --------------------------------------------------------------------------- #
class CustomerError(AppError):
    """Raised for business-rule violations related to a customer."""

    status_code = 400
    default_message = "customer error"


class ServiceError(AppError):
    """Raised for business-rule violations related to a service."""

    status_code = 400
    default_message = "service error"


class TariffError(AppError):
    """Raised for business-rule violations related to a tariff."""

    status_code = 400
    default_message = "tariff error"


class FeeError(AppError):
    """Raised for business-rule violations related to fees / transactions."""

    status_code = 400
    default_message = "fee error"


# --------------------------------------------------------------------------- #
# Generic HTTP-style errors
# --------------------------------------------------------------------------- #
class NotFoundError(AppError):
    """Raised when a referenced entity cannot be found."""

    status_code = 404
    default_message = "not found"


class ValidationError(AppError):
    """Raised for hand-rolled validation failures not covered by Pydantic."""

    status_code = 422
    default_message = "validation error"


class DatabaseError(AppError):
    """Raised when a database operation fails.

    The original exception is chained so it can be inspected by handlers
    or debug tooling.
    """

    status_code = 502
    default_message = "database error"

    def __init__(self, message: str | None = None, *, cause: BaseException | None = None) -> None:
        """Initialise the error.

        Args:
            message: Optional override for :attr:`default_message`.
            cause: The underlying DB exception (re-raised via ``__cause__``).
        """
        super().__init__(message)
        if cause is not None:
            self.__cause__ = cause


__all__ = [
    "AppError",
    "AuthenticationError",
    "InvalidCredentialsError",
    "UserNotFoundError",
    "IncorrectUsernameError",
    "InvalidTokenError",
    "AuthorizationError",
    "CustomerError",
    "ServiceError",
    "TariffError",
    "FeeError",
    "NotFoundError",
    "ValidationError",
    "DatabaseError",
]
