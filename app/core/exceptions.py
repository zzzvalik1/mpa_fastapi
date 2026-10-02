"""Иерархия исключений приложения.

Все кастомные исключения наследуются от :class:`AppError`. Каждое исключение
несёт HTTP-код статуса и человекочитаемое сообщение; центральный обработчик
исключений в :mod:`app.core.exception_handlers` преобразует их в JSON-конверт,
ожидаемый мобильным приложением:

::

    {
        "success": false,
        "message": "<error message>",
        "code": <http status>
    }

Использование выделенных классов исключений (вместо возбуждения ``HTTPException``)
позволяет сохранить бизнес-логику развязанной от веб-слоя.
"""

from __future__ import annotations


class AppError(Exception):
    """Базовый класс для каждого определённого в приложении исключения.

    Attributes:
        status_code: HTTP-код статуса, возвращаемый клиенту.
        message: Человекочитаемое описание ошибки.
    """

    #: HTTP-код статуса по умолчанию (переопределяется подклассами).
    status_code: int = 500

    #: Сообщение об ошибке по умолчанию.
    default_message: str = "Internal server error."

    def __init__(self, message: str | None = None, *, status_code: int | None = None) -> None:
        """Инициализировать исключение.

        Args:
            message: Необязательное переопределение :attr:`default_message`.
            status_code: Необязательное переопределение :attr:`status_code`.
        """
        self.message = message or self.default_message
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)

    def __repr__(self) -> str:  # pragma: no cover — debugging convenience
        return f"{type(self).__name__}(status_code={self.status_code}, message={self.message!r})"


# --------------------------------------------------------------------------- #
# Ошибки аутентификации
# --------------------------------------------------------------------------- #
class AuthenticationError(AppError):
    """Возбуждается, когда учётные данные для аутентификации отсутствуют или недействительны."""

    status_code = 401
    default_message = "Authentication required."


class InvalidCredentialsError(AuthenticationError):
    """Возбуждается, когда имя пользователя / пароль не совпадают."""

    default_message = "incorrect username or password"


class UserNotFoundError(AuthenticationError):
    """Возбуждается, когда имя пользователя не удаётся найти."""

    default_message = "username is not found"


class IncorrectUsernameError(AuthenticationError):
    """Возбуждается, когда имя пользователя не соответствует ожидаемому формату."""

    default_message = "incorrect username"


class InvalidTokenError(AppError):
    """Возбуждается, когда JWT отсутствует, malformed или не проходит валидацию."""

    status_code = 401
    default_message = "not valid token"


# --------------------------------------------------------------------------- #
# Ошибки авторизации
# --------------------------------------------------------------------------- #
class AuthorizationError(AppError):
    """Возбуждается, когда аутентифицированному пользователю запрещён доступ к ресурсу."""

    status_code = 403
    default_message = "forbidden"


# --------------------------------------------------------------------------- #
# Доменные (бизнес) ошибки — зеркалят исходные классы ``App/Exception``.
# --------------------------------------------------------------------------- #
class CustomerError(AppError):
    """Возбуждается при нарушениях бизнес-правил, связанных с клиентом."""

    status_code = 400
    default_message = "customer error"


class ServiceError(AppError):
    """Возбуждается при нарушениях бизнес-правил, связанных с сервисом."""

    status_code = 400
    default_message = "service error"


class TariffError(AppError):
    """Возбуждается при нарушениях бизнес-правил, связанных с тарифом."""

    status_code = 400
    default_message = "tariff error"


class FeeError(AppError):
    """Возбуждается при нарушениях бизнес-правил, связанных со сборами / транзакциями."""

    status_code = 400
    default_message = "fee error"


# --------------------------------------------------------------------------- #
# Универсальные ошибки в стиле HTTP
# --------------------------------------------------------------------------- #
class NotFoundError(AppError):
    """Возбуждается, когда упоминаемая сущность не может быть найдена."""

    status_code = 404
    default_message = "not found"


class ValidationError(AppError):
    """Возбуждается при самописных ошибках валидации, не покрываемых Pydantic."""

    status_code = 422
    default_message = "validation error"


class DatabaseError(AppError):
    """Возбуждается, когда операция с базой данных завершается неудачей.

    Исходное исключение цепляется, чтобы его могли просмотреть обработчики
    или отладочные инструменты.
    """

    status_code = 502
    default_message = "database error"

    def __init__(self, message: str | None = None, *, cause: BaseException | None = None) -> None:
        """Инициализировать ошибку.

        Args:
            message: Необязательное переопределение :attr:`default_message`.
            cause: Исходное исключение БД (повторно возбуждается через ``__cause__``).
        """
        super().__init__(message)
        if cause is not None:
            self.__cause__ = cause


__all__ = [
    "AppError",
    "AuthenticationError",
    "InvalidCredentialsError",
    "UserNotFoundError",
    "IncorrectUsernameError",
    "InvalidTokenError",
    "AuthorizationError",
    "CustomerError",
    "ServiceError",
    "TariffError",
    "FeeError",
    "NotFoundError",
    "ValidationError",
    "DatabaseError",
]
