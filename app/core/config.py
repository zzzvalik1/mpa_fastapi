"""Application settings.

All configuration is loaded from environment variables (or a local ``.env``
file) and validated by Pydantic Settings v2.  The settings instance is a
singleton exposed as :data:`settings` and is safe to import from anywhere
inside the application.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application configuration.

    All fields map 1:1 to the environment variables documented in
    ``.env.example``.  Field names are case-insensitive on load.
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
    app_name: str = Field(default="MLK_company", description="JWT ``iss`` claim.")
    app_debug: bool = Field(default=True, description="Show error details in responses.")
    app_key: str = Field(default="appsecretkey", description="Application secret used in JWT ``jti``.")

    # ------------------------------------------------------------------ #
    # JWT
    # ------------------------------------------------------------------ #
    jwt_key: str = Field(default="jwtsecretkey")
    jwt_algorithm: str = Field(default="HS256")
    jwt_lifetime: int = Field(default=3600, description="JWT lifetime in seconds.")

    # ------------------------------------------------------------------ #
    # Database #1 — main (CUSTOMER / SERVICE / TARIF / FEE ...)
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
    # Database #3 — LK logs (st_logs)
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
    # External services
    # ------------------------------------------------------------------ #
    mail_url: str = Field(default="https://messaging.ru/mail/api.php")
    mail_key: str = Field(default="mail_key")

    push_url: str = Field(default="https://push.ru")
    push_key: str = Field(default="push_key")

    # ------------------------------------------------------------------ #
    # Server
    # ------------------------------------------------------------------ #
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080, ge=1, le=65535)

    # ------------------------------------------------------------------ #
    # Validators
    # ------------------------------------------------------------------ #
    @field_validator("jwt_algorithm")
    @classmethod
    def _validate_jwt_algorithm(cls, value: str) -> str:
        """Restrict ``jwt_algorithm`` to the HS-family (symmetric) algorithms.

        Args:
            value: Raw environment value.

        Returns:
            Normalized algorithm name (e.g. ``"HS256"``).

        Raises:
            ValueError: If the algorithm is not in the allowed set.
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
        """Normalize the log level to an uppercase standard value.

        Args:
            value: Raw environment value.

        Returns:
            Uppercase level name.

        Raises:
            ValueError: If the level is not recognised by the ``logging`` module.
        """
        import logging

        upper = value.upper()
        if upper not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"log_level must be a standard logging level; got {value!r}.")
        return upper

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @property
    def log_level_int(self) -> int:
        """Return the numeric log level for the configured :attr:`log_level`."""
        import logging

        return getattr(logging, self.log_level)

    @property
    def db_dsn_main(self) -> str:
        """Return the SQLAlchemy URL for the main database."""
        return self._build_dsn(self.db_host, self.db_port, self.db_name, self.db_user, self.db_pass)

    @property
    def db_dsn_client(self) -> str:
        """Return the SQLAlchemy URL for the webclient_logs database."""
        return self._build_dsn(
            self.db2_host, self.db2_port, self.db2_name, self.db2_user, self.db2_pass
        )

    @property
    def db_dsn_lk(self) -> str:
        """Return the SQLAlchemy URL for the LK logs database."""
        return self._build_dsn(
            self.db3_host, self.db3_port, self.db3_name, self.db3_user, self.db3_pass
        )

    @staticmethod
    def _build_dsn(host: str, port: int, name: str, user: str, password: str) -> str:
        """Build a PyMySQL-style SQLAlchemy URL.

        Args:
            host: Database host.
            port: Database port.
            name: Database (schema) name.
            user: Database user.
            password: Database password.

        Returns:
            A ``mysql+pymysql://...`` connection URL with URL-encoded credentials.
        """
        from urllib.parse import quote_plus

        auth = f"{quote_plus(user)}:{quote_plus(password)}"
        return f"mysql+pymysql://{auth}@{host}:{port}/{name}?charset=utf8"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance.

    The cache ensures that environment parsing happens only once per process.

    Returns:
        The application-wide :class:`Settings` singleton.
    """
    return Settings()


#: Module-level singleton used by the rest of the application.
settings: Settings = get_settings()


__all__ = ["Settings", "get_settings", "settings"]
