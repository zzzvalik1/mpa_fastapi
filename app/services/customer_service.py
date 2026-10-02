"""Customer service (mirrors ``App/Controller/CustomerController.php``).

Implements the subscriber / account / suspend / promised-pay / pay-link
flows.  Uses :class:`BaseService` for the shared precheck algorithms.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.core.exceptions import (
    AuthorizationError,
    CustomerError,
    NotFoundError,
)
from app.core.logging import get_logger
from app.repositories.customer_repository import CustomerRepository
from app.repositories.service_repository import ServiceRepository
from app.repositories.tariff_repository import TariffRepository
from app.schemas.common import RUB_CURRENCY
from app.services.base_service import BaseService, PromisedPayPrecheck


class CustomerService(BaseService):
    """High-level customer operations.

    Inherits precheck helpers from :class:`BaseService` and adds the
    concrete business methods that the API endpoints call.
    """

    # ------------------------------------------------------------------ #
    # Builders for response payloads
    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_balance(user: dict[str, Any], precheck: PromisedPayPrecheck) -> dict[str, Any]:
        """Build the ``balance`` block used by ``/subscriber`` responses."""
        date_expire = user.get("date_expire")
        pay_until = None
        ended_at = None
        if date_expire:
            try:
                dt = datetime.fromisoformat(date_expire)
                pay_until = (dt - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
                ended_at = pay_until
            except ValueError:
                pay_until = date_expire
                ended_at = date_expire
        return {
            "total": float(user.get("balance") or 0.0),
            "recommended_pay": float(user.get("rec_fee") or 0.0),
            "pay_until": pay_until,
            "started_at": user.get("date_register"),
            "ended_at": ended_at,
            "promised_pay": {
                "sum": precheck.sum,
                "promised_until": precheck.promised_until,
                "status": precheck.opstatus,
            },
            "currency": RUB_CURRENCY.model_dump(),
        }

    @staticmethod
    def _split_name(name: str | None) -> tuple[str, str]:
        """Return ``(last_name, first_name)`` from a ``"Last First"`` string."""
        if not name:
            return "", ""
        parts = name.split(" ", 1)
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], parts[1]

    def _build_suspend_info(self, user: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        """Return ``(suspend_allow, suspend_info)`` for an account row.

        Args:
            user: The subscriber row.

        Returns:
            A 2-tuple with the allow flag and the suspend info dict.
        """
        suspend_info: dict[str, Any] = {}
        suspend_allow = True
        tarif_type = int(user.get("tarif_type") or 0)
        uid = int(user.get("uid") or 0)

        if tarif_type == 2:
            if self.precheck_unfreeze(uid):
                suspend = self.customer_repo.get_suspend_from(uid) or {}
                suspend_info["suspend_from"] = suspend.get("date_freeze")
                suspend_info["suspend_to"] = suspend.get("date_unfreeze")
                suspend_allow = False
            elif not self.precheck_freeze(uid).status:
                suspend_allow = False
        elif tarif_type == 6:
            if self.precheck_unblock(uid):
                suspend = self.customer_repo.get_date_block(uid) or {}
                suspend_info["suspend_from"] = suspend.get("date_freeze")
                suspend_info["suspend_to"] = suspend.get("date_unfreeze")
                suspend_allow = False
        return suspend_allow, suspend_info

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_subscriber(self, uid: int) -> dict[str, Any]:
        """Return the subscriber payload for ``GET /api/v1/subscriber``.

        Args:
            uid: User id.

        Returns:
            A dict ready to be embedded in the response envelope.

        Raises:
            NotFoundError: If the subscriber cannot be found.
        """
        user = self.customer_repo.find_subscriber_by_uid(uid)
        if not user:
            self.logger.error("User of uid: %s not found.", uid)
            raise NotFoundError("incorrect username")

        self.logger.debug("User of id: %s get query '/subscriber'.", uid)
        precheck = self.precheck_oplatezh(uid)
        last_name, first_name = self._split_name(user.get("name"))
        return {
            "id": str(user["uid"]),
            "code": user.get("pin"),
            "first_name": first_name,
            "last_name": last_name or user.get("name") or "",
            "active_account": {
                "id": str(user["uid"]),
                "number": user.get("pin"),
                "balance": self._build_balance(user, precheck),
            },
        }

    def get_accounts(self, uid: int) -> list[dict[str, Any]]:
        """Return the list of accounts for ``GET /subscriber/accounts``.

        Args:
            uid: User id.

        Returns:
            A list with a single account dict (the original API returns one
            account per subscriber).
        """
        user = self.customer_repo.find_subscriber_by_uid(uid)
        if not user:
            raise NotFoundError("incorrect username")
        self.logger.debug("User of id: %s get query GET '/subscriber/accounts'.", uid)
        precheck = self.precheck_oplatezh(uid)
        suspend_allow, suspend_info = self._build_suspend_info(user)
        return [
            {
                "id": str(user["uid"]),
                "number": user.get("pin"),
                "suspend_allow": suspend_allow,
                "balance": self._build_balance(user, precheck),
                "suspend_info": suspend_info,
            }
        ]

    def get_account(self, uid: int, account_id: int) -> dict[str, Any]:
        """Return a single account for ``GET /subscriber/accounts/{accountId}``.

        Args:
            uid: Authenticated user id.
            account_id: Account id from the path.

        Returns:
            Account dict.

        Raises:
            AuthorizationError: If ``account_id`` does not match ``uid``.
            NotFoundError: If the user cannot be found.
        """
        user = self.customer_repo.find_subscriber_by_uid(uid)
        if not user:
            raise NotFoundError("incorrect username")
        if int(user["uid"]) != account_id:
            self.logger.error("User of accountId: %s not found.", account_id)
            raise AuthorizationError("incorrect accountId")

        self.logger.debug(
            "User of id: %s get query '/subscriber/accounts/%s/'.", uid, account_id
        )
        precheck = self.precheck_oplatezh(uid)
        suspend_allow, suspend_info = self._build_suspend_info(user)
        auto_payment = self.customer_repo.get_recurrent_pay(uid) is not None
        return {
            "id": str(user["uid"]),
            "number": user.get("pin"),
            "suspend_allow": suspend_allow,
            "balance": self._build_balance(user, precheck),
            "auto_payment": auto_payment,
            "suspend_info": suspend_info,
        }

    # ------------------------------------------------------------------ #
    # PATCH /subscriber/accounts/{accountId}
    # ------------------------------------------------------------------ #
    def change_account(
        self,
        uid: int,
        account_id: int,
        action: str,
        date_start: str | None = None,
        date_end: str | None = None,
    ) -> dict[str, Any]:
        """Apply a ``suspend`` / ``unsuspend`` / ``promised-pay`` action.

        Args:
            uid: Authenticated user id.
            account_id: Path account id.
            action: Action name.
            date_start: Optional freeze start (for ``suspend``).
            date_end: Optional freeze end (for ``suspend``).

        Returns:
            A dict with ``success`` / ``message`` / ``code`` keys.

        Raises:
            AuthorizationError: If the account id does not match.
            CustomerError: If a precheck fails.
        """
        user = self.customer_repo.find_subscriber_by_uid(uid)
        if not user:
            raise NotFoundError("incorrect username")
        if int(user["uid"]) != account_id:
            raise AuthorizationError("incorrect accountId")

        service = self.service_repo.get_primary_service(uid)
        if not service:
            raise CustomerError("primary service not found")

        self.logger.debug(
            "User of id: %s get query PATCH '/subscriber/accounts/%s/', action %s.",
            uid, account_id, action,
        )

        if action == "suspend":
            return self._do_suspend(user, service, date_start, date_end)
        if action == "unsuspend":
            return self._do_unsuspend(user, service)
        if action == "promised-pay":
            return self._do_promised_pay(user, service)
        raise CustomerError("incorrect action input")

    # ------------------------------------------------------------------ #
    # Action implementations
    # ------------------------------------------------------------------ #
    def _do_suspend(
        self,
        user: dict[str, Any],
        service: dict[str, Any],
        date_start: str | None,
        date_end: str | None,
    ) -> dict[str, Any]:
        """Execute a suspend (freeze or voluntary block) action."""
        uid = int(user["uid"])
        duration = int(service.get("duration") or 0)
        if not date_start:
            date_start = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")
        if not date_end:
            date_end = (datetime.now() + timedelta(days=91)).strftime("%Y-%m-%d 00:00:00")

        if duration == 2:
            res = self.precheck_freeze(uid, date_start, date_end)
            if not res.status:
                return {"success": False, "message": res.info, "code": 400}
            self.customer_repo.update_customer(
                uid, {"date_freeze": date_start, "date_unfreeze": date_end}
            )
            date_expire = service.get("date_expire")
            if date_expire:
                try:
                    new_expire = datetime.fromisoformat(date_expire).strftime("%Y-%m-%d 04:00:00")
                except ValueError:
                    new_expire = date_expire
                self.service_repo.update_service(int(service["sid"]), {"date_expire": new_expire})
            self.logger.info(
                "User of id: %s frozen service success from %s to %s.", uid, date_start, date_end
            )
            self.write_lk_log(
                uid, "Заказ заморозки в МЛК", "freezeAdd",
                "",
                {"dateStart": date_start, "dateEnd": date_end},
            )
            return {"success": True, "message": "User frozen service success.", "code": 200}

        if duration == 6:
            res = self.precheck_block(uid, date_start, date_end)
            if not res.status:
                self.logger.error(
                    "Block failed: %s; User of id: %s blocked account from %s to %s.",
                    res.error, uid, date_start, date_end,
                )
                return {"success": False, "message": res.error or "block failed", "code": 400}
            self.customer_repo.set_block(uid, date_start, date_end)
            self.logger.info(
                "User of id: %s blocked account from %s to %s.", uid, date_start, date_end
            )
            self.write_lk_log(
                uid, "Заказ добровольной блокировки в МЛК", "freezeAdd",
                "",
                {"dateStart": date_start, "dateEnd": date_end},
            )
            return {"success": True, "message": "User blocked service success.", "code": 200}

        return {"success": False, "message": "block failed2", "code": 400}

    def _do_unsuspend(self, user: dict[str, Any], service: dict[str, Any]) -> dict[str, Any]:
        """Execute an unsuspend (unfreeze / unblock) action."""
        uid = int(user["uid"])
        duration = int(service.get("duration") or 0)

        if duration == 2:
            if not self.precheck_unfreeze(uid):
                return {"success": False, "message": "blocked is empty", "code": 400}
            date_freeze_raw = user.get("date_freeze")
            date_unfreeze_raw = user.get("date_unfreeze")
            is_frozen = bool(int(user.get("is_frozen") or 0))
            today = datetime.now()
            tomorrow = today + timedelta(days=1)
            try:
                df = datetime.fromisoformat(date_freeze_raw) if date_freeze_raw else None
                du = datetime.fromisoformat(date_unfreeze_raw) if date_unfreeze_raw else None
            except ValueError:
                df = du = None

            if df and du and df < tomorrow and du > today and is_frozen:
                service_expire = service.get("date_expire")
                try:
                    se = datetime.fromisoformat(service_expire) if service_expire else None
                except ValueError:
                    se = None
                if se and du:
                    new_expire = (se - (du - today)).strftime("%Y-%m-%d")
                    self.service_repo.update_service(int(service["sid"]), {"date_expire": new_expire})
                    self.service_repo.update_service_add(int(service["sid"]), {"date_expire": new_expire})
                self.customer_repo.update_customer(uid, {"date_unfreeze": today.strftime("%Y-%m-%d")})
                self.logger.info("User of id: %s. Unblocked service success.", uid)
                self.write_lk_log(
                    uid, "Отмена заморозки в МЛК", "freezeDel",
                    {"dateStart": (df.strftime("%d-%m-%Y") if df else ""),
                     "dateEnd": today.strftime("%d-%m-%Y")},
                    "",
                )
                return {"success": True, "message": "User unblocked service success.", "code": 200}
            if df and df >= tomorrow:
                self.customer_repo.update_customer(uid, {"date_freeze": None, "date_unfreeze": None})
                self.logger.info("User of id: %s. Unblocked service success.", uid)
                return {"success": True, "message": "User unblocked service success.", "code": 200}
            return {"success": False, "message": "unblock failed", "code": 400}

        if duration == 6:
            if not self.precheck_unblock(uid):
                return {"success": False, "message": "blocked is empty", "code": 400}
            period = self.customer_repo.get_date_block(uid) or {}
            self.customer_repo.unblock(uid)
            self.logger.info("User of id: %s. Unblocked service success.", uid)
            today_str = today.strftime("%Y-%m-%d")
            df_raw = period.get("date_freeze")
            du_raw = period.get("date_unfreeze")
            try:
                df = datetime.fromisoformat(df_raw).strftime("%d-%m-%Y") if df_raw else ""
            except ValueError:
                df = ""
            self.write_lk_log(
                uid, "Отмена добровольной блокировки в МЛК", "freezeDel",
                {"dateStart": df, "dateEnd": (du_raw or "")},
                {"dateStart": df, "dateEnd": today_str},
            )
            return {"success": True, "message": "User unblocked service success.", "code": 200}

        return {"success": False, "message": "blocked is empty", "code": 400}

    def _do_promised_pay(self, user: dict[str, Any], service: dict[str, Any]) -> dict[str, Any]:
        """Execute a promised-pay request."""
        uid = int(user["uid"])
        precheck = self.precheck_oplatezh(uid)
        if precheck.opstatus != "available":
            return {"success": False, "message": "trustedFee failed", "code": 400}

        tariff = self.tariff_repo.get_tariff_by_tid(int(service.get("tid") or 0)) or {}
        average_pay = self.customer_repo.get_average_pay(uid)
        promised_pay = float(user.get("promised_pay") or 0.0)
        subtype = int(tariff.get("subtype") or 0)
        date_expire = service.get("date_expire")

        new_id = self.customer_repo.insert_oplatezhq(
            uid, int(service["sid"]), date_expire, promised_pay, subtype, average_pay
        )
        if new_id is None:
            return {"success": False, "message": "change failed", "code": 400}
        self.logger.info("User of id: %s set trustedfee.", uid)
        self.write_lk_log(uid, "Заказ обещанного платежа в МЛК", "trustedFeeAdd")
        return {
            "success": True,
            "message": "User ordered a service trustedfee success.",
            "code": 200,
        }

    # ------------------------------------------------------------------ #
    # Pay links
    # ------------------------------------------------------------------ #
    def get_pay_link(self, uid: int, amount: float) -> dict[str, Any]:
        """Return the payment URL payload for ``GET /pay-link``."""
        user = self.customer_repo.find_subscriber_by_uid(uid)
        if not user:
            raise NotFoundError("incorrect username")
        self.logger.debug(
            "User of get query '/subscriber/accounts/%s/pay-link/?amount=%s'.", uid, amount
        )
        pin = user.get("pin") or ""
        return {
            "pay_link": f"https://rsb.ru/reg.php/?source=mlk&pin={pin}&amount={amount}",
            "success_redirect_url": "https://www.star.ru/payment/?rsb_status=OK",
            "failure_redirect_url": "https://www.star.ru/payment/?rsb_status=FAILED",
        }

    def get_auto_pay_link(self, uid: int, amount: float) -> dict[str, Any]:
        """Return the auto-payment URL payload for ``GET /auto-payment-link``."""
        user = self.customer_repo.find_subscriber_by_uid(uid)
        if not user:
            raise NotFoundError("incorrect username")
        pin = user.get("pin") or ""
        return {
            "auto-payment-link": (
                f"https://rsb.ru/reg.php/?source=mlk&pin={pin}&amount={amount}&cmd=register_regular"
            ),
            "success_redirect_url": "https://www.star.ru/payment/?rsb_status=OK",
            "failure_redirect_url": "https://www.star.ru/payment/?rsb_status=FAILED",
        }

    def set_auto_pay_off(self, uid: int) -> dict[str, Any]:
        """Disable the auto-payment binding for the user (``GET /auto-payment-off``)."""
        user = self.customer_repo.find_subscriber_by_uid(uid)
        if not user:
            raise NotFoundError("incorrect username")
        deleted = self.customer_repo.delete_recurrent_pay(uid)
        if not deleted:
            return {"success": False, "data": "mistake", "message": False, "code": 401}
        self.logger.debug("User of get query '/subscriber/accounts/%s/auto-payment-off'.", uid)
        self.write_lk_log(uid, "Отключение услуги автоплатеж в МЛК", "autoPay")
        return {
            "success": True,
            "data": "Auto-payment is turned off",
            "message": "success",
            "code": 200,
        }

    def promised_pay_terms(self, uid: int) -> str:
        """Return the static HTML describing the promised-pay terms."""
        user = self.customer_repo.find_subscriber_by_uid(uid)
        if not user:
            raise NotFoundError("incorrect username")
        return (
            "<div>"
            "<p>Обещанный платеж – это сервис, позволяющий Вам оперативно "
            "восстановить доступ к сети Интернет, даже если на счету закончились "
            "деньги, и нет возможности своевременно пополнить счет. Теперь Вы не "
            "зависите от обстоятельств и сами можете продлить срок оказания услуг "
            "на 4 календарных дня до внесения денежных средств.</p>"
            "<p>При заказе услуги \"Обещанный платеж\" срок до окончания текущего "
            "расчетного периода увеличивается на 4 дня, со списанием соответствующей "
            "абонентской платы в за 4 дня.</p>"
            "<p>Погашение обещанного платежа должно быть произведено в течение "
            "72-х часов (3-х суток), в противном случае предоставление услуг "
            "блокируется.</p>"
            "<p>Услуга может быть использована не более одного раза за расчетный "
            "период.</p>"
            "<p>После внесения денег на счет сперва погашается кредит, потом "
            "снимаются деньги за следующий расчетный период.</p>"
            "</div>"
        )


__all__ = ["CustomerService"]
