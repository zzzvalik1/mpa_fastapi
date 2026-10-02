"""Fee repository (mirrors ``App/Service/Fee.php``)."""

from __future__ import annotations

from typing import Any

from app.repositories.base import BaseRepository


class FeeRepository(BaseRepository):
    """Read access to the ``FEE`` / ``FREEZING`` tables for transaction history."""

    def get_payments_by_uid(
        self,
        uid: int,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return all payments for the user, optionally filtered by date range.

        Args:
            uid: Customer id.
            start_date: Optional inclusive lower bound (ISO-8601).
            end_date:   Optional inclusive upper bound (ISO-8601).

        Returns:
            A list of ``FEE`` rows as dicts (newest first).
        """
        where = ["`uid` = :uid"]
        params: dict[str, Any] = {"uid": uid}
        if start_date:
            where.append("`date_pay` >= :start")
            params["start"] = start_date
        if end_date:
            where.append("`date_pay` <= :end")
            params["end"] = end_date

        sql = (
            "SELECT * FROM `FEE` WHERE "
            + " AND ".join(where)
            + " ORDER BY `date_pay` DESC"
        )
        return self._fetchall(sql, params)

    def get_freeze_description(self, fid: int) -> str:
        """Return the human-readable description of a freeze-related fee row.

        Args:
            fid: ``FEE.fid`` value.

        Returns:
            Localised description (empty string if not found).
        """
        sql = """
            SELECT CONCAT(
                       'Добровольная блокировка',
                       IF(fz.id IS NULL, '',
                          CONCAT(' ', DATE_FORMAT(fz.date_freeze, '%d-%m-%Y'),
                                 ' - ', DATE_FORMAT(fz.date_unfreeze, '%d-%m-%Y'),
                                 ' (', TO_DAYS(fz.date_unfreeze) - TO_DAYS(fz.date_freeze), ' дн.)')
                       )
                   ) AS description
            FROM FEE f
            LEFT JOIN FREEZING fz
                   ON (fz.uid = f.uid AND TO_DAYS(fz.date_unfreeze) = TO_DAYS(f.date_pay))
            WHERE fid = :fid
        """
        row = self._fetchone(sql, {"fid": fid})
        return str((row or {}).get("description") or "")


__all__ = ["FeeRepository"]
