"""Auth endpoints (``POST /auth/token``, ``POST /auth/logout``)."""

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
    """Authenticate a subscriber and return a signed JWT.

    Args:
        body: Login request body (PIN + password).
        service: Injected :class:`AuthService`.

    Returns:
        An :class:`Envelope` whose ``data`` is ``{"id": <uid>, "jwt": <token>}``.
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
    """Log out the authenticated user.

    The JWT is stateless, so this endpoint only validates that the user
    still exists and logs the event.

    Args:
        uid: Authenticated user id.
        service: Injected :class:`AuthService`.

    Returns:
        An empty success :class:`Envelope`.
    """
    service.logout(uid)
    return Envelope(success=True, message="success", code=200)


__all__ = ["router"]
