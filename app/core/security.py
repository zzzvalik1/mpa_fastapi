"""JWT security helpers.

This module reproduces the behaviour of the original PHP
``AuthMiddleware`` / ``AuthController``:

* Tokens are signed with ``Settings.jwt_algorithm`` (HS-family) using
  :data:`Settings.jwt_key`.
* The ``jti`` claim is computed as ``sha1(uid + app_key + iat)`` — the same
  formula as the PHP reference implementation — so tokens issued by either
  implementation are interchangeable.
* The ``iss`` claim must equal :data:`Settings.app_name`.
* The ``sub`` claim carries the user's ``uid``.
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
    """Lightweight, validated representation of a decoded JWT.

    Attributes:
        uid: The user identifier (``sub`` claim).
        iat: ``issued at`` timestamp.
        exp: ``expiration`` timestamp.
        jti: JWT id (used for replay protection).
        iss: Issuer.
        raw: The original claims dict.
    """

    uid: int
    iat: int
    exp: int
    jti: str
    iss: str
    raw: dict[str, Any]


def _compute_jti(uid: int, app_key: str, iat: int) -> str:
    """Compute the ``jti`` claim.

    Replicates ``sha1(uid . app_key . iat)`` from the PHP implementation.

    Args:
        uid: User identifier (``sub`` claim).
        app_key: Application secret (:data:`Settings.app_key`).
        iat: ``issued at`` unix timestamp.

    Returns:
        Hex-encoded SHA-1 digest (40 characters).
    """
    payload = f"{uid}{app_key}{iat}".encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def encode_token(
    uid: int,
    settings: Settings = _settings,
) -> str:
    """Issue a signed JWT for the given user id.

    Args:
        uid: The user identifier to embed in the ``sub`` claim.
        settings: Application settings (defaults to the global singleton).

    Returns:
        A compact JWT string.
    """
    iat = int(datetime.now(timezone.utc).timestamp())
    jti = _compute_jti(uid, settings.app_key, iat)
    payload = {
        "iss": settings.app_name,
        "jti": jti,
        "iat": iat,
        "exp": iat + settings.jwt_lifetime,
        # PyJWT (and RFC 7519) requires ``sub`` to be a string.
        "sub": str(uid),
    }
    return jwt.encode(payload, settings.jwt_key, algorithm=settings.jwt_algorithm)


def decode_token(
    token: str,
    settings: Settings = _settings,
) -> DecodedToken:
    """Decode and validate a JWT.

    Validation rules:

    * Signature must verify against :data:`Settings.jwt_key`.
    * ``exp`` must be in the future (handled by PyJWT).
    * ``iss`` must equal :data:`Settings.app_name`.
    * ``jti`` must equal ``sha1(sub . app_key . iat)``.

    Args:
        token: The raw JWT string (without the ``"Bearer "`` prefix).
        settings: Application settings.

    Returns:
        A :class:`DecodedToken` with the validated claims.

    Raises:
        InvalidTokenError: If the token fails signature, expiry, issuer or
            ``jti`` validation.
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
    """Return the absolute expiry datetime for a token issued *now*.

    Convenience helper for callers that need to display the expiry.

    Args:
        uid: User identifier.
        settings: Application settings.

    Returns:
        Timezone-aware expiry datetime in UTC.
    """
    now = datetime.now(timezone.utc)
    return now + timedelta(seconds=settings.jwt_lifetime)


__all__ = ["DecodedToken", "encode_token", "decode_token", "token_expires_at"]
