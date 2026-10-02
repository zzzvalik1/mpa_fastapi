"""Tariff service (mirrors ``App/Controller/TariffController.php``)."""

from __future__ import annotations

from typing import Any

from app.core.exceptions import AuthorizationError, NotFoundError
from app.core.logging import get_logger
from app.repositories.customer_repository import CustomerRepository
from app.repositories.service_repository import ServiceRepository
from app.repositories.tariff_repository import TariffRepository
from app.schemas.common import RUB_CURRENCY
from app.services.base_service import BaseService


class TariffService(BaseService):
    """Returns the list of tariffs available for switching."""

    def get_tariffs(
        self, uid: int, account_id: int, service_id: int
    ) -> list[dict[str, Any]]:
        """Return the list of tariffs for ``GET .../tariffs``.

        Args:
            uid: Authenticated user id.
            account_id: Path account id.
            service_id: Path service id.

        Returns:
            A list of tariff dicts.
        """
        user = self.customer_repo.find_subscriber_by_uid(uid)
        if not user:
            raise NotFoundError("incorrect username")
        if int(user["uid"]) != account_id:
            raise AuthorizationError("incorrect accountId")

        self.logger.debug(
            "User of id: %s get query GET '/subscriber/accounts/%s/services/%s/tariffs'.",
            uid, account_id, service_id,
        )

        primary = self.service_repo.get_primary_service(uid)
        if not primary:
            return []
        cur_tariff = self.tariff_repo.get_tariff_by_tid(int(primary.get("tid") or 0)) or {}
        svc_view = self.service_repo.get_service_by_sid(service_id)
        if not svc_view or int(svc_view.get("uid") or 0) != uid:
            return []

        get_tariff = self.tariff_repo.get_tariff_by_tid(int(svc_view.get("tid") or 0)) or {}
        if int(primary.get("type") or 0) != int(get_tariff.get("type") or 0):
            return []

        nxt_tariff = self.tariff_repo.get_tariff_by_tid(int(primary.get("tid_next") or 0)) or {}
        if not self.is_allow_change_tariff(uid):
            return []

        active_tariffs = self.tariff_repo.get_details_active_tarifs()
        result: list[dict[str, Any]] = []
        for t in active_tariffs:
            tid = int(t.get("tariffId") or 0)
            if tid in (int(cur_tariff.get("tid") or 0), int(nxt_tariff.get("tid") or 0)):
                continue
            if int(cur_tariff.get("duration") or 0) != int(t.get("duration") or 0):
                continue
            if int(nxt_tariff.get("duration") or 0) != int(t.get("duration") or 0):
                continue

            cur_has_real = "[real]" in (cur_tariff.get("name") or "")
            nxt_has_real = "[real]" in (nxt_tariff.get("name") or "")
            t_has_real = "[real]" in (t.get("tariffName") or "")
            ctype_zero = int(user.get("ctype") or 0) == 0

            fee = float(t.get("abonent_fee") or 0.0)
            name = t.get("tariffName") or ""
            if cur_has_real and nxt_has_real and ctype_zero and t_has_real:
                fee = fee - 150 if fee else 0.0
                name = name.replace("[real]", "").strip()
            elif not cur_has_real and ctype_zero and not t_has_real:
                pass
            elif (
                cur_has_real
                and not nxt_has_real
                and ctype_zero
                and not t_has_real
            ):
                pass
            else:
                continue

            result.append({
                "id": tid,
                "title": name,
                "price": {
                    "total": fee,
                    "currency": RUB_CURRENCY.model_dump(),
                    "frequency": _duration_slug(int(primary.get("duration") or 0)),
                },
                "started_at": primary.get("date_expire"),
            })
        return result


def _duration_slug(duration: int) -> str:
    """Map a duration id to a frequency string (see :mod:`service_service`)."""
    if duration in (1, 3, 6):
        return "month"
    if duration == 2:
        return "30 day"
    if duration in (4, 5):
        return "daytime"
    return "unknown"


__all__ = ["TariffService"]
