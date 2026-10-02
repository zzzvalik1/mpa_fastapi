# MPA FastAPI

Python 3.12 / FastAPI port of the original `mpa_slim` (Slim 4) mobile-application API.

The project reproduces — route-by-route — the REST API defined by the PHP
Slim 4 reference implementation, while adopting modern Python conventions:

* FastAPI + Pydantic v2 + SQLAlchemy 2.x (sync, `PyMySQL` driver).
* Pydantic-Settings-driven configuration with full type hints.
* Layered architecture: **endpoints → services → repositories → DB**.
* Centralised exception hierarchy and JSON envelope (`{success, message, code, data}`).
* JWT (HS256) auth with the same `jti = sha1(uid + app_key + iat)` formula
  as the PHP version, so tokens are interchangeable.
* Time-rotated log files (30 days) via `TimedRotatingFileHandler`.
* Docker / docker-compose setup with MySQL 5.7.
* Battery-included tests (`pytest`).

---

## Project layout

```
fastapi/
├── app/
│   ├── main.py                     # FastAPI entry point
│   ├── core/
│   │   ├── config.py               # Settings (Pydantic v2)
│   │   ├── logging.py              # 30-day rotating file logger
│   │   ├── security.py             # JWT encode / decode
│   │   ├── exceptions.py           # Application exception hierarchy
│   │   └── exception_handlers.py   # JSON envelope handlers
│   ├── db/
│   │   ├── session.py              # SQLAlchemy engines (3 databases)
│   │   └── dependencies.py         # get_db / get_db_client / get_db_lk
│   ├── schemas/                    # Pydantic request/response models
│   ├── repositories/               # SQL queries (1 file per table group)
│   ├── services/                   # Business logic + precheck algorithms
│   ├── api/v1/
│   │   ├── dependencies.py         # FastAPI deps (current_uid, services, ...)
│   │   ├── endpoints/              # Route handlers (1 file per resource)
│   │   └── router.py               # Aggregator mounted at /api/v1
│   └── middleware/                 # Request logging + CORS
├── tests/                          # pytest test-suite
├── storage/logs/                   # Rotating log files (auto-created)
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
└── .env.example
```

---

## API endpoints

All routes are mounted under `/api/v1`.

| Method | Path                                                                                        | Auth   | Description                                              |
|--------|----------------------------------------------------------------------------------------------|--------|----------------------------------------------------------|
| POST   | `/auth/token`                                                                                | -      | Login (PIN + password) → returns JWT                     |
| POST   | `/auth/logout`                                                                               | JWT    | Logout (validates user exists)                           |
| GET    | `/subscriber`                                                                                | JWT    | Get subscriber profile                                   |
| GET    | `/subscriber/accounts`                                                                       | JWT    | List accounts                                            |
| GET    | `/subscriber/accounts/{accountId}`                                                           | JWT    | Get a single account                                     |
| PATCH  | `/subscriber/accounts/{accountId}`                                                           | JWT    | Suspend / unsuspend / promised-pay                       |
| GET    | `/subscriber/accounts/{accountId}/services`                                                  | JWT    | List services (primary + additional)                     |
| PATCH  | `/subscriber/accounts/{accountId}/services/{serviceId}`                                      | JWT    | Change tariff / suspend / unsuspend a service            |
| GET    | `/subscriber/accounts/{accountId}/services/{serviceId}/tariffs`                              | JWT    | List tariffs available for switching                     |
| GET    | `/subscriber/accounts/{accountId}/services/{serviceId}/additional-services`                  | JWT    | List additional services catalogue                       |
| PATCH  | `/subscriber/accounts/{accountId}/services/{serviceId}/additional-services/{id}`             | JWT    | Subscribe / unsubscribe an add-on                        |
| POST   | `/subscriber/accounts/{accountId}/transactions`                                              | JWT    | List transactions                                        |
| GET    | `/subscriber/accounts/{accountId}/pay-link?amount=...`                                       | JWT    | Get payment URL                                          |
| GET    | `/subscriber/accounts/{accountId}/auto-payment-link?amount=...`                              | JWT    | Get auto-payment URL                                     |
| GET    | `/subscriber/accounts/{accountId}/auto-payment-off`                                          | JWT    | Disable auto-payment                                     |
| GET    | `/resources/promised-pay-terms`                                                              | JWT    | Promised-pay terms HTML                                  |
| POST   | `/subscriber/shop`                                                                           | opt.   | Send shop-order email to support                         |
| POST   | `/support/send-email`                                                                        | -      | Send support email                                       |
| GET    | `/notifications/send`                                                                        | -      | Flush waiting push messages                              |
| GET    | `/notifications/status`                                                                      | -      | Refresh push statuses                                    |
| GET    | `/notifications/status-old`                                                                  | -      | Refresh long-pending push statuses                       |
| GET    | `/health`                                                                                    | -      | Liveness probe                                           |

