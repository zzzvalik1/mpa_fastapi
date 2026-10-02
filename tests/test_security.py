"""Тесты для JWT-хелперов в :mod:`app.core.security`."""

from __future__ import annotations

import time

from app.core.config import settings
from app.core.security import decode_token, encode_token


def test_encode_decode_round_trip() -> None:
    """Токен, выпущенный :func:`encode_token`, должен проходить round-trip."""
    uid = 12345
    token = encode_token(uid)
    decoded = decode_token(token)
    assert decoded.uid == uid
    assert decoded.iss == settings.app_name
    # jti должен соответствовать детерминированной формуле sha1(uid . app_key . iat).
    import hashlib

    expected_jti = hashlib.sha1(
        f"{uid}{settings.app_key}{decoded.iat}".encode("utf-8")
    ).hexdigest()
    assert decoded.jti == expected_jti


def test_decode_rejects_tampered_token() -> None:
    """Токен с изменённой подписью должен быть отклонён."""
    token = encode_token(1)
    tampered = token[:-2] + ("AA" if token[-2:] != "AA" else "BB")
    from jwt.exceptions import InvalidTokenError

    try:
        decode_token(tampered)
    except InvalidTokenError:
        return
    raise AssertionError("Expected InvalidTokenError for tampered token")


def test_decode_rejects_expired_token() -> None:
    """Просроченный токен должен быть отклонён."""
    # Выпускаем токен, затем отматываем его `exp` назад путём манипуляции кэшем настроек.
    from app.core.config import Settings

    short_settings = Settings(JWT_KEY=settings.jwt_key, JWT_LIFETIME=-10)
    token = encode_token(1, settings=short_settings)
    # PyJWT выбрасывает ExpiredSignatureError, который является подклассом InvalidTokenError.
    from jwt.exceptions import InvalidTokenError

    try:
        decode_token(token)
    except InvalidTokenError:
        return
    raise AssertionError("Expected InvalidTokenError for expired token")


def test_decode_rejects_wrong_issuer() -> None:
    """Токен, выпущенный с другим ``iss``, должен быть отклонён."""
    from app.core.config import Settings

    other_settings = Settings(JWT_KEY=settings.jwt_key, APP_NAME="someone-else")
    token = encode_token(1, settings=other_settings)
    from jwt.exceptions import InvalidTokenError

    try:
        decode_token(token)
    except InvalidTokenError:
        return
    raise AssertionError("Expected InvalidTokenError for wrong issuer")
