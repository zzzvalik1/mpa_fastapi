"""Authentication service (login / logout).

Replaces ``App/Controller/AuthController.php``.  Password verification is
done with :mod:`bcrypt` so that hashes produced by PHP's
``password_hash(..., PASSWORD_DEFAULT)`` continue to validate.
"""

from __future__ import annotations

import bcrypt

from app.core.config import Settings, settings as _settings
from app.core.exceptions import (
    IncorrectUsernameError,
    InvalidCredentialsError,
    UserNotFoundError,
)
from app.core.logging import get_logger
from app.core.security import encode_token
from app.repositories.customer_repository import CustomerRepository


class AuthService:
    """Encapsulates login / logout business logic.

    Attributes:
        customer_repo: Customer repository (main DB).
        settings: Application settings.
    """

    def __init__(
        self,
        customer_repo: CustomerRepository,
        settings: Settings = _settings,
    ) -> None:
        """Initialise the service.

        Args:
            customer_repo: Customer repository instance.
            settings: Application settings (defaults to the global singleton).
        """
        self.customer_repo = customer_repo
        self.settings = settings
        self.logger = get_logger()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _verify_password(plain: str, stored_hash: str | None) -> bool:
        """Verify a plain-text password against a stored hash.

        Supports both PHP's ``password_hash`` (bcrypt, prefix ``$2y$``) and
        Python's bcrypt (prefix ``$2b$``).  ``$2a$`` is also accepted.

        Args:
            plain: Plain-text password entered by the user.
            stored_hash: Hash stored in the database (may be ``None``).

        Returns:
            ``True`` if the password matches.
        """
        if not stored_hash:
            return False
        # PHP uses $2y$; Python bcrypt expects $2b$ (or $2a$ / $2y$ in newer versions).
        h = stored_hash
        if h.startswith("$2y$"):
            h = "$2b$" + h[4:]
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), h.encode("utf-8"))
        except ValueError:
            return False

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def login(self, username: str, password: str) -> dict[str, str]:
        """Authenticate a subscriber and return a JWT token payload.

        Args:
            username: 6-digit PIN code.
            password: Plain-text password.

        Returns:
            A dict ``{"id": <uid>, "jwt": <token>}``.

        Raises:
            IncorrectUsernameError: If ``username`` is not 6 characters long.
            UserNotFoundError: If no customer matches the PIN.
            InvalidCredentialsError: If the password does not verify.
        """
        if len(username) != 6 or not username or not password:
            self.logger.error("Incorrect username. Username: %s.", username)
            raise IncorrectUsernameError()

        user = self.customer_repo.find_customer_by_pin(username)
        if not user or not user.get("uid"):
            self.logger.error("Username is not found. Username: %s.", username)
            raise UserNotFoundError()

        stored_hash = user.get("password")
        if not self._verify_password(password, stored_hash):
            self.logger.error("Incorrect username or password. Username: %s.", username)
            raise InvalidCredentialsError()

        uid = int(user["uid"])
        token = encode_token(uid, self.settings)
        self.logger.info("User of id: %s only has logged in", uid)
        return {"id": str(uid), "jwt": token}

    def logout(self, uid: int) -> None:
        """Validate that the user exists (the original API only logs the event).

        Args:
            uid: User id extracted from the JWT.

        Raises:
            UserNotFoundError: If the user does not exist.
        """
        user = self.customer_repo.find_customer_by_uid(uid)
        if not user:
            self.logger.error("User of uid: %s not found", uid)
            raise UserNotFoundError()
        self.logger.info("User of id: %s has logout", uid)


__all__ = ["AuthService"]