Interactive docs are available at `/docs` (Swagger) and `/redoc` (ReDoc).

---

## Getting started

### 1. Local development

```bash
cd fastapi
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env with your DB credentials, JWT secret, mail/push URLs

uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### 2. Docker

```bash
cd fastapi
cp .env.example .env
# edit .env

docker compose up -d --build
# API:        http://localhost:8080
# Swagger:    http://localhost:8080/docs
# MySQL:      localhost:33060
```

### 3. Tests

```bash
cd fastapi
pip install -r requirements.txt
pip install pytest
pytest -v
```

---

## Configuration

All settings live in `.env` (see `.env.example`). Highlights:

| Variable          | Description                                              | Default                |
|-------------------|----------------------------------------------------------|------------------------|
| `APP_NAME`        | Application name (JWT `iss` claim)                       | `MLK_company`          |
| `APP_KEY`         | Secret used in JWT `jti` computation                     | `appsecretkey`         |
| `JWT_KEY`         | JWT signing key                                          | `jwtsecretkey`         |
| `JWT_ALGORITHM`   | JWT algorithm (`HS256` / `HS384` / `HS512`)              | `HS256`                |
| `JWT_LIFETIME`    | Token lifetime in seconds                                | `3600`                 |
| `DB_HOST`/`DB2_*`/`DB3_*` | Main / webclient / LK database connections     | `127.0.0.1`            |
| `LOG_DIR`         | Directory for rotating log files                         | `storage/logs`         |
| `LOG_RETENTION_DAYS` | Log retention (days)                                 | `30`                   |
| `MAIL_URL`/`MAIL_KEY` | External mailer gateway                             | —                      |
| `PUSH_URL`/`PUSH_KEY` | External push-notification gateway                  | —                      |

---

## Logging

Two named loggers are configured in `app/core/logging.py`:

* `logged`     → `storage/logs/log.log`        (main application)
* `push_log`   → `storage/logs/push_log.log`   (push workers)

Both use `TimedRotatingFileHandler(when="midnight", backupCount=30)` so a new
file is created every day and **30 days** of history are kept.  Every request
is also logged with method, path, status code, duration (ms) and client IP
by `RequestLoggingMiddleware`.

---

## Notes on the port

* The `password_verify` flow uses Python's `bcrypt` package.  PHP's
  `password_hash(..., PASSWORD_DEFAULT)` produces `$2y$` hashes; we
  rewrite the prefix to `$2b$` before calling `bcrypt.checkpw` so hashes
  produced by either implementation validate interchangeably.
* The `precheck*` algorithms (`precheckOplatezh`, `precheckFreeze`,
  `precheckBlock`, `precheckUnFreeze`, `precheckUnBlock`) are ported
  verbatim from `App/Controller/Base.php` and live in
  `app/services/base_service.py`.
* The push endpoints replace the PHP `shell_exec("ps ax | grep …")`
  single-flight trick with an in-process `threading.Lock`, which is
  sufficient for the recommended single-worker uvicorn deployment.
* No ORM models are declared — every SQL query is written explicitly with
  `:param` placeholders so behaviour matches the PHP reference exactly.
