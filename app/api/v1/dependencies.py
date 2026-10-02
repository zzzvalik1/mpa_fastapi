"""FastAPI dependencies shared by the v1 endpoints.

Three categories are exposed:

* **Auth dependencies** — ``current_uid`` (required JWT) and ``optional_uid``
  (best-effort JWT, used by ``/subscriber/shop``).
* **Service factories** — FastAPI ``Depends`` callables that build the
  per-request service objects (``AuthService``, ``CustomerService``, ...).
* **Request context** — ``client_ip`` dependency that extracts the caller IP
  for audit logging.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.exceptions import InvalidTokenError as AppInvalidTokenError
from app.core.security import decode_token
from app.db.dependencies import get_db, get_db_client, get_db_lk
from app.repositories.customer_repository import CustomerRepository
from app.repositories.fee_repository import FeeRepository
from app.repositories.lklog_repository import LkLogRepository
from app.repositories.service_repository import ServiceRepository
from app.repositories.tariff_repository import TariffRepository
from app.repositories.webclientlog_repository import WebClientLogRepository
from app.services.auth_service import AuthService
from app.services.customer_service import CustomerService
from app.services.fee_service import FeeService
from app.services.mailer_client import MailerClient
from app.services.message_service import MessageService
from app.services.push_client import PushClient
from app.services.push_service import PushService
from app.services.service_service import ServiceService
from app.services.tariff_service import TariffService


# --------------------------------------------------------------------------- #
# DB sessions
# --------------------------------------------------------------------------- #
DbSession = Annotated[Session, Depends(get_db)]
DbClientSession = Annotated[Session, Depends(get_db_client)]
DbLkSession = Annotated[Session, Depends(get_db_lk)]


# --------------------------------------------------------------------------- #
# Client IP
# --------------------------------------------------------------------------- #
def client_ip(request: Request) -> str:
    """Return the IP address of the calling client.

    Honours the ``X-Forwarded-For`` header (first hop) when present so the
    audit log shows the real client IP behind a reverse proxy.

    Args:
        request: The incoming Starlette :class:`Request`.

    Returns:
        The client IP as a string.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


ClientIp = Annotated[str, Depends(client_ip)]


# --------------------------------------------------------------------------- #
# Auth dependencies
# --------------------------------------------------------------------------- #
def _extract_bearer(authorization: str | None) -> str:
    """Return the raw token from an ``Authorization: Bearer <token>`` header.

    Args:
        authorization: The raw header value (may be ``None``).

    Returns:
        The token string.

    Raises:
        AppInvalidTokenError: If the header is missing or malformed.
    """
    if not authorization:
        raise AppInvalidTokenError("missing Authorization header")
    if not authorization.lower().startswith("bearer "):
        raise AppInvalidTokenError("empty Bearer token")
    token = authorization[7:].strip()
    if not token:
        raise AppInvalidTokenError("empty Bearer token")
    return token


def current_uid(authorization: Annotated[str | None, Header()] = None) -> int:
    """Return the authenticated user's id (required JWT).

    Args:
        authorization: The ``Authorization`` header.

    Returns:
        The user id (``uid``).

    Raises:
        AppInvalidTokenError: If the token is missing / invalid / expired.
    """
    token = _extract_bearer(authorization)
    decoded = decode_token(token)
    return decoded.uid


def optional_uid(authorization: Annotated[str | None, Header()] = None) -> int | None:
    """Return the authenticated user's id, or ``None`` if no token is present.

    Used by endpoints that accept both authenticated and anonymous requests
    (e.g. ``POST /subscriber/shop``).

    Args:
        authorization: The ``Authorization`` header (optional).

    Returns:
        The user id, or ``None``.
    """
    if not authorization:
        return None
    try:
        return current_uid(authorization=authorization)
    except AppInvalidTokenError:
        return None


CurrentUid = Annotated[int, Depends(current_uid)]
OptionalUid = Annotated[int | None, Depends(optional_uid)]


# --------------------------------------------------------------------------- #
# Service factories
# --------------------------------------------------------------------------- #
def auth_service(db: DbSession) -> AuthService:
    """Build an :class:`AuthService` for the current request.

    Args:
        db: Main-DB session.

    Returns:
        A new :class:`AuthService` instance.
    """
    return AuthService(customer_repo=CustomerRepository(db))


