# MPA FastAPI

Python 3.12 / FastAPI порт оригинального мобильного API `mpa_slim` (Slim 4).

Проект воспроизводит — маршрут за маршрутом — REST API, определённое в
PHP Slim 4 референсе, с применением современных Python-конвенций:

* FastAPI + Pydantic v2 + SQLAlchemy 2.x (синхронный драйвер `PyMySQL`).
* Конфигурация через Pydantic-Settings с полными type hints.
* Слоистая архитектура: **эндпоинты → сервисы → репозитории → БД**.
* Централизованная иерархия исключений и JSON-конверт (`{success, message, code, data}`).
* JWT (HS256) авторизация с той же формулой `jti = sha1(uid + app_key + iat)`,
  что и в PHP, поэтому токены взаимозаменяемы.
* Ротируемые по времени лог-файлы (30 дней) через `TimedRotatingFileHandler`.
* Docker / docker-compose с MySQL 5.7.
* Тесты (`pytest`).

---

## Структура проекта

```
fastapi/
├── app/
│   ├── main.py                     # Точка входа FastAPI
│   ├── core/
│   │   ├── config.py               # Настройки (Pydantic v2)
│   │   ├── logging.py              # Ротируемый файловый логгер (30 дней)
│   │   ├── security.py             # JWT encode / decode
│   │   ├── exceptions.py           # Иерархия исключений приложения
│   │   └── exception_handlers.py   # Обработчики JSON-конверта
│   ├── db/
│   │   ├── session.py              # SQLAlchemy-движки (3 БД)
│   │   └── dependencies.py         # get_db / get_db_client / get_db_lk
│   ├── schemas/                    # Pydantic модели запросов/ответов
│   ├── repositories/               # SQL-запросы (1 файл на группу таблиц)
│   ├── services/                   # Бизнес-логика + precheck-алгоритмы
│   ├── api/v1/
│   │   ├── dependencies.py         # FastAPI-зависимости (current_uid, сервисы, ...)
│   │   ├── endpoints/              # Обработчики маршрутов (1 файл на ресурс)
│   │   └── router.py               # Агрегатор, монтируемый на /api/v1
│   └── middleware/                 # Логирование запросов + CORS
├── tests/                          # pytest тесты
├── storage/logs/                   # Ротируемые лог-файлы (создаются автоматически)
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
└── .env.example
```

---

## API эндпоинты

Все маршруты смонтированы под `/api/v1`.

| Метод  | Путь                                                                                        | Auth   | Описание                                                |
|--------|----------------------------------------------------------------------------------------------|--------|---------------------------------------------------------|
| POST   | `/auth/token`                                                                                | -      | Вход (PIN + пароль) → возвращает JWT                    |
| POST   | `/auth/logout`                                                                               | JWT    | Выход (проверяет что пользователь существует)           |
| GET    | `/subscriber`                                                                                | JWT    | Профиль абонента                                        |
| GET    | `/subscriber/accounts`                                                                       | JWT    | Список аккаунтов                                        |
| GET    | `/subscriber/accounts/{accountId}`                                                           | JWT    | Отдельный аккаунт                                       |
| PATCH  | `/subscriber/accounts/{accountId}`                                                           | JWT    | Заморозка / разморозка / обещанный платёж               |
| GET    | `/subscriber/accounts/{accountId}/services`                                                  | JWT    | Список услуг (основная + дополнительные)                |
| PATCH  | `/subscriber/accounts/{accountId}/services/{serviceId}`                                      | JWT    | Смена тарифа / заморозка / разморозка услуги             |
| GET    | `/subscriber/accounts/{accountId}/services/{serviceId}/tariffs`                              | JWT    | Доступные тарифы для смены                              |
| GET    | `/subscriber/accounts/{accountId}/services/{serviceId}/additional-services`                  | JWT    | Каталог дополнительных услуг                            |
| PATCH  | `/subscriber/accounts/{accountId}/services/{serviceId}/additional-services/{id}`             | JWT    | Подписка / отписка от доп. услуги                       |
| POST   | `/subscriber/accounts/{accountId}/transactions`                                              | JWT    | История транзакций                                      |
| GET    | `/subscriber/accounts/{accountId}/pay-link?amount=...`                                       | JWT    | URL для платежа                                         |
| GET    | `/subscriber/accounts/{accountId}/auto-payment-link?amount=...`                              | JWT    | URL для автоплатежа                                     |
| GET    | `/subscriber/accounts/{accountId}/auto-payment-off`                                          | JWT    | Отключить автоплатёж                                    |
| GET    | `/resources/promised-pay-terms`                                                              | JWT    | HTML условий обещанного платежа                         |
| POST   | `/subscriber/shop`                                                                           | опц.   | Заявка из магазина на email поддержки                   |
| POST   | `/support/send-email`                                                                        | -      | Письмо в тех. поддержку                                 |
| GET    | `/notifications/send`                                                                        | -      | Отправка ожидающих push-уведомлений                     |
| GET    | `/notifications/status`                                                                      | -      | Обновление статусов push                                |
| GET    | `/notifications/status-old`                                                                  | -      | Обновление статусов долго-ожидающих push                |
| GET    | `/health`                                                                                    | -      | Liveness-проба                                          |

