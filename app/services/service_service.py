"""Сервис услуг (порт ``App/Controller/ServiceController.php``).

Реализует:

* ``GET    .../services``                                → список услуг
* ``PATCH   .../services/{serviceId}``                   → смена тарифа / suspend / unsuspend
* ``GET    .../services/{serviceId}/additional-services`` → список доступных доп. услуг
* ``PATCH   .../services/{serviceId}/additional-services/{AdditionalServiceId}`` → подписка/отписка
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.core.exceptions import (
    AuthorizationError,
    NotFoundError,
    ServiceError,
)
from app.core.logging import get_logger
from app.repositories.customer_repository import CustomerRepository
from app.repositories.service_repository import ServiceRepository
from app.repositories.tariff_repository import TariffRepository
from app.schemas.common import RUB_CURRENCY
from app.services.base_service import BaseService
from app.services.mailer_client import MailerClient


# Mapping ``TARIF.type`` -> MLK service type slug.
_TYPE_SLUG_MAP: dict[int, str] = {
    1: "type_inet", 8: "type_inet",
    28: "type_tv", 29: "type_tv",
    9: "type_serv", 24: "type_serv", 31: "type_serv",
}


def _type_slug(tariff_type: int | None) -> str:
    """Возвращает MLK-слаг типа услуги для числового типа тарифа."""
    if tariff_type is None:
        return "type_misc"
    return _TYPE_SLUG_MAP.get(tariff_type, "type_misc")


def _duration_slug(duration: int | None) -> str:
    """Сопоставляет ``TARIF.duration`` с человекочитаемой строкой периодичности."""
    if duration in (1, 3, 6):
        return "month"
    if duration == 2:
        return "30 day"
    if duration in (4, 5):
        return "daytime"
    return "unknown"


def _status_block(code: int, title: str | None) -> dict[str, Any]:
    """Строит блок ``state`` из числового кода статуса."""
    is_unlock = code == 1
    return {
        "id": code,
        "code": "unlock" if is_unlock else "lock",
        "title": title or "",
        "paused": not is_unlock,
    }


class ServiceService(BaseService):
    """Высокоуровневые операции с услугами / тарифами / доп. услугами."""

    def __init__(
        self,
        customer_repo: CustomerRepository,
        service_repo: ServiceRepository,
        tariff_repo: TariffRepository,
        fee_repo,  # noqa: ANN001 — circular-safe type omitted
        lklog_repo,  # noqa: ANN001
        webclientlog_repo,  # noqa: ANN001
        mailer: MailerClient,
        client_ip: str = "",
    ) -> None:
        """Инициализирует сервис.

        Args:
            customer_repo: Репозиторий клиентов.
            service_repo: Репозиторий услуг.
            tariff_repo: Репозиторий тарифов.
            fee_repo: Репозиторий платежей (не используется здесь, но сохранён для симметрии API).
            lklog_repo: Репозиторий LK-логов.
            webclientlog_repo: Репозиторий webclient-логов.
            mailer: Mailer-клиент для отправки уведомлений о смене тарифа.
            client_ip: IP вызывающего клиента.
        """
        super().__init__(
            customer_repo=customer_repo,
            service_repo=service_repo,
            tariff_repo=tariff_repo,
            fee_repo=fee_repo,
            lklog_repo=lklog_repo,
            webclientlog_repo=webclientlog_repo,
            client_ip=client_ip,
        )
        self.mailer = mailer

    # ------------------------------------------------------------------ #
    # GET .../services
    # ------------------------------------------------------------------ #
    def get_services(self, uid: int, account_id: int) -> list[dict[str, Any]]:
        """Возвращает список услуг для ``GET .../services``.

        Args:
            uid: Идентификатор аутентифицированного пользователя.
            account_id: Идентификатор аккаунта из пути (должен совпадать с ``uid``).

        Returns:
            Список dict услуг (сначала основной, затем доп. услуги).

        Raises:
            NotFoundError: Если пользователь не найден.
            AuthorizationError: Если ``account_id`` не совпадает с ``uid``.
        """
        user = self.customer_repo.find_customer_by_uid(uid)
        if not user:
            raise NotFoundError("incorrect username")
        if int(user["uid"]) != account_id:
            raise AuthorizationError("incorrect accountId")

        self.logger.debug(
            "User of id: %s get query GET '/subscriber/accounts/%s/services'.", uid, account_id
        )

        services = self.service_repo.get_actual_services(uid)
        if not services:
            return []

        primary_row = next((s for s in services if int(s.get("isPrimary") or 0) == 1), None)
        if not primary_row:
            return []

        # Build the "next" block when a tariff change is scheduled.
        next_block: dict[str, Any] | list[Any] = []
        if int(primary_row.get("tariffId") or 0) != int(primary_row.get("tariffIdNext") or 0):
            next_block = {
                "id": int(primary_row.get("serviceId") or 0),
                "title": primary_row.get("nextTariffName") or "",
                "info": {
                    "type": "speed",
                    "title": "Скорость",
                    "description": f"{self.mb_speed(primary_row.get('nextTariffSpeed'))} Мб/с",
                },
                "description": primary_row.get("tariffType") or "",
                "started_at": primary_row.get("date_expire"),
                "price": {
                    "total": float(primary_row.get("nextTariffFee") or 0.0)
                    * (100 - float(primary_row.get("discount") or 0)) / 100,
                    "currency": RUB_CURRENCY.model_dump(),
                    "frequency": primary_row.get("nextTariffDuration") or "unknown",
                },
                "state": _status_block(
                    int(primary_row.get("codeStatus") or 0), primary_row.get("status")
                ),
                "address": "",
                "mutations": [],
            }

        # Additional services
        additional_services: list[dict[str, Any]] = []
        current_additional: list[dict[str, Any]] = []
        for s in services:
            if int(s.get("isPrimary") or 0) == 1:
                continue
            title = s.get("tariffName") or ""
            if "[add]" in title and "[real]" in title:
                title = f"Дополнительный IP - {s.get('serviceIP') or ''}"
            elif "[add]" in title:
                title = "Дополнительный компьютер"
            if "Subnet" in title:
                title = "Подсеть"

            price = {
                "total": float(s.get("tariffFee") or 0.0),
                "currency": RUB_CURRENCY.model_dump(),
                "frequency": s.get("tariffDuration") or "unknown",
            }
            state = _status_block(int(s.get("codeStatus") or 0), s.get("status"))
            date_expire = s.get("date_expire")
            # PHP: date('Y-m-d H:i:s ', ...) — с trailing space!
            _dt = self._parse_date_dt(date_expire)
            pay_until = (_dt - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S ") if _dt else None
            additional_services.append({
                "id": int(s.get("serviceId") or 0),
                "title": title,
                "description": s.get("tariffType") or "",
                "pay_until": pay_until,
                "ended_at": pay_until,
                "price": price,
                "state": state,
                "mutations": [],
            })
            current_additional.append({
                "id": int(s.get("serviceId") or 0),
                "title": title,
                "description": s.get("tariffType") or "",
                "pay_until": pay_until,
                "type": s.get("type") or "",
                "price": price,
                "state": state,
                "next": {},
                "address": "",
                "additional_services": [],
                "mutations": [],
            })

        mutations = ["addServs"]
        if self.is_allow_change_tariff(uid):
            mutations.append("changeTariff")

        # Primary service entry
        date_expire = primary_row.get("date_expire")
        # PHP: date('Y-m-d H:i:s ', ...) — с trailing space!
        _dt = self._parse_date_dt(date_expire)
        pay_until_primary = (_dt - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S ") if _dt else None
        primary_price = {
            "total": float(primary_row.get("tariffFee") or 0.0)
            * (100 - float(primary_row.get("discount") or 0)) / 100,
            "currency": RUB_CURRENCY.model_dump(),
            "frequency": primary_row.get("tariffDuration") or "unknown",
        }
        primary_entry = {
            "id": int(primary_row.get("serviceId") or 0),
            "title": primary_row.get("tariffName") or "",
            "info": {
                "type": "speed",
                "title": "Скорость",
                "description": f"{self.mb_speed(primary_row.get('tariffSpeed'))} Мб/с",
            },
            "description": primary_row.get("tariffType") or "",
            "pay_until": pay_until_primary,
            "type": primary_row.get("type") or "",
            "price": primary_price,
            "state": _status_block(int(primary_row.get("codeStatus") or 0), primary_row.get("status")),
            "next": next_block,
            "address": "",
            "additional_services": additional_services,
            "mutations": mutations,
        }
        return [primary_entry, *current_additional]

    # ------------------------------------------------------------------ #
    # PATCH .../services/{serviceId}
    # ------------------------------------------------------------------ #
    def change_service(
        self,
        uid: int,
        account_id: int,
        service_id: int,
        action: str,
        tariff_id: int | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
    ) -> dict[str, Any]:
        """Применяет действие ``change-tariff`` / ``suspend`` / ``unsuspend``.

        Args:
            uid: Идентификатор аутентифицированного пользователя.
            account_id: Идентификатор аккаунта из пути.
            service_id: Идентификатор услуги из пути.
            action: Имя действия.
            tariff_id: Идентификатор целевого тарифа (обязателен для ``change-tariff``).
            date_start: Опциональное начало заморозки (для ``suspend``).
            date_end: Опциональный конец заморозки (для ``suspend``).

        Returns:
            Словарь с ключами ``success`` / ``message`` / ``code``.
        """
        user = self.customer_repo.find_customer_by_uid(uid)
        if not user:
            raise NotFoundError("incorrect username")
        if int(user["uid"]) != account_id:
            raise AuthorizationError("incorrect accountId")

        service = self.service_repo.get_primary_service(uid)
        if not service:
            raise ServiceError("primary service not found")

        self.logger.debug(
            "User of id: %s get query PATCH '/subscriber/accounts/%s/services/%s/', action: %s.",
            uid, account_id, service_id, action,
        )

        if action == "change-tariff":
            if tariff_id is None:
                raise ServiceError("tariffId is required for change-tariff")
            return self._change_tariff(user, service, tariff_id)
        if action == "suspend":
            return self._suspend_service(user, service, date_start, date_end)
        if action == "unsuspend":
            return self._unsuspend_service(user, service)
        raise ServiceError("incorrect action input")

    # ------------------------------------------------------------------ #
    # Action: change-tariff
    # ------------------------------------------------------------------ #
    def _change_tariff(
        self,
        user: dict[str, Any],
        service: dict[str, Any],
        tariff_id: int,
    ) -> dict[str, Any]:
        """Выполняет смену тарифа."""
        uid = int(user["uid"])
        if not self.is_allow_change_tariff(uid):
            return {"success": False, "message": "changing the tariff is forbidden", "code": 400}

        allowed = self.tariff_repo.get_private_switch_allowed_list()
        if not any(int(t.get("tid") or 0) == tariff_id for t in allowed):
            return {"success": False, "message": "tariff not allowed", "code": 400}

        next_tariff = self.tariff_repo.get_tariff_by_tid(tariff_id) or {}
        sid = int(service.get("sid") or 0)
        cur_speed = self.mb_speed(int(service.get("speedlimit") or 0))
        next_speed = self.mb_speed(int(next_tariff.get("speedlimit") or 0))

        # If the user is upgrading past 100Mbps, just email support and report ordered.
        if cur_speed <= 100 and next_speed > 100:
            subject = f"Заказ смены ТП из мобильного приложения {user.get('pin')}"
            self._notify_support_tariff_change(user, next_tariff, tariff_id, subject, ordered=True)
            self.logger.info("User of id: %s ordered a change of tariff to %s.", uid, tariff_id)
            return {"success": True, "message": "ordered a change of tariff", "code": 200}

        # Otherwise apply immediately.
        if not self.tariff_repo.set_tariff(sid, tariff_id):
            return {"success": False, "message": "change failed 1", "code": 400}
        if self.customer_repo.get_personal_discount(uid):
            self.customer_repo.set_next_personal_discount(uid)
        self.logger.info("User of id: %s change tariff on service %s to %s.", uid, sid, tariff_id)

        before = {
            "tariffId": service.get("tid"),
            "tariffName": service.get("name"),
            "abonent_fee": service.get("abonent_fee"),
        }
        after = {
            "tariffId": next_tariff.get("tid"),
            "tariffName": next_tariff.get("name"),
            "abonent_fee": next_tariff.get("abonent_fee"),
        }
        self.write_lk_log(uid, "Смена тарифа в МЛК", "tarifChange", before, after)

        subject = f"Смена ТП из мобильного приложения {user.get('pin')}"
        self._notify_support_tariff_change(user, next_tariff, tariff_id, subject, ordered=False)
        return {"success": True, "message": "completed successfully", "code": 200}

    def _notify_support_tariff_change(
        self,
        user: dict[str, Any],
        next_tariff: dict[str, Any],
        tariff_id: int,
        subject: str,
        *,
        ordered: bool,
    ) -> None:
        """Отправляет email-уведомление о смене тарифа в support."""
        uid = int(user["uid"])
        body = (
            f'Клиент <a href="https://client.ru/showuser/{uid}.html">'
            f"https://client.ru/showuser/{uid}.html</a> <br />"
            "---------------------------------------------------------------- <br />"
            f"ПИН: {user.get('pin')} <br />"
            f"Логин: {user.get('login')} <br />"
            f"Телефон: {user.get('phones')} <br />"
        )
        verb = "Заказ смены тарифа на" if ordered else "Сменил тариф на"
        body += (
            f"{verb} {next_tariff.get('name')} стоимостью "
            f"{next_tariff.get('abonent_fee')} руб. (tid {tariff_id}); <br />"
        )
        if self.customer_repo.get_personal_discount(uid):
            body += f"Имеется персональная скидка: {self.customer_repo.get_personal_discount(uid)} %<br />"
        body += "---------------------------------------------------------------- <br />"
        self.mailer.send_email(
            sender="messaging@starlink.ru",
            to="support@starlink.ru",
            subject=subject,
            message=body,
        )

    # ------------------------------------------------------------------ #
    # Action: suspend / unsuspend (delegates to base prechecks)
    # ------------------------------------------------------------------ #
    def _suspend_service(
        self,
        user: dict[str, Any],
        service: dict[str, Any],
        date_start: str | None,
        date_end: str | None,
    ) -> dict[str, Any]:
        """Выполняет service-level suspend (заморозка или добровольная блокировка)."""
        uid = int(user["uid"])
        if not date_start or not date_end:
            tomorrow, end = self._default_freeze_dates()
            date_start = date_start or tomorrow
            date_end = date_end or end

        if self.precheck_freeze(uid, date_start, date_end).status:
            self.customer_repo.update_customer(
                uid, {"date_freeze": date_start, "date_unfreeze": date_end}
            )
            date_expire = service.get("date_expire")
            if date_expire:
                _dt = self._parse_date_dt(date_expire)
                new_expire = _dt.strftime("%Y-%m-%d 04:00:00") if _dt else str(date_expire)
                self.service_repo.update_service(int(service["sid"]), {"date_expire": new_expire})
            self.logger.info(
                "User of id: %s freeze account from %s to %s.", uid, date_start, date_end
            )
            self.write_lk_log(
                uid, "Заказ заморозки из МЛК", "freezeAdd", "",
                {"dateStart": date_start, "dateEnd": date_end},
            )
            return {"success": True, "message": "completed successfully", "code": 200}

        block = self.precheck_block(uid, date_start, date_end)
        if block.status:
            self.customer_repo.set_block(uid, date_start, date_end)
            self.logger.info(
                "User of id: %s blocked account from %s to %s.", uid, date_start, date_end
            )
            self.write_lk_log(
                uid, "Заказ добровольной блокировки из МЛК", "freezeAdd", "",
                {"dateStart": date_start, "dateEnd": date_end},
            )
            return {"success": True, "message": "completed successfully", "code": 200}

        return {"success": False, "message": f"block failed: {block.error}", "code": 400}

    def _unsuspend_service(
        self,
        user: dict[str, Any],
        service: dict[str, Any],
    ) -> dict[str, Any]:
        """Выполняет service-level unsuspend."""
        uid = int(user["uid"])
        df_raw = user.get("date_freeze")
        du_raw = user.get("date_unfreeze")
        is_frozen = bool(int(user.get("is_frozen") or 0))
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        df = self._parse_date_dt(df_raw)
        du = self._parse_date_dt(du_raw)

        if df and du and df < tomorrow and du > today and is_frozen:
            service_expire = service.get("date_expire")
            se = self._parse_date_dt(service_expire)
            if se and du:
                new_expire = (se - (du - today)).strftime("%Y-%m-%d")
                self.service_repo.update_service(int(service["sid"]), {"date_expire": new_expire})
            self.customer_repo.update_customer(uid, {"date_unfreeze": today.strftime("%Y-%m-%d")})
            self.logger.info("User of id: %s unblocked service.", uid)
            self.write_lk_log(
                uid, "Отмена добровольной блокировки в МЛК", "freezeDel",
                {"dateStart": str(df_raw), "dateEnd": str(du_raw)},
                {"dateStart": str(df_raw), "dateEnd": today.strftime("%Y-%m-%d")},
            )
            return {"success": True, "message": "completed successfully", "code": 200}

        if df and df >= tomorrow:
            self.customer_repo.update_customer(uid, {"date_freeze": None, "date_unfreeze": None})
            self.logger.info("User of id: %s unblocked account.", uid)
            self.write_lk_log(
                uid, "Отмена добровольной блокировки в МЛК", "freezeDel",
                {"dateStart": str(df_raw), "dateEnd": str(du_raw)},
                {"dateStart": None, "dateEnd": None},
            )
            return {"success": True, "message": "completed successfully", "code": 200}

        return {"success": False, "message": "block failed", "code": 400}

    # ------------------------------------------------------------------ #
    # GET .../additional-services  +  PATCH .../additional-services/{id}
    # ------------------------------------------------------------------ #
    # Mapping ``tid`` -> description (kept identical to the PHP version).
    _ADD_SERVICES_DESCRIPTIONS: dict[int, str] = {
        20320: (
            "HD-каналы - 58 каналов\nДетские - 11 каналов\nКино - 22 канала\n"
            "Музыкальные - 23 каналов\nНовостные - 15 каналов\nПознавательные - 41 канал\n"
            "Развлекательные - 46 каналов\nСпорт - 13 каналов\nЭфирные - 18 каналов\n"
            "Региональные - 51 канал\nПолный список доступных каналов вы можете посмотреть на нашем сайте\n"
            "starlink.ru в разделе Цифровое ТВ"
        ),
        20326: (
            "HD-каналы - 87 каналов\nДетские - 18 каналов\nКино - 44 канала\n"
            "Музыкальные - 25 каналов\nНовостные - 15 каналов\nПознавательные - 68 каналов\n"
            "Развлекательные - 55 каналов\nСпорт - 21 канал\nЭфирные - 18 каналов\n"
            "Региональные - 51 канал\nПолный список доступных каналов вы можете посмотреть на нашем сайте\n"
            "starlink.ru в разделе Цифровое ТВ"
        ),
        20335: (
            "HD-каналы - 104 канала\nДетские - 19 каналов\nКино - 56 каналов\n"
            "Музыкальные - 25 каналов\nНовостные - 15 каналов\nПознавательные - 77 каналов\n"
            "Развлекательные - 56 каналов\nСпорт - 21 канал\nЭфирные - 18 каналов\n"
            "Региональные - 51 канал\nПолный список доступных каналов вы можете посмотреть на нашем сайте\n"
            "starlink.ru в разделе Цифровое ТВ"
        ),
        20347: (
            "HD-каналы - 104 канала\nДетские - 19 каналов\nКино - 56 каналов\n"
            "Музыкальные - 25 каналов\nНовостные - 15 каналов\nПознавательные - 77 каналов\n"
            "Развлекательные - 56 каналов\nСпорт - 21 канал\nЭфирные - 18 каналов\n"
            "Региональные - 51 канал\nAMEDIATEKA+IVI+START онлайн кинотеатры\n"
            "Полный список доступных каналов вы можете посмотреть на нашем сайте\n"
            "starlink.ru в разделе Цифровое ТВ"
        ),
    }

    def get_additional_services(
        self, uid: int, account_id: int, service_id: int
    ) -> list[dict[str, Any]]:
        """Возвращает каталог доп. услуг, доступных для ``service_id``."""
        user = self.customer_repo.find_customer_by_uid(uid)
        if not user:
            raise NotFoundError("incorrect username")
        if int(user["uid"]) != account_id:
            raise AuthorizationError("incorrect accountId")

        self.logger.debug(
            "User of id: %s get query GET '/subscriber/accounts/%s/services/%s/additional-services'.",
            uid, account_id, service_id,
        )

        # Build main service lookup.
        active_services = self.service_repo.get_actual_services(uid)
        main_service = next(
            (s for s in active_services if int(s.get("isPrimary") or 0) == 1), None
        )
        if not main_service:
            return []
        if int(main_service.get("serviceId") or 0) != service_id:
            self.logger.error("User of serviceId: %s is already an additional service.", service_id)
            raise ServiceError("serviceId is already an additional service")

        main_tariff = self.tariff_repo.get_tariff_by_tid(int(main_service.get("tariffId") or 0)) or {}
        existing_tids = {int(s.get("tariffId") or 0) for s in active_services}

        # Real-IP tariff variant
        realip_tariffs: list[dict[str, Any]] = []
        if (
            int(user.get("ctype") or 0) == 0
            and (self.is_allow_realip_tariff(uid) or self.is_allow_wo_realip_tariff(uid))
        ):
            target_tid = (
                self.tariff_repo.find_tariff_without_realip(int(main_tariff.get("tid") or 0))
                if "[real]" in (main_tariff.get("name") or "")
                else self.tariff_repo.find_tariff_with_realip(int(main_tariff.get("tid") or 0))
            )
            if target_tid:
                rows = self.tariff_repo.get_services_tariffs(tids=[target_tid])
                if rows:
                    row = dict(rows[0])
                    row["serviceName"] = "Реальный ip адрес"
                    row["typeAddService"] = "auto"
                    row["serviceFee"] = (
                        self.get_real_ip_cost(
                            int(main_service.get("tariffId") or 0),
                            int(main_service.get("nextTariffId") or 0),
                        )
                        if main_tariff.get("abonent_fee")
                        else 0.0
                    )
                    realip_tariffs.append(row)

        catalogue = self.tariff_repo.get_services_tariffs(
            tids=list(self._ADD_SERVICES_DESCRIPTIONS.keys())
        )
        services = realip_tariffs + catalogue
        result: list[dict[str, Any]] = []
        for s in services:
            tid = int(s.get("serviceTid") or 0)
            unlock = tid in existing_tids or int(s.get("serviceType") or 0) == 1
            result.append({
                "id": tid,
                "title": s.get("serviceName") or "",
                "description": self._ADD_SERVICES_DESCRIPTIONS.get(tid) or s.get("tariffType") or "",
                "pay_until": main_service.get("date_expire"),
                "started_at": datetime.now().strftime("%Y-%m-%d 04:00:00"),
                "ended_at": main_service.get("date_expire"),
                "info": {},
                "type": s.get("type") or _type_slug(int(s.get("serviceType") or 0)),
                "price": {
                    "total": float(s.get("serviceFee") or 0.0),
                    "currency": RUB_CURRENCY.model_dump(),
                    "frequency": main_service.get("tariffDuration") or "unknown",
                },
                "state": {
                    "id": 1 if unlock else 2,
                    "code": "unlock" if unlock else "lock",
                    "title": "Услуга оказывается" if unlock else "Не обслуживается",
                    "paused": not unlock,
                },
                "type_add_service": s.get("typeAddService") or "manual",
                "mutations": [],
            })
        return result

    def set_additional_service(
        self,
        uid: int,
        account_id: int,
        service_id: int,
        additional_service_id: int,
        action: int,
    ) -> dict[str, Any]:
        """Подписывает (``action == 1``) или отписывает (``action == 0``) доп. услугу."""
        user = self.customer_repo.find_customer_by_uid(uid)
        if not user:
            raise NotFoundError("incorrect username")
        if int(user["uid"]) != account_id:
            raise AuthorizationError("incorrect accountId")

        service = self.service_repo.get_primary_service(uid)
        if not service:
            raise ServiceError("primary service not found")
        if int(service.get("sid") or 0) != service_id:
            return {
                "success": False,
                "message": f"subscribe change failed, main service {service_id} not found",
                "code": 400,
            }

        trf_change = self.tariff_repo.get_tariff_by_tid(additional_service_id) or {}
        if not trf_change:
            self.logger.info("Can't find tariff %s.", additional_service_id)
            raise ServiceError("change failed")

        self.logger.debug(
            "User of id: %s get query PATCH '/subscriber/accounts/%s/services/%s/"
            "additional-services/%s', action %s.",
            uid, account_id, service_id, additional_service_id, action,
        )

        if action == 0:
            return self._unsubscribe_addon(user, service, trf_change, additional_service_id, service_id)
        if action == 1:
            return self._subscribe_addon(user, service, trf_change, additional_service_id, service_id)
        raise ServiceError("subscribe incorrect action input")

    # ------------------------------------------------------------------ #
    # Subscribe / unsubscribe helpers
    # ------------------------------------------------------------------ #
    def _unsubscribe_addon(
        self,
        user: dict[str, Any],
        service: dict[str, Any],
        trf_change: dict[str, Any],
        change_tid: int,
        service_id: int,
    ) -> dict[str, Any]:
        """Отписывает доп. услугу."""
        uid = int(user["uid"])
        if not self.is_exist_in_active_service(uid, change_tid, service_id):
            return {
                "success": False,
                "message": f"change unsubscribe failed, add service {change_tid} not found",
                "code": 400,
            }
        trf = self.tariff_repo.get_tariff_by_tid(int(service.get("tid") or 0)) or {}
        if (
            "[real]" in (trf.get("name") or "")
            and "[real]" in (trf_change.get("name") or "")
        ):
            new_tid = self.tariff_repo.find_tariff_without_realip(change_tid)
            if self.tariff_repo.set_tariff(int(service["sid"]), new_tid):
                self.logger.info("User of id: %s change tariff to %s from next RP", uid, new_tid)
                self.write_lk_log(
                    uid, "Отключение услуги в МЛК", "serviceDel",
                    {
                        "tariffId": service.get("tid"),
                        "tariffName": service.get("name"),
                        "abonent_fee": service.get("abonent_fee"),
                    },
                    "",
                )
                return {"success": True, "message": "completed successfully", "code": 200}
            return {"success": False, "message": "change failed1", "code": 400}

        # Other add-ons: notify support by email.
        self.logger.info("User of id: %s lock tariff %s from next RP.", uid, change_tid)
        self.mailer.send_email(
            sender=user.get("email") or "messaging@starlink.ru",
            to="support@starlink.ru",
            subject=f"Сообщение из мобильного приложения авторизованного пользователя {user.get('pin')}",
            message=(
                f'Клиент <a href="https://client.ru/showuser/{uid}.html">'
                f"https://client.ru/showuser/{uid}.html</a> <br />"
                "---------------------------------------------------------------- <br />"
                "<b>Заявка на отключение дополнительного сервиса</b> <br />"
                f"ПИН: {user.get('pin')} <br />"
                f"Логин: {user.get('login')} <br />"
                f"Адрес: {user.get('address')} <br />"
                f"Телефон: {user.get('phones')} <br />"
                "Комментарий: Добрый день! Хочу отключить дополнительный сервис <br />"
                f"ТП: {trf_change.get('name')} стоимостью {trf_change.get('abonent_fee')} руб. [tid {change_tid}]<br />"
            ),
        )
        return {"success": True, "message": "unsubscribe completed successfully", "code": 200}

    def _subscribe_addon(
        self,
        user: dict[str, Any],
        service: dict[str, Any],
        trf_change: dict[str, Any],
        change_tid: int,
        service_id: int,
    ) -> dict[str, Any]:
        """Подписывает доп. услугу."""
        uid = int(user["uid"])
        # Balance check for non-real-IP add-ons.
        if not trf_change.get("name", "").startswith("[real]"):
            balance = float(user.get("balance") or 0.0)
            fee = float(trf_change.get("abonent_fee") or 0.0)
            if not int(user.get("ign_balance") or 0) and balance < fee:
                return {
                    "success": False,
                    "message": "Not enough money to add service11",
                    "code": 401,
                }
            if self.is_exist_in_active_service(uid, change_tid, service_id):
                return {
                    "success": False,
                    "message": f"subscribe change failed, add service {change_tid} already found",
                    "code": 400,
                }
            self.logger.info("User of id: %s add service tariff to %s.", uid, change_tid)
            self.mailer.send_email(
                sender=user.get("email") or "messaging@starlink.ru",
                to="support@starlink.ru",
                subject=f"Сообщение из мобильного приложения авторизованного пользователя {user.get('pin')}",
                message=(
                    f'Клиент <a href="https://client.ru/showuser/{uid}.html">'
                    f"https://client.ru/showuser/{uid}.html</a> <br />"
                    "---------------------------------------------------------------- <br />"
                    "<b>Заявка на подключение дополнительного сервиса</b> <br />"
                    f"ПИН: {user.get('pin')} <br />"
                    f"Логин: {user.get('login')} <br />"
                    f"Адрес: {user.get('address')} <br />"
                    f"Телефон: {user.get('phones')} <br />"
                    "Комментарий: Добрый день! Хочу подключить дополнительный сервис <br />"
                    f"ТП: {trf_change.get('name')} стоимостью {trf_change.get('abonent_fee')} руб. [tid {change_tid}]<br />"
                ),
            )
            return {"success": True, "message": "subscribe completed successfully", "code": 200}

        # Real-IP subscription (simplified — mirrors PHP's fast-path).
        cost = self.get_real_ip_cost(int(service.get("tid") or 0), change_tid)
        if float(user.get("balance") or 0.0) < cost:
            return {"success": False, "message": "change failed", "code": 400}
        sid_prev = service.get("sid_prev")
        if not self.tariff_repo.set_tariff_now(
            int(sid_prev) if sid_prev else int(service["sid"]),
            int(service["sid"]),
            change_tid,
        ):
            return {"success": False, "message": "change failed", "code": 400}
        self.logger.info("User of id: %s change tariff to %s.", uid, change_tid)
        self.write_lk_log(
            uid, "Подключение услуги в МЛК", "serviceAdd",
            "",
            {"serviceTid": change_tid, "serviceName": trf_change.get("name")},
        )
        return {"success": True, "message": "completed successfully", "code": 200}


__all__ = ["ServiceService"]
