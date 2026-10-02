"""Репозиторий платежей (порт ``App/Service/Fee.php``)."""

from __future__ import annotations

from typing import Any

from app.repositories.base import BaseRepository


class FeeRepository(BaseRepository):
    """Доступ на чтение к таблицам ``FEE`` / ``FREEZING`` для истории транзакций."""

    def get_payments_by_uid(
        self,
        uid: int,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Вернуть все платежи пользователя, опционально отфильтрованные по диапазону дат.

        Args:
            uid: Идентификатор клиента.
            start_date: Необязательная нижняя граница включительно (ISO-8601).
            end_date:   Необязательная верхняя граница включительно (ISO-8601).

        Returns:
            Список строк ``FEE`` как словари (сначала новые).
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
        """Вернуть человекочитаемое описание строки платежа, связанной с заморозкой.

        Args:
            fid: Значение ``FEE.fid``.

        Returns:
            Локализованное описание (пустая строка, если не найдено).
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