def customer_service(
    db: DbSession,
    db_client: DbClientSession,
    db_lk: DbLkSession,
    ip: ClientIp,
) -> CustomerService:
    """Build a :class:`CustomerService` for the current request.

    Args:
        db: Main-DB session.
        db_client: Webclient-log DB session.
        db_lk: LK-log DB session.
        ip: Caller IP.

    Returns:
        A new :class:`CustomerService` instance.
    """
    return CustomerService(
        customer_repo=CustomerRepository(db),
        service_repo=ServiceRepository(db),
        tariff_repo=TariffRepository(db),
        fee_repo=FeeRepository(db),
        lklog_repo=LkLogRepository(db_lk),
        webclientlog_repo=WebClientLogRepository(db_client),
        client_ip=ip,
    )


def service_service(
    db: DbSession,
    db_client: DbClientSession,
    db_lk: DbLkSession,
    ip: ClientIp,
) -> ServiceService:
    """Build a :class:`ServiceService` for the current request."""
    return ServiceService(
        customer_repo=CustomerRepository(db),
        service_repo=ServiceRepository(db),
        tariff_repo=TariffRepository(db),
        fee_repo=FeeRepository(db),
        lklog_repo=LkLogRepository(db_lk),
        webclientlog_repo=WebClientLogRepository(db_client),
        mailer=MailerClient(),
        client_ip=ip,
    )


def tariff_service(
    db: DbSession,
    db_client: DbClientSession,
    db_lk: DbLkSession,
    ip: ClientIp,
) -> TariffService:
    """Build a :class:`TariffService` for the current request."""
    return TariffService(
        customer_repo=CustomerRepository(db),
        service_repo=ServiceRepository(db),
        tariff_repo=TariffRepository(db),
        fee_repo=FeeRepository(db),
        lklog_repo=LkLogRepository(db_lk),
        webclientlog_repo=WebClientLogRepository(db_client),
        client_ip=ip,
    )


def fee_service(
    db: DbSession,
    db_client: DbClientSession,
    db_lk: DbLkSession,
    ip: ClientIp,
) -> FeeService:
    """Build a :class:`FeeService` for the current request."""
    return FeeService(
        customer_repo=CustomerRepository(db),
        service_repo=ServiceRepository(db),
        tariff_repo=TariffRepository(db),
        fee_repo=FeeRepository(db),
        lklog_repo=LkLogRepository(db_lk),
        webclientlog_repo=WebClientLogRepository(db_client),
        client_ip=ip,
    )


def message_service(
    db: DbSession,
    db_client: DbClientSession,
    db_lk: DbLkSession,
    ip: ClientIp,
) -> MessageService:
    """Build a :class:`MessageService` for the current request."""
    return MessageService(
        customer_repo=CustomerRepository(db),
        service_repo=ServiceRepository(db),
        tariff_repo=TariffRepository(db),
        fee_repo=FeeRepository(db),
        lklog_repo=LkLogRepository(db_lk),
        webclientlog_repo=WebClientLogRepository(db_client),
        mailer=MailerClient(),
        client_ip=ip,
    )


def push_service(db: DbSession) -> PushService:
    """Build a :class:`PushService` for the current request."""
    return PushService(push_repo=PushRepository(db), push_client=PushClient())


# Re-exported Annotated aliases for ergonomic endpoint signatures.
AuthServiceDep = Annotated[AuthService, Depends(auth_service)]
CustomerServiceDep = Annotated[CustomerService, Depends(customer_service)]
ServiceServiceDep = Annotated[ServiceService, Depends(service_service)]
TariffServiceDep = Annotated[TariffService, Depends(tariff_service)]
FeeServiceDep = Annotated[FeeService, Depends(fee_service)]
MessageServiceDep = Annotated[MessageService, Depends(message_service)]
PushServiceDep = Annotated[PushService, Depends(push_service)]


__all__ = [
    # Sessions / IP
    "DbSession",
    "DbClientSession",
    "DbLkSession",
    "ClientIp",
    # Auth
    "current_uid",
    "optional_uid",
    "CurrentUid",
    "OptionalUid",
    # Factories
    "auth_service",
    "customer_service",
    "service_service",
    "tariff_service",
    "fee_service",
    "message_service",
    "push_service",
    # Annotated aliases
    "AuthServiceDep",
    "CustomerServiceDep",
    "ServiceServiceDep",
    "TariffServiceDep",
    "FeeServiceDep",
    "MessageServiceDep",
    "PushServiceDep",
]
