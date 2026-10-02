"""Настройки приложения.

Вся конфигурация загружается из переменных окружения (или локального файла
``.env``) и валидируется Pydantic Settings v2. Экземпляр настроек является
синглтоном, доступным как :data:`settings`, и его безопасно импортировать
из любого места приложения.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Строго типизированная конфигурация приложения.

    Все поля отображаются 1:1 на переменные окружения, описанные в
    ``.env.example``. Имена полей при загрузке нечувствительны к регистру.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Application
    # ------------------------------------------------------------------ #
    app_name: str = Field(default="MLK_company", description="Утверждение ``iss`` для JWT.")
    app_debug: bool = Field(default=True, description="Показывать детали ошибок в ответах.")
    app_key: str = Field(default="appsecretkey", description="Секрет приложения, используемый в JWT ``jti``.")

    # ------------------------------------------------------------------ #
    # JWT
    # ------------------------------------------------------------------ #
    jwt_key: str = Field(default="jwtsecretkey")
    jwt_algorithm: str = Field(default="HS256")
    jwt_lifetime: int = Field(default=3600, description="Время жизни JWT в секундах.")

    # ------------------------------------------------------------------ #
    # Database #1 — основная (CUSTOMER / SERVICE / TARIF / FEE ...)
    # ------------------------------------------------------------------ #
    db_host: str = Field(default="127.0.0.1")
    db_port: int = Field(default=3306)
    db_name: str = Field(default="slim4_api_skeleton")
    db_user: str = Field(default="root")
    db_pass: str = Field(default="")

    # ------------------------------------------------------------------ #
    # Database #2 — webclient_logs
    # ------------------------------------------------------------------ #
    db2_host: str = Field(default="127.0.0.1")
    db2_port: int = Field(default=3306)
    db2_name: str = Field(default="slim4_api_skeleton")
    db2_user: str = Field(default="root")
    db2_pass: str = Field(default="")

    # ------------------------------------------------------------------ #
    # Database #3 — логи ЛК (st_logs)
    # ------------------------------------------------------------------ #
    db3_host: str = Field(default="127.0.0.1")
    db3_port: int = Field(default=3306)
    db3_name: str = Field(default="slim4_api_skeleton")
    db3_user: str = Field(default="root")
    db3_pass: str = Field(default="")

    # ------------------------------------------------------------------ #
    # Logging
    # ------------------------------------------------------------------ #
    log_name: str = Field(default="logged")
    log_push_name: str = Field(default="push_log")
    log_level: str = Field(default="DEBUG")
    log_dir: str = Field(default="storage/logs")
    log_retention_days: int = Field(default=30, ge=1, le=365)

    # ------------------------------------------------------------------ #
    # Внешние сервисы
    # ------------------------------------------------------------------ #
    mail_url: str = Field(default="https://messaging.ru/mail/api.php")
    mail_key: str = Field(default="mail_key")

    push_url: str = Field(default="https://push.ru")
    push_key: str = Field(default="push_key")

    # ------------------------------------------------------------------ #
    # Сервер
    # ------------------------------------------------------------------ #
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080, ge=1, le=65535)

    # ------------------------------------------------------------------ #
    # Валидаторы
    # ------------------------------------------------------------------ #
    @field_validator("jwt_algorithm")
    @classmethod
    def _validate_jwt_algorithm(cls, value: str) -> str:
        """Ограничить ``jwt_algorithm`` алгоритмами семейства HS (симметричными).

        Args:
            value: Сырое значение из окружения.

        Returns:
            Нормализованное имя алгоритма (например ``"HS256"``).

        Raises:
            ValueError: Если алгоритма нет среди разрешённых.
        """
        allowed = {"HS256", "HS384", "HS512"}
        if value not in allowed:
            raise ValueError(
                f"jwt_algorithm must be one of {sorted(allowed)}; got {value!r}."
            )
        return value

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        """Нормализовать уровень логирования к стандартному значению в верхнем регистре.

        Args:
            value: Сырое значение из окружения.

        Returns:
            Имя уровня в верхнем регистре.

        Raises:
            ValueError: Если уровень не распознан модулем ``logging``.
        """
        import logging

        upper = value.upper()
        if upper not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"log_level must be a standard logging level; got {value!r}.")
        return upper

    # ------------------------------------------------------------------ #
    # Хелперы
    # ------------------------------------------------------------------ #
    @property
    def log_level_int(self) -> int:
        """Вернуть числовой уровень логирования для настроенного :attr:`log_level`."""
        import logging

        return getattr(logging, self.log_level)

    @property
    def db_dsn_main(self) -> str:
        """Вернуть SQLAlchemy URL для основной базы данных."""
        return self._build_dsn(self.db_host, self.db_port, self.db_name, self.db_user, self.db_pass)

    @property
    def db_dsn_client(self) -> str:
        """Вернуть SQLAlchemy URL для базы данных webclient_logs."""
        return self._build_dsn(
            self.db2_host, self.db2_port, self.db2_name, self.db2_user, self.db2_pass
        )

    @property
    def db_dsn_lk(self) -> str:
        """Вернуть SQLAlchemy URL для базы данных логов ЛК."""
        return self._build_dsn(
            self.db3_host, self.db3_port, self.db3_name, self.db3_user, self.db3_pass
        )

    @staticmethod
    def _build_dsn(host: str, port: int, name: str, user: str, password: str) -> str:
        """Построить SQLAlchemy URL в стиле PyMySQL.

        Args:
            host: Хост базы данных.
            port: Порт базы данных.
            name: Имя базы данных (схемы).
            user: Пользователь базы данных.
            password: Пароль базы данных.

        Returns:
            URL подключения ``mysql+pymysql://...`` с URL-кодированными учётными данными.
        """
        from urllib.parse import quote_plus

        auth = f"{quote_plus(user)}:{quote_plus(password)}"
        return f"mysql+pymysql://{auth}@{host}:{port}/{name}?charset=utf8"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Вернуть кэшированный экземпляр :class:`Settings`.

    Кэш гарантирует, что разбор переменных окружения выполняется один раз за процесс.

    Returns:
        Общедоменный :class:`Settings`-синглтон приложения.
    """
    return Settings()


#: Синглтон на уровне модуля, используемый остальным приложением.
settings: Settings = get_settings()


__all__ = ["Settings", "get_settings", "settings"]
