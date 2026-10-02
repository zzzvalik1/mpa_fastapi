"""Эндпоинты аутентификации (``POST /auth/token``, ``POST /auth/logout``)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.v1.dependencies import AuthServiceDep, CurrentUid
from app.core.logging import get_logger
from app.schemas.auth import LoginRequest
from app.schemas.common import Envelope

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger()


@router.post(
    "/token",
    response_model=Envelope[dict],
    status_code=status.HTTP_200_OK,
    summary="Авторизация (login by PIN + password).",
)
def login(
    body: LoginRequest,
    service: AuthServiceDep,
) -> Envelope[dict]:
    """Аутентифицировать подписчика и вернуть подписанный JWT.

    Args:
        body: Тело запроса на вход (PIN + пароль).
        service: Внедрённый :class:`AuthService`.

    Returns:
        :class:`Envelope`, у которого ``data`` равно ``{"id": <uid>, "jwt": <token>}``.
    """
    data = service.login(body.username, body.password)
    return Envelope(success=True, data=data, message="success", code=200)


@router.post(
    "/logout",
    response_model=Envelope[None],
    status_code=status.HTTP_200_OK,
    summary="Выход из приложения.",
)
def logout(uid: CurrentUid, service: AuthServiceDep) -> Envelope[None]:
    """Выполнить выход для аутентифицированного пользователя.

    JWT — stateless, поэтому этот эндпоинт только проверяет, что
    пользователь всё ещё существует, и логирует событие.

    Args:
        uid: id аутентифицированного пользователя.
        service: Внедрённый :class:`AuthService`.

    Returns:
        Пустой успешный :class:`Envelope`.
    """
    service.logout(uid)
    return Envelope(success=True, message="success", code=200)


__all__ = ["router"]