> **Важно:** интерактивная документация (`/docs`, `/redoc`, `/openapi.json`)
> доступна **только в debug-режиме** (`APP_DEBUG=true`). На продакшене
> (`APP_DEBUG=false`) эти эндпоинты полностью отключены.

---

## Быстрый старт

### 1. Локальная разработка

```bash
cd fastapi
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# отредактируйте .env: параметры БД, JWT-секрет, URL mail/push

uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### 2. Docker

```bash
cd fastapi
cp .env.example .env
# отредактируйте .env

docker compose up -d --build
# API:        http://localhost:8080
# Swagger:    http://localhost:8080/docs  (только при APP_DEBUG=true)
# MySQL:      localhost:33060
```

### 3. Тесты

```bash
cd fastapi
pip install -r requirements.txt
pip install pytest
pytest -v
```

---

## Конфигурация

Все настройки хранятся в `.env` (см. `.env.example`). Основные:

| Переменная        | Описание                                                  | По умолчанию          |
|-------------------|----------------------------------------------------------|------------------------|
| `APP_NAME`        | Имя приложения (JWT-клейм `iss`)                         | `MLK_company`          |
| `APP_DEBUG`       | Включить debug-режим (показ ошибок + /docs, /redoc)      | `true`                 |
| `APP_KEY`         | Секрет для вычисления JWT `jti`                          | `appsecretkey`         |
| `JWT_KEY`         | Ключ подписи JWT                                         | `jwtsecretkey`         |
| `JWT_ALGORITHM`   | Алгоритм JWT (`HS256` / `HS384` / `HS512`)               | `HS256`                |
| `JWT_LIFETIME`    | Время жизни токена в секундах                            | `3600`                 |
| `DB_HOST`/`DB2_*`/`DB3_*` | Подключения к основной / webclient / LK БД     | `127.0.0.1`            |
| `LOG_DIR`         | Директория для ротируемых лог-файлов                     | `storage/logs`         |
| `LOG_RETENTION_DAYS` | Срок хранения логов в днях                            | `30`                   |
| `MAIL_URL`/`MAIL_KEY` | Внешний mailer-шлюз                                  | —                      |
| `PUSH_URL`/`PUSH_KEY` | Внешний push-шлюз                                    | —                      |

---

## Логирование

Два именованных логгера настроены в `app/core/logging.py`:

* `logged`     → `storage/logs/log.log`        (основное приложение)
* `push_log`   → `storage/logs/push_log.log`   (push-воркеры)

Оба используют `TimedRotatingFileHandler(when="midnight", backupCount=30)`,
поэтому новый файл создаётся каждый день и хранится **30 дней** истории.
Каждый запрос также логируется с методом, путём, статус-кодом, длительностью
(мс) и IP клиента через `RequestLoggingMiddleware`.

---

## Примечания по порту

* Проверка пароля использует Python-пакет `bcrypt`. PHP-функция
  `password_hash(..., PASSWORD_DEFAULT)` создаёт хэши с префиксом `$2y$`;
  мы переписываем префикс на `$2b$` перед вызовом `bcrypt.checkpw`, поэтому
  хэши, созданные любой из реализаций, валидируются взаимозаменяемо.
* Алгоритмы `precheck*` (`precheckOplatezh`, `precheckFreeze`,
  `precheckBlock`, `precheckUnFreeze`, `precheckUnBlock`) перенесены дословно
  из `App/Controller/Base.php` и находятся в `app/services/base_service.py`.
* Push-эндпоинты заменяют PHP-трюк single-flight `shell_exec("ps ax | grep …")`
  на in-process `threading.Lock`, что достаточно для рекомендуемого
  single-worker uvicorn-деплоя.
* ORM-модели не объявляются — каждый SQL-запрос написан явно с
  `:param` плейсхолдерами, чтобы поведение точно совпадало с PHP-референсом.
* Документация (`/docs`, `/redoc`, `/openapi.json`) отключается на продакшене
  через `APP_DEBUG=false`.
