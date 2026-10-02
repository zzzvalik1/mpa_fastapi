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
    def _verify_password(plain: str, stored_value: str | None) -> bool:
        """Verify a plain-text password against the value stored in DB.

        Reproduces the **non-standard** logic of the PHP reference
        (``AuthController::login``):

        .. code-block:: php

            $password_hash_input = password_hash($user->password, PASSWORD_DEFAULT);
            if (password_verify($password, $password_hash_input)) { ... }

        The PHP code takes the password **from the DB**, hashes it, and then
        calls ``password_verify(user_input, hash_of_db_value)`` — which is
        ``True`` iff ``user_input == db_value``.  This works for **any**
        format stored in the DB (plaintext, MD5, SHA1, another hash …).

        We reproduce that behaviour here with a small optimisation: if the
        stored value already **is** a bcrypt hash (prefix ``$2y$`` / ``$2b$``
        / ``$2a$``) we verify directly with ``bcrypt.checkpw`` — otherwise
        we mirror the PHP trick (hash the stored value, then ``checkpw``
        the user input against it).

        Args:
            plain: Plain-text password entered by the user.
            stored_value: Password (or hash) stored in the ``CUSTOMER.password``
                column.  May be ``None``.

        Returns:
            ``True`` if the password matches.
        """
        if not stored_value:
            return False

        stored_bytes = stored_value.encode("utf-8")
        plain_bytes = plain.encode("utf-8")

        # Case 1 — DB already holds a bcrypt hash → verify directly.
        if stored_value.startswith(("$2y$", "$2b$", "$2a$")):
            h = stored_value
            if h.startswith("$2y$"):
                h = "$2b$" + h[4:]
            try:
                return bcrypt.checkpw(plain_bytes, h.encode("utf-8"))
            except ValueError:
                return False

        # Case 2 — DB holds plaintext (or any non-bcrypt format).
        # Mirror PHP: hash the stored value, then checkpw the user input.
        # bcrypt.checkpw(input, hash(stored)) == True  iff  input == stored.
        try:
            hashed = bcrypt.hashpw(stored_bytes, bcrypt.gensalt())
            return bcrypt.checkpw(plain_bytes, hashed)
        except (ValueError, TypeError):
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

        stored_value = user.get("password")
        if not self._verify_password(password, stored_value):
            self.logger.error("Incorrect username or password. Username: %s.", username)
            raise InvalidCredentialsError()

        uid = int(user["uid"])
        token = encode_token(uid, self.settings)
        self.logger.info("User of id: %s only has logged in", uid)
        # PHP: 'id' => $user->uid — целое число (без cast к string).
        return {"id": uid, "jwt": token}

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
