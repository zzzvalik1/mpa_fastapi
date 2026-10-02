"""JWT-хелперы безопасности.

Этот модуль воспроизводит поведение исходных PHP-классов
``AuthMiddleware`` / ``AuthController``:

* Токены подписываются алгоритмом ``Settings.jwt_algorithm`` (семейство HS) с
  использованием :data:`Settings.jwt_key`.
* Claim ``jti`` вычисляется как ``sha1(uid + app_key + iat)`` — по той же
  формуле, что и в эталонной PHP-реализации — поэтому токены, выпущенные
  любой из реализаций, взаимозаменяемы.
* Claim ``iss`` должен быть равен :data:`Settings.app_name`.
* Claim ``sub`` несёт ``uid`` пользователя.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt import InvalidTokenError, PyJWTError

from app.core.config import Settings, settings as _settings


@dataclass(frozen=True, slots=True)
class DecodedToken:
    """Легковесное, провалидированное представление декодированного JWT.

    Attributes:
        uid: Идентификатор пользователя (claim ``sub``).
        iat: Метка времени ``issued at``.
        exp: Метка времени ``expiration``.
        jti: JWT id (используется для защиты от повторов).
        iss: Издатель.
        raw: Исходный словарь claims.
    """

    uid: int
    iat: int
    exp: int
    jti: str
    iss: str
    raw: dict[str, Any]


def _compute_jti(uid: int, app_key: str, iat: int) -> str:
    """Вычислить claim ``jti``.

    Воспроизводит ``sha1(uid . app_key . iat)`` из PHP-реализации.

    Args:
        uid: Идентификатор пользователя (claim ``sub``).
        app_key: Секрет приложения (:data:`Settings.app_key`).
        iat: Unix-метка времени ``issued at``.

    Returns:
        SHA-1-дайджест в шестнадцатеричной кодировке (40 символов).
    """
    payload = f"{uid}{app_key}{iat}".encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def encode_token(
    uid: int,
    settings: Settings = _settings,
) -> str:
    """Выпустить подписанный JWT для заданного id пользователя.

    Args:
        uid: Идентификатор пользователя, который будет помещён в claim ``sub``.
        settings: Настройки приложения (по умолчанию глобальный синглтон).

    Returns:
        Компактная строка JWT.
    """
    iat = int(datetime.now(timezone.utc).timestamp())
    jti = _compute_jti(uid, settings.app_key, iat)
    payload = {
        "iss": settings.app_name,
        "jti": jti,
        "iat": iat,
        "exp": iat + settings.jwt_lifetime,
        # PyJWT (и RFC 7519) требует, чтобы ``sub`` был строкой.
        "sub": str(uid),
    }
    return jwt.encode(payload, settings.jwt_key, algorithm=settings.jwt_algorithm)


def decode_token(
    token: str,
    settings: Settings = _settings,
) -> DecodedToken:
    """Декодировать и провалидировать JWT.

    Правила валидации:

    * Подпись должна проверяться относительно :data:`Settings.jwt_key`.
    * ``exp`` должен быть в будущем (обрабатывается PyJWT).
    * ``iss`` должен быть равен :data:`Settings.app_name`.
    * ``jti`` должен быть равен ``sha1(sub . app_key . iat)``.

    Args:
        token: Сырая строка JWT (без префикса ``"Bearer "``).
        settings: Настройки приложения.

    Returns:
        :class:`DecodedToken` с провалидированными claims.

    Raises:
        InvalidTokenError: Если токен не проходит проверку подписи, срока
            действия, издателя или ``jti``.
    """
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.app_name,
        )
    except PyJWTError as exc:  # pragma: no cover — re-raised below
        raise InvalidTokenError(f"JWT decode failed: {exc}") from exc

    if "sub" not in claims or "iat" not in claims or "jti" not in claims:
        raise InvalidTokenError("Missing required claims (sub/iat/jti).")

    try:
        uid = int(claims["sub"])
        iat = int(claims["iat"])
    except (TypeError, ValueError) as exc:
        raise InvalidTokenError("sub/iat must be integers.") from exc

    expected_jti = _compute_jti(uid, settings.app_key, iat)
    if not isinstance(claims["jti"], str) or claims["jti"] != expected_jti:
        raise InvalidTokenError("Invalid jti claim.")

    return DecodedToken(
        uid=uid,
        iat=iat,
        exp=int(claims.get("exp", 0)),
        jti=claims["jti"],
        iss=str(claims.get("iss", "")),
        raw=claims,
    )


def token_expires_at(uid: int, settings: Settings = _settings) -> datetime:
    """Вернуть абсолютное время истечения токена, выпущенного *сейчас*.

    Удобный хелпер для вызовающих, которым нужно показать время истечения.

    Args:
        uid: Идентификатор пользователя.
        settings: Настройки приложения.

    Returns:
        Время истечения с учётом часового пояса в UTC.
    """
    now = datetime.now(timezone.utc)
    return now + timedelta(seconds=settings.jwt_lifetime)


__all__ = ["DecodedToken", "encode_token", "decode_token", "token_expires_at"]
