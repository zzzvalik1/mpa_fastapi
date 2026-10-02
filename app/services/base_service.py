"""Base service with shared business logic (the ``precheck*`` helpers).

This module is the Python equivalent of the original
``App/Controller/Base.php`` abstract class.  It owns the freeze / block /
promised-pay / real-IP precheck algorithms and exposes them as plain
methods (no I/O of their own beyond what the repositories provide).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from app.core.logging import get_logger
from app.repositories.customer_repository import CustomerRepository
from app.repositories.fee_repository import FeeRepository
from app.repositories.lklog_repository import LkLogRepository
from app.repositories.service_repository import ServiceRepository
from app.repositories.tariff_repository import TariffRepository
from app.repositories.webclientlog_repository import WebClientLogRepository


# --------------------------------------------------------------------------- #
# Result dataclasses
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class PrecheckResult:
    """Generic boolean precheck result with optional error/info text."""

    status: bool
    error: str | None = None
    info: str = ""


@dataclass(frozen=True, slots=True)
class PromisedPayPrecheck:
    """Result of :meth:`BaseService.precheck_oplatezh`.

    Attributes:
        sum: Recommended amount to pay (``None`` when N/A).
        promised_until: Iso date until which the promise is honoured.
        opstatus: One of ``available``, ``unavailable``, ``expired``, ``taken``.
    """

    sum: float | None
    promised_until: str | None
    opstatus: str


# --------------------------------------------------------------------------- #
# Service
# --------------------------------------------------------------------------- #
@dataclass
class BaseService:
    """Aggregate the six repositories + mailer and run precheck algorithms.

    Instances are created per-request by FastAPI dependencies (see
    :mod:`app.api.v1.dependencies`).  All repository instances share the
    same SQLAlchemy session (the main DB session); the LK / webclient
    repositories receive their own sessions.

    Attributes:
        customer_repo:  Customer repository (main DB).
        service_repo:   Service repository (main DB).
        tariff_repo:    Tariff repository (main DB).
        fee_repo:       Fee repository (main DB).
        lklog_repo:     LK-log repository (LK DB).
        webclientlog_repo: Webclient-log repository (webclient DB).
        client_ip:      IP address of the calling client (for audit logs).
    """

    customer_repo: CustomerRepository
    service_repo: ServiceRepository
    tariff_repo: TariffRepository
    fee_repo: FeeRepository
    lklog_repo: LkLogRepository
    webclientlog_repo: WebClientLogRepository
    client_ip: str = ""

    def __post_init__(self) -> None:
        """Initialise the logger field."""
        self.logger = get_logger()

    # ------------------------------------------------------------------ #
    # Audit log helpers
    # ------------------------------------------------------------------ #
    def write_lk_log(
        self,
        user_id: int | None,
        log_info: str,
        type_: str,
        before: Any = "",
        after: Any = "",
    ) -> int | None:
        """Append a row to ``st_logs`` (LK audit log).

        Args:
            user_id: Acting user id.
            log_info: Short description.
            type_: Type tag (e.g. ``tarifChange``).
            before: Optional "before" state (any JSON-serialisable value).
            after: Optional "after" state.

        Returns:
            New ``st_logs.Id``, or ``None`` if ``log_info`` is empty.
        """
        if not log_info:
            return None
        import json

        return self.lklog_repo.insert_lklog(
            user_id=user_id,
            log_info=log_info,
            ip_addr=self.client_ip,
            before_=json.dumps(before, ensure_ascii=False, default=str) if before else None,
            after_=json.dumps(after, ensure_ascii=False, default=str) if after else None,
            type_=type_ or None,
        )

    def write_client_log(
        self,
        user_id: int | None,
        log_info: str,
        type_: str,
        before: Any = "",
        after: Any = "",
    ) -> int | None:
        """Append a row to ``webclient_logs``.

        Args:
            user_id: Acting user id.
            log_info: Short description.
            type_: Type tag.
            before: Optional "before" state.
            after: Optional "after" state.

        Returns:
            New ``webclient_logs.Id``, or ``None`` if ``log_info`` is empty.
        """
        if not log_info:
            return None
        import json

        return self.webclientlog_repo.insert_webclientlog(
            user_id=user_id,
            log_info=log_info,
            ip_addr=self.client_ip,
            before_=json.dumps(before, ensure_ascii=False, default=str) if before else None,
            after_=json.dumps(after, ensure_ascii=False, default=str) if after else None,
            type_=type_ or None,
        )

    # ------------------------------------------------------------------ #
    # Static helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def mb_speed(kbps: int | None) -> float:
        """Convert a kbps value to Mbps using the original lookup table.

        Args:
            kbps: Speed in kbps (e.g. ``112640``).

        Returns:
            Speed in Mbps (rounded to 1 decimal place where appropriate).
        """
        if kbps is None:
            return 100.0
        table = {112640: 100.0, 0: 100.0}
        if kbps in table:
            return table[kbps]
        if kbps in (25000, 33000, 50000, 60000, 70000):
            return kbps / 1000.0
        return round(kbps / 1024.0, 1)

    @staticmethod
    def is_private_ip(ip: str) -> bool:
        """Return ``True`` if ``ip`` is a private / loopback address.

        Args:
            ip: IPv4 or IPv6 string.

        Returns:
            ``True`` for private addresses.
        """
        if not ip:
            return False
        pattern = re.compile(
            r"^(127\.|192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|::1$)"
        )
        return bool(pattern.match(ip))

    # ------------------------------------------------------------------ #
    # Tariff-change checks
    # ------------------------------------------------------------------ #
    def is_allow_change_tariff(self, uid: int) -> bool:
        """Return ``True`` if the user is currently allowed to change tariff."""
        service = self.service_repo.get_primary_service(uid)
        if not service:
            return False
        tid = int(service.get("tid") or 0)
        tid_next = int(service.get("tid_next") or 0)
        without_realip = self.tariff_repo.find_tariff_without_realip(tid)
        is_blocked = self.tariff_repo.is_blocked_change_tariff(uid)
        is_bundle = self.tariff_repo.is_tids_from_bundle(tid, tid_next)
        no_change_ordered = (tid == tid_next) or (tid_next == without_realip)
        return bool(no_change_ordered and not is_blocked and not is_bundle)

    def is_allow_realip_tariff(self, uid: int) -> bool:
        """Return ``True`` if the user is allowed to switch *to* a real-IP tariff."""
        customer = self.customer_repo.find_customer_by_uid(uid)
        service = self.service_repo.get_primary_service(uid)
        if not customer or not service:
            return False
        tid = int(service.get("tid") or 0)
        tid_next = int(service.get("tid_next") or 0)
        without_realip = self.tariff_repo.find_tariff_without_realip(tid)
        return (tid == tid_next) or (tid_next == without_realip)

    def is_allow_wo_realip_tariff(self, uid: int) -> bool:
        """Return ``True`` if the user is allowed to switch *away* from a real-IP tariff."""
        customer = self.customer_repo.find_customer_by_uid(uid)
        service = self.service_repo.get_primary_service(uid)
        if not customer or not service:
            return False
        tid = int(service.get("tid") or 0)
        tid_next = int(service.get("tid_next") or 0)
        with_realip = self.tariff_repo.find_tariff_with_realip(tid)
        return (tid == tid_next) or (tid_next == with_realip)

    def get_real_ip_cost(self, tid: int, tid_next: int) -> float:
        """Return the cost of adding/removing a real-IP on top of the tariff.

        Args:
            tid: Current tariff id.
            tid_next: Target tariff id.

        Returns:
            ``0.0`` when the tariff is already real-IP or DC-named,
            ``150.00`` otherwise.
        """
        tariff = self.tariff_repo.get_details_by_tid(tid) or {}
        tariff_next = self.tariff_repo.get_details_by_tid(tid_next) or {}
        tariff_with_real_ip = int(tariff.get("tariffId") or 0) in (7664, 7724)
        is_dc = "DC_" in (tariff_next.get("tariffName") or "")
        return 0.0 if (is_dc or tariff_with_real_ip) else 150.0

    def is_exist_in_active_service(self, uid: int, change_tid: int, service_id: int) -> bool:
        """Return ``True`` if the given tid is part of the user's active services."""
        service = self.service_repo.get_primary_service(uid)
        if not service:
            return False
        parent_sid = self.service_repo.get_parent_sid(uid, change_tid)
        sid = int(service.get("sid") or 0)
        return sid == parent_sid and service_id == sid

    # ------------------------------------------------------------------ #
    # Promised-pay precheck
    # ------------------------------------------------------------------ #
    def precheck_oplatezh(self, uid: int) -> PromisedPayPrecheck:
        """Return the promised-pay availability summary for the user.

        Algorithm ported verbatim from ``Base::precheckOplatezh``.

        Args:
            uid: Customer id.

        Returns:
            A :class:`PromisedPayPrecheck` with the sum / until / status.
        """
        user = self.customer_repo.find_subscriber_by_uid(uid)
        service = self.service_repo.get_primary_service(uid)

        # Defaults: "available" — the original also starts optimistic.
        result = PromisedPayPrecheck(
            sum=float(user.get("promised_pay") or 0.0) if user else None,
            promised_until=None,
            opstatus="available",
        )

        if not user or not service:
            return PromisedPayPrecheck(sum=None, promised_until=None, opstatus="unavailable")

        date_expire = user.get("date_expire")
        promised_pay = float(user.get("promised_pay") or 0.0)
        default_until = (
            (datetime.fromisoformat(date_expire) + timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
            if date_expire
            else None
        )
        result = PromisedPayPrecheck(
            sum=promised_pay,
            promised_until=default_until,
            opstatus="available",
        )

        tarif_type = int(user.get("tarif_type") or 0)
        op = self.customer_repo.find_op_by_uid(uid)
        opq = self.customer_repo.find_opq_by_sid(int(service.get("sid") or 0))
        status = int(user.get("user_status") or 0)

        if tarif_type != 2:
            return PromisedPayPrecheck(sum=None, promised_until=None, opstatus="unavailable")
        if op:
            sum_cost_services = float(user.get("sum_cost_services") or 0.0)
            return PromisedPayPrecheck(
                sum=promised_pay + sum_cost_services,
                promised_until=str(date_expire),
                opstatus="expired",
            )
        if opq:
            abon = float(opq.get("abon") or 0.0)
            until = (
                (datetime.fromisoformat(date_expire) - timedelta(days=1)).strftime("%Y-%m-%d")
                if date_expire
                else None
            )
            return PromisedPayPrecheck(sum=abon, promised_until=until, opstatus="taken")

        yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        date_expire_day = (
            datetime.fromisoformat(date_expire).strftime("%Y-%m-%d")
            if date_expire
            else None
        )
        if status not in (3, 2) and date_expire_day != yesterday:
            return PromisedPayPrecheck(sum=None, promised_until=None, opstatus="unavailable")
        return result

    # ------------------------------------------------------------------ #
    # Freeze / block prechecks
    # ------------------------------------------------------------------ #
    FREEZE_DMIN: int = 7
    FREEZE_DMAX: int = 90

    def _default_freeze_dates(self) -> tuple[str, str]:
        """Return the default (start, end) date pair for a freeze."""
        tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        end = (date.today() + timedelta(days=1 + self.FREEZE_DMAX)).strftime("%Y-%m-%d")
        return tomorrow, end

    def _get_planning_costs(self, uid: int, date_start: str) -> float:
        """Compute the projected cost of a freeze that starts after ``date_expire``."""
        service = self.service_repo.get_primary_service(uid)
        if not service:
            return 0.0
        tid = int(service.get("tid") or 0)
        tid_next = int(service.get("tid_next") or 0)
        tariff = self.tariff_repo.get_tariff_by_tid(tid) or {}
        tariff_next = self.tariff_repo.get_tariff_by_tid(tid_next) or {}
        discounts = self.customer_repo.get_planning_discounts(uid)
        date_expire = service.get("date_expire")
        if not date_expire or not tariff or not tariff_next:
            return 0.0

        try:
            ds = datetime.fromisoformat(date_start).date()
            de = datetime.fromisoformat(date_expire).date()
        except ValueError:
            return 0.0
        if ds <= de:
            return 0.0

        cur_fee = float(tariff.get("abonent_fee") or 0.0)
        next_fee = float(tariff_next.get("abonent_fee") or 0.0)
        cur_discount = discounts.get("discount", 0)
        next_discount = discounts.get("next_discount", 0)
        cost_current = round(cur_fee - cur_fee * cur_discount / 100.0, 2)
        cost_next = round(next_fee - next_fee * next_discount / 100.0, 2)

        days_until_block = (ds - de).days
        if days_until_block <= 0:
            return 0.0
        # Approximate month length from today (matches PHP's cal_days_in_month).
        today = date.today()
        days_in_month = (date(today.year, today.month, 1) + timedelta(days=31)).day - 1
        if days_in_month <= 0:
            days_in_month = 30
        periods = -(-days_until_block // days_in_month)  # ceil division
        cost = cost_next if tid != tid_next else cost_current
        return float(periods * cost)

    def precheck_block(
        self,
        uid: int,
        date_start: str | None = None,
        date_end: str | None = None,
    ) -> PrecheckResult:
        """Validate a voluntary block request.

        Args:
            uid: Customer id.
            date_start: Optional freeze start (YYYY-MM-DD).
            date_end:   Optional freeze end   (YYYY-MM-DD).

        Returns:
            :class:`PrecheckResult` with ``status=True`` when allowed.
        """
        if not date_start:
            date_start, _ = self._default_freeze_dates()
        if not date_end:
            _, date_end = self._default_freeze_dates()

        customer = self.customer_repo.find_customer_by_uid(uid)
        service = self.service_repo.get_primary_service(uid)
        if not customer or not service:
            return PrecheckResult(False, error="User not found.")

        tariff = self.tariff_repo.get_tariff_by_tid(int(service.get("tid") or 0)) or {}
        period = self.service_repo.get_current_period(uid)
        blocked = self.customer_repo.is_blocked(uid)
        ordered = self.customer_repo.is_block_ordered(uid)
        period_start = (period or {}).get("dateStart")
        period_end = (period or {}).get("dateEnd")
        exist_freeze = (
            self.customer_repo.exist_freeze_current_rp(uid, period_start, period_end)
            if period_start and period_end
            else 0
        )
        disallow_freeze = (
            self.customer_repo.disallow_freeze_current_rp(uid, period_start, period_end)
            if period_start and period_end
            else 0
        )

        freeze_cost = 0.0
        try:
            ds = datetime.fromisoformat(date_start).date()
            de_expire = datetime.fromisoformat(service.get("date_expire") or "").date()
            if ds > de_expire:
                freeze_cost = self._get_planning_costs(uid, date_start)
        except ValueError:
            pass

        balance = float(customer.get("balance") or 0.0)
        duration = int(tariff.get("duration") or 0)
        service_status = int(service.get("status") or 0)

        try:
            ds = datetime.fromisoformat(date_start).date()
            de = datetime.fromisoformat(date_end).date()
            dmin = ds + timedelta(days=self.FREEZE_DMIN)
            dmax = ds + timedelta(days=self.FREEZE_DMAX)
            tomorrow = date.today() + timedelta(days=1)
        except ValueError:
            return PrecheckResult(False, error="Bad dates period.")

        if duration != 6:
            return PrecheckResult(False, error="Not allow for your primary service.")
        if balance < freeze_cost:
            return PrecheckResult(False, error="Not enough money. Balance equal or less 0")
        if service_status != 1:
            return PrecheckResult(False, error="Primary service is closed.")
        if blocked:
            return PrecheckResult(False, error="You are already blocked.")
        if not (dmin <= de <= dmax):
            return PrecheckResult(False, error="Bad dates period.")
        if ds < tomorrow:
            return PrecheckResult(False, error="Bad start date")
        if exist_freeze or disallow_freeze or ordered:
            return PrecheckResult(False, error="Block has already been used (planning).")
        return PrecheckResult(True)

    def precheck_unblock(self, uid: int) -> bool:
        """Return ``True`` if the user can be unblocked right now."""
        service = self.service_repo.get_primary_service(uid)
        if not service:
            return False
        tariff = self.tariff_repo.get_tariff_by_tid(int(service.get("tid") or 0)) or {}
        if int(tariff.get("duration") or 0) != 6:
            return False
        blocked = self.customer_repo.is_blocked(uid)
        ordered = self.customer_repo.is_block_ordered(uid)
        if blocked == 0 and ordered == 0:
            return False
        return True

    def precheck_freeze(
        self,
        uid: int,
        date_start: str | None = None,
        date_end: str | None = None,
    ) -> PrecheckResult:
        """Validate a freeze request (the "30-day" tariff flavour)."""
        if not date_start:
            date_start, _ = self._default_freeze_dates()
        if not date_end:
            _, date_end = self._default_freeze_dates()

        customer = self.customer_repo.find_customer_by_uid(uid)
        service = self.service_repo.get_primary_service(uid)
        if not customer or not service:
            return PrecheckResult(False, info="User not found.")

        tariff = self.tariff_repo.get_tariff_by_tid(int(service.get("tid") or 0)) or {}
        period = self.service_repo.get_current_period(uid)
        period_start = (period or {}).get("dateStart")
        period_end = (period or {}).get("dateEnd")
        exist_freeze = (
            self.customer_repo.exist_freeze_current_rp(uid, period_start, period_end)
            if period_start and period_end
            else 0
        )
        disallow_frozen = (
            self.customer_repo.disallow_frozen_current_rp(uid, period_start, period_end)
            if period_start and period_end
            else 0
        )

        try:
            ds = datetime.fromisoformat(date_start).date()
            de = datetime.fromisoformat(date_end).date()
        except ValueError:
            return PrecheckResult(False, info="Bad dates period")

        date_expire_raw = service.get("date_expire")
        try:
            date_expire = datetime.fromisoformat(date_expire_raw).date() if date_expire_raw else None
        except ValueError:
            date_expire = None

        tomorrow = date.today() + timedelta(days=1)
        dmin = ds + timedelta(days=self.FREEZE_DMIN)
        dmax = ds + timedelta(days=self.FREEZE_DMAX)

        if int(customer.get("admin_block") or 0):
            return PrecheckResult(False, info="User is admin blocked")
        if int(service.get("status") or 0) not in (1, 3):
            return PrecheckResult(False, info="Primary service is closed.")
        if int(tariff.get("duration") or 0) != 2:
            return PrecheckResult(False, info="Not allow for your primary service.")
        balance = float(customer.get("balance") or 0.0)
        if balance < 0.0 and not int(customer.get("ign_balance") or 0):
            return PrecheckResult(False, info=f"Not enough money. Need {-balance} rub")
        if int(customer.get("status") or 0) not in (1, 2):
            return PrecheckResult(False, info="You are already blocked")
        df_raw = customer.get("date_freeze")
        try:
            date_freeze = datetime.fromisoformat(df_raw).date() if df_raw else None
        except ValueError:
            date_freeze = None
        if date_freeze and date_freeze >= tomorrow:
            return PrecheckResult(False, info="You are already ordered block")
        if ds < tomorrow:
            return PrecheckResult(False, info="Bad start date")
        if not (
            tomorrow <= ds
            and (date_expire is None or ds < date_expire or
                 (int(service.get("status") or 0) == 3 and tomorrow == ds))
            and dmin <= de
            and de <= dmax
        ):
            return PrecheckResult(False, info="Bad dates period")
        if exist_freeze or disallow_frozen:
            return PrecheckResult(False, info="Frozen has already been used.")
        return PrecheckResult(True, info="Frozen is success")

    def precheck_unfreeze(self, uid: int) -> bool:
        """Return ``True`` if the user can be unfrozen right now."""
        return self.customer_repo.allow_unfrozen_now(uid) > 0


__all__ = [
    "BaseService",
    "PrecheckResult",
    "PromisedPayPrecheck",
]
