"""Сервис аутентификации (login / logout).

Заменяет ``App/Controller/AuthController.php``.  Проверка пароля выполняется
через :mod:`bcrypt`, поэтому хеши, созданные PHP-функцией
``password_hash(..., PASSWORD_DEFAULT)``, продолжают проходить проверку.
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
    """Инкапсулирует бизнес-логику login / logout.

    Attributes:
        customer_repo: Репозиторий клиентов (основная БД).
        settings: Настройки приложения.
    """

    def __init__(
        self,
        customer_repo: CustomerRepository,
        settings: Settings = _settings,
    ) -> None:
        """Инициализирует сервис.

        Args:
            customer_repo: Экземпляр репозитория клиентов.
            settings: Настройки приложения (по умолчанию — глобальный singleton).
        """
        self.customer_repo = customer_repo
        self.settings = settings
        self.logger = get_logger()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _verify_password(plain: str, stored_hash: str | None) -> bool:
        """Проверяет открытый пароль против сохранённого хеша.

        Поддерживаются как PHP-функция ``password_hash`` (bcrypt, префикс ``$2y$``),
        так и Python bcrypt (префикс ``$2b$``).  ``$2a$`` также принимается.

        Args:
            plain: Открытый пароль, введённый пользователем.
            stored_hash: Хеш, сохранённый в БД (может быть ``None``).

        Returns:
            ``True``, если пароль совпадает.
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
        """Аутентифицирует абонента и возвращает payload с JWT-токеном.

        Args:
            username: 6-значный PIN-код.
            password: Открытый пароль.

        Returns:
            Словарь ``{"id": <uid>, "jwt": <token>}``.

        Raises:
            IncorrectUsernameError: Если ``username`` не состоит из 6 символов.
            UserNotFoundError: Если ни один клиент не соответствует PIN.
            InvalidCredentialsError: Если пароль не прошёл проверку.
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
        """Проверяет, что пользователь существует (исходный API только пишет событие в лог).

        Args:
            uid: Идентификатор пользователя, извлечённый из JWT.

        Raises:
            UserNotFoundError: Если пользователь не существует.
        """
        user = self.customer_repo.find_customer_by_uid(uid)
        if not user:
            self.logger.error("User of uid: %s not found", uid)
            raise UserNotFoundError()
        self.logger.info("User of id: %s has logout", uid)


__all__ = ["AuthService"]
