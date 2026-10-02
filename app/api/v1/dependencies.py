"""FastAPI-зависимости, общие для v1 эндпоинтов.

Доступны три категории:

* **Auth-зависимости** — ``current_uid`` (обязательный JWT) и ``optional_uid``
  (best-effort JWT, используется ``/subscriber/shop``).
* **Фабрики сервисов** — FastAPI-вызовы ``Depends``, создающие объекты
  сервисов на каждый запрос (``AuthService``, ``CustomerService``, ...).
* **Контекст запроса** — зависимость ``client_ip``, извлекающая IP
  вызывающей стороны для аудит-логирования.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
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
# Security scheme — позволяет Swagger UI показывать кнопку "Authorize" (🔒)
# и автоматически добавлять заголовок Authorization: Bearer <token> во все
# защищённые эндпоинты.
# --------------------------------------------------------------------------- #
# auto_error=False — мы хотим сами обрабатывать отсутствие токена
# (чтобы выбрасывать наше кастомное AppError, а не дефолтный 403 от FastAPI).
bearer_scheme = HTTPBearer(auto_error=False)


# --------------------------------------------------------------------------- #
# Client IP
# --------------------------------------------------------------------------- #
def client_ip(request: Request) -> str:
    """Вернуть IP-адрес вызывающего клиента.

    Учитывает заголовок ``X-Forwarded-For`` (первый хоп), если он присутствует,
    чтобы аудит-лог отображал реальный IP клиента за обратным прокси.

    Args:
        request: Входящий Starlette-запрос :class:`Request`.

    Returns:
        IP-адрес клиента в виде строки.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


ClientIp = Annotated[str, Depends(client_ip)]


# --------------------------------------------------------------------------- #
# Auth dependencies
# --------------------------------------------------------------------------- #
def current_uid(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> int:
    """Вернуть id аутентифицированного пользователя (обязательный JWT).

    Использует :class:`HTTPBearer` security scheme, поэтому Swagger UI
    автоматически показывает кнопку **Authorize** и отправляет заголовок
    ``Authorization: Bearer <token>``.

    Args:
        credentials: Учётные данные из заголовка (scheme + token).

    Returns:
        id пользователя (``uid``).

    Raises:
        AppInvalidTokenError: Если токен отсутствует / недействителен / истёк.
    """
    if credentials is None:
        raise AppInvalidTokenError("missing Authorization header")
    token = credentials.credentials
    if not token:
        raise AppInvalidTokenError("empty Bearer token")
    decoded = decode_token(token)
    return decoded.uid


def optional_uid(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> int | None:
    """Вернуть id аутентифицированного пользователя или ``None``, если токена нет.

    Используется эндпоинтами, которые принимают как аутентифицированные, так и
    анонимные запросы (например, ``POST /subscriber/shop``).

    Args:
        credentials: Учётные данные из заголовка (необязательные).

    Returns:
        id пользователя или ``None``.
    """
    if credentials is None:
        return None
    try:
        decoded = decode_token(credentials.credentials)
        return decoded.uid
    except AppInvalidTokenError:
        return None


CurrentUid = Annotated[int, Depends(current_uid)]
OptionalUid = Annotated[int | None, Depends(optional_uid)]


# --------------------------------------------------------------------------- #
# Service factories
# --------------------------------------------------------------------------- #
def auth_service(db: DbSession) -> AuthService:
    """Создать :class:`AuthService` для текущего запроса.

    Args:
        db: Сессия основной БД.

    Returns:
        Новый экземпляр :class:`AuthService`.
    """
    return AuthService(customer_repo=CustomerRepository(db))


def customer_service(
    db: DbSession,
    db_client: DbClientSession,
    db_lk: DbLkSession,
    ip: ClientIp,
) -> CustomerService:
    """Создать :class:`CustomerService` для текущего запроса.

    Args:
        db: Сессия основной БД.
        db_client: Сессия БД логов webclient.
        db_lk: Сессия БД логов LK.
        ip: IP вызывающей стороны.

    Returns:
        Новый экземпляр :class:`CustomerService`.
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
    """Создать :class:`ServiceService` для текущего запроса."""
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
    """Создать :class:`TariffService` для текущего запроса."""
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
    """Создать :class:`FeeService` для текущего запроса."""
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
    """Создать :class:`MessageService` для текущего запроса."""
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
    """Создать :class:`PushService` для текущего запроса."""
    return PushService(push_repo=PushRepository(db), push_client=PushClient())


# Реэкспортируемые Annotated-алиасы для эргономичных сигнатур эндпоинтов.
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
