"""Tests for the JWT helpers in :mod:`app.core.security`."""

from __future__ import annotations

import time

from app.core.config import settings
from app.core.security import decode_token, encode_token


def test_encode_decode_round_trip() -> None:
    """A token issued by :func:`encode_token` should round-trip."""
    uid = 12345
    token = encode_token(uid)
    decoded = decode_token(token)
    assert decoded.uid == uid
    assert decoded.iss == settings.app_name
    # jti must match the deterministic sha1(uid . app_key . iat) formula.
    import hashlib

    expected_jti = hashlib.sha1(
        f"{uid}{settings.app_key}{decoded.iat}".encode("utf-8")
    ).hexdigest()
    assert decoded.jti == expected_jti


def test_decode_rejects_tampered_token() -> None:
    """A token whose signature has been tampered with must be rejected."""
    token = encode_token(1)
    tampered = token[:-2] + ("AA" if token[-2:] != "AA" else "BB")
    from jwt.exceptions import InvalidTokenError

    try:
        decode_token(tampered)
    except InvalidTokenError:
        return
    raise AssertionError("Expected InvalidTokenError for tampered token")


def test_decode_rejects_expired_token() -> None:
    """An expired token must be rejected."""
    # Issue a token, then rewind its `exp` by manipulating the settings cache.
    from app.core.config import Settings

    short_settings = Settings(JWT_KEY=settings.jwt_key, JWT_LIFETIME=-10)
    token = encode_token(1, settings=short_settings)
    # PyJWT raises ExpiredSignatureError, which is a subclass of InvalidTokenError.
    from jwt.exceptions import InvalidTokenError

    try:
        decode_token(token)
    except InvalidTokenError:
        return
    raise AssertionError("Expected InvalidTokenError for expired token")


def test_decode_rejects_wrong_issuer() -> None:
    """A token issued with a different ``iss`` must be rejected."""
    from app.core.config import Settings

    other_settings = Settings(JWT_KEY=settings.jwt_key, APP_NAME="someone-else")
    token = encode_token(1, settings=other_settings)
    from jwt.exceptions import InvalidTokenError

    try:
        decode_token(token)
    except InvalidTokenError:
        return
    raise AssertionError("Expected InvalidTokenError for wrong issuer")
