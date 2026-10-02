"""Fee service (mirrors ``App/Controller/FeeController.php``)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.core.exceptions import AuthorizationError, NotFoundError
from app.core.logging import get_logger
from app.repositories.customer_repository import CustomerRepository
from app.repositories.fee_repository import FeeRepository
from app.repositories.service_repository import ServiceRepository
from app.repositories.tariff_repository import TariffRepository
from app.schemas.common import RUB_CURRENCY
from app.services.base_service import BaseService


class FeeService(BaseService):
    """Builds the transaction history for ``POST .../transactions``."""

    # Map of ``ticket_id`` -> human-readable comment (verbatim from the PHP version).
    _TICKET_COMMENTS: dict[str, str] = {
        "Cyberplat": "Оплата через CyberPlat",
        "CyberTerm": "Оплата через терминалы CyberPlat",
        "Infopay": "Оплата с мобильного телефона",
        "platbox": "Оплата с мобильного телефона",
        "nord_kassir": "Оплата в пункте приема платежей (9-я северная линия, 13к1)",
        "OSMP": "Оплата через QIWI",
        "OSMP (UNL)": "Оплата через QIWI",
        "RoboKassa": "Оплата через RoboKassa",
        "robokassa": "Оплата через RoboKassa",
        "NOFELET": "Оплата через терминалы без комиссии",
        "armax": "Оплата через терминалы без комиссии",
        "patch-in": "Оплата при подключении",
        "Yandex": "Оплата через Яндекс.Деньги",
        "Media_Sber": "Оплата по реквизитам",
        "RSBank": "Оплата банковской картой",
        "Acquiropay": "Оплата банковской картой",
        "SBOnline": "Оплата через Сбербанк Онлайн",
        "SBOnline (UNL)": "Оплата через Сбербанк Онлайн",
        "MKBank": "Оплата через терминалы МКБ",
        "MKBank (UNL)": "Оплата через терминалы МКБ",
        "MobilElement": "Оплата через терминалы Мобил Элемент",
        "Prostaya_Alfa": "Оплата по реквизитам",
        "nln_interkoop": 'Оплата через "ИНТЕРКООПБАНК"',
        "cloudpayments": "Оплата банковской картой",
    }

    def get_transactions(
        self,
        uid: int,
        account_id: int,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return the full transaction history for the given account.

        Args:
            uid: Authenticated user id.
            account_id: Path account id (must equal ``uid``).
            start_date: Optional inclusive lower bound (ISO-8601).
            end_date: Optional inclusive upper bound (ISO-8601).

        Returns:
            A list of transaction dicts sorted newest-first.
        """
        user = self.customer_repo.find_subscriber_by_uid(uid)
        if not user:
            raise NotFoundError("incorrect username")
        if int(user["uid"]) != account_id:
            raise AuthorizationError("incorrect accountId")

        self.logger.debug(
            "User of id: %s get query GET '/subscriber/accounts/%s/transactions'.", uid, account_id
        )

        transactions: list[dict[str, Any]] = []
        payments = self.fee_repo.get_payments_by_uid(uid, start_date, end_date)
        for payment in payments:
            method = int(payment.get("method") or 0)
            sum_paid = float(payment.get("sum_paid") or 0.0)
            ticket_id = payment.get("ticket_id") or ""

            # Income (positive) entries
            if method != 6 and sum_paid >= 0:
                comment = self._resolve_comment(payment, ticket_id, method)
                transactions.append(self._build_row(payment, sum_paid, comment))

            # Expense (negative) entries
            if sum_paid < 0:
                if method == 8:
                    continue
                comment = payment.get("comment") or ""
                if method == 7:
                    comment = "комиссия за оплату услуг через стороннюю платежную систему"
                if comment == "За заморозку":
                    comment = "Оплата услуги Добровольная блокировка"
                if "обещанный платеж" in comment:
                    comment = "Оплата за дополнительные 4 дня (обещанный платеж)"
                transactions.append(self._build_row(payment, sum_paid, comment))

        # Service-period expenses.
        services = self.service_repo.get_services_by_uid(uid)
        today = datetime.now()
        for service in services:
            cost = float(service.get("cost") or 0.0)
            tid = int(service.get("tid") or 0)
            if cost <= 0 or tid == 900:
                continue
            tarif = self.tariff_repo.get_tariff_by_tid(tid) or {}
            d_reg = service.get("date_register")
            d_exp = service.get("date_expire")
            if not d_reg or not d_exp:
                continue
            try:
                dt_reg = datetime.fromisoformat(d_reg)
                dt_exp = datetime.fromisoformat(d_exp)
            except ValueError:
                continue
            d_reg_str = dt_reg.strftime("%Y-%m-%d")
            d_exp_str = dt_exp.strftime("%Y-%m-%d")
            d_reg_comment = dt_reg.strftime("%d-%m-%Y")
            d_exp_comment = dt_exp.strftime("%d-%m-%Y")
            iso_reg = dt_reg.strftime("%Y-%m-%dT%H:%M:%S")
            duration = int(tarif.get("duration") or 0)

            tariff_name = (tarif.get("name") or "").strip()
            base_comment = f"Оплата периода по тарифу '{tariff_name}' ({d_reg_comment} - {d_exp_comment})"

            if duration in (4, 5) and dt_exp > today:
                # Daily breakdown for daytime tariffs.
                days = (today - dt_reg).days
                days_in_month = 30  # approximation matches the PHP version
                pay_for_day = round(float(tarif.get("abonent_fee") or 0.0) / days_in_month, 2)
                for day in range(days + 1):
                    transactions.append({
                        "date": (dt_reg + _days(day)).strftime("%Y-%m-%dT%H:%M:%S"),
                        "debit": pay_for_day,
                        "currency": RUB_CURRENCY.model_dump(),
                        "comment": f"Ежедневное списание по тарифу '{tariff_name}' ({d_reg_comment} - {d_exp_comment})",
                    })
            elif start_date and end_date and start_date <= iso_reg <= end_date:
                transactions.append(self._build_expense_row(iso_reg, cost, base_comment))
            elif start_date and not end_date and iso_reg >= start_date:
                transactions.append(self._build_expense_row(iso_reg, cost, base_comment))
            elif end_date and not start_date and iso_reg <= end_date:
                transactions.append(self._build_expense_row(iso_reg, cost, base_comment))
            elif not start_date and not end_date:
                transactions.append(self._build_expense_row(iso_reg, cost, base_comment))

        # Sort newest-first.
        transactions.sort(key=lambda r: r["date"], reverse=True)
        return transactions

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _resolve_comment(
        self, payment: dict[str, Any], ticket_id: str, method: int
    ) -> str:
        """Return the localised comment for an income payment."""
        if ticket_id in self._TICKET_COMMENTS:
            return self._TICKET_COMMENTS[ticket_id]
        if ticket_id in ("aggregated", "mainoffice", "Шенкурский", "m-lines-office"):
            return " "
        if ticket_id in ("Bonus", "recalc"):
            return payment.get("comment") or ""
        if method == 17 and ticket_id == "freezing":
            return self.fee_repo.get_freeze_description(int(payment.get("fid") or 0))
        if re.match(r"^Terminal[a-z0-9]+$", ticket_id):
            return " "
        if re.match(r"^GTL[0-9-]+$", ticket_id):
            return "Оплата через терминалы без комиссии"
        if re.match(r"^Prs_[0-9]+$", ticket_id, re.IGNORECASE):
            return "Оплата через терминалы без комиссии"
        if re.match(r"^UTP_[0-9]+$", ticket_id):
            return "Оплата через терминалы без комиссии"
        return ticket_id

    @staticmethod
    def _build_row(payment: dict[str, Any], sum_paid: float, comment: str) -> dict[str, Any]:
        """Build an income / generic transaction row."""
        date_pay = payment.get("date_pay")
        iso = (
            datetime.fromisoformat(date_pay).strftime("%Y-%m-%dT%H:%M:%S")
            if date_pay
            else datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        )
        return {
            "date": iso,
            "debit": sum_paid,
            "currency": RUB_CURRENCY.model_dump(),
            "comment": comment,
        }

    @staticmethod
    def _build_expense_row(iso: str, cost: float, comment: str) -> dict[str, Any]:
        """Build a service-period expense row (cost is negated)."""
        return {
            "date": iso,
            "debit": -cost,
            "currency": RUB_CURRENCY.model_dump(),
            "comment": comment,
        }


def _days(n: int):
    """Return a :class:`timedelta` of ``n`` days (kept tiny for readability)."""
    from datetime import timedelta

    return timedelta(days=n)


__all__ = ["FeeService"]
