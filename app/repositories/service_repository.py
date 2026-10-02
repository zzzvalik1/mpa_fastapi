"""Service repository (mirrors ``App/Service/Service.php``)."""

from __future__ import annotations

from typing import Any

from app.repositories.base import BaseRepository


class ServiceRepository(BaseRepository):
    """Read / write access to the ``SERVICE`` / ``RESOURCE`` tables."""

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #
    def get_actual_services(self, uid: int) -> list[dict[str, Any]]:
        """Return all active services (primary + additional) for the user.

        Args:
            uid: Customer id.

        Returns:
            A list of dicts (one per service).  Empty list if none.
        """
        sql = """
            SELECT
                s.sid                        AS serviceId,
                s.date_register,
                s.date_expire,
                IF(s.parent_sid IS NULL, 1, 0) AS isPrimary,
                tn.name                       AS nextTariffName,
                tn.abonent_fee                AS nextTariffFee,
                tn.tid                        AS nextTariffId,
                IF(tn.duration IN (1,3,6), 'month',
                   IF(tn.duration = 2, '30 day',
                      IF(tn.duration IN (4,5), 'daytime', 'unknown'))) AS nextTariffDuration,
                tn.speedlimit                 AS nextTariffSpeed,
                s.prolong,
                s.`status`                    AS codeStatus,
                IF(s.`status` = 1, 'Услуга оказывается',
                   IF(s.`status` IN (2,3), 'Услуга заблокирована',
                      IF(s.`status` = 4, 'Услуга просрочена',
                         IF(s.`status` = 5, 'Услуга заморожена',
                            IF(s.`status` = 0, 'Новый клиент',
                               IF(s.`status` = 6, 'Нет услуг', 'Неизвестно')))))) AS status,
                t.tid                         AS tariffId,
                t.duration,
                IF(t.duration IN (1,3,6), 'month',
                   IF(t.duration = 2, '30 day',
                      IF(t.duration IN (4,5), 'daytime', 'unknown'))) AS tariffDuration,
                s.tid_next                    AS tariffIdNext,
                t.name                        AS tariffName,
                t.speedlimit                  AS tariffSpeed,
                t.type                        AS tariffTypeCode,
                t.abonent_fee                 AS tariffFee,
                r.client_address              AS serviceIP,
                IF(t.`type` IN (1,8), 'type_inet',
                   IF(t.`type` IN (28,29), 'type_tv',
                      IF(t.`type` IN (9,24,31), 'type_serv', 'type_misc'))) AS type,
                ttt.vcCaption                 AS tariffType,
                r.service_info,
                s.process,
                r.server_dir,
                d.discount
            FROM SERVICE s
            JOIN TARIF tn              ON s.tid_next = tn.tid
            JOIN TARIF_DURATION td2    ON tn.duration = td2.id
            JOIN TARIF t               ON s.tid = t.tid
            JOIN TARIF_DURATION td     ON t.duration = td.id
            JOIN RESOURCE r            ON r.sid = s.sid
            LEFT JOIN `TARIF_TYPES` ttt ON (ttt.typeid = t.type)
            LEFT JOIN `TARIF_TYPES` tttn ON (tttn.typeid = tn.type)
            LEFT JOIN (
                SELECT uid, MAX(discount) AS discount
                FROM DISCOUNT
                WHERE uid = :uid2
            ) d ON (s.uid = d.uid)
            WHERE s.uid = :uid
              AND s.process != 2
              AND r.pid IN (12, 6, 14, 18, 19, 25, 32, 33)
            GROUP BY s.sid
        """
        return self._fetchall(sql, {"uid": uid, "uid2": uid})

    def get_primary_service(self, uid: int) -> dict[str, Any] | None:
        """Return the user's primary service (``parent_sid IS NULL``)."""
        sql = """
            SELECT *,
                   IF(t.duration IN (1,3,6), 'month',
                      IF(t.duration = 2, '30 day',
                         IF(t.duration IN (4,5), 'daytime', 'unknown'))) AS tariffDuration
            FROM `SERVICE`
            JOIN TARIF t ON `SERVICE`.tid = t.tid
            WHERE `parent_sid` IS NULL
              AND `process` != 2
              AND `uid` = :uid
        """
        return self._fetchone(sql, {"uid": uid})

    def get_services_by_uid(self, uid: int) -> list[dict[str, Any]]:
        """Return every ``SERVICE`` row for the user (primary + child)."""
        sql = "SELECT * FROM SERVICE WHERE `uid` = :uid"
        return self._fetchall(sql, {"uid": uid})

    def get_service_by_sid(self, sid: int) -> dict[str, Any] | None:
        """Return a single ``SERVICE`` row by ``sid``."""
        sql = "SELECT * FROM SERVICE WHERE `sid` = :sid"
        return self._fetchone(sql, {"sid": sid})

    def get_current_period(self, uid: int) -> dict[str, Any] | None:
        """Return the user's current billing period (start / end)."""
        sql = """
            SELECT DATE(`date_register`) AS dateStart, DATE(`date_expire`) AS dateEnd
            FROM SERVICE
            WHERE `parent_sid` IS NULL
              AND `uid` = :uid
              AND `process` != '2'
        """
        return self._fetchone(sql, {"uid": uid})

    def get_parent_sid(self, uid: int, tid: int) -> int:
        """Return the parent_sid (or sid) of the service holding the given tid."""
        sql = """
            SELECT parent_sid, sid
            FROM SERVICE
            WHERE `tid` = :tid
              AND `uid` = :uid
              AND `process` != '2'
        """
        row = self._fetchone(sql, {"uid": uid, "tid": tid})
        if not row:
            return 0
        return int(row.get("parent_sid") or row.get("sid") or 0)

    def get_day_accounting(self, uid: int) -> int:
        """Return the ``day_accounting`` flag for the user's primary service."""
        sql = """
            SELECT `day_accounting`
            FROM SERVICE
            WHERE `parent_sid` IS NULL
              AND `process` != 2
              AND `uid` = :uid
        """
        row = self._fetchone(sql, {"uid": uid})
        return int((row or {}).get("day_accounting") or 0)

    def get_sum_last_days(self, uid: int, tid: int) -> float:
        """Return the proportional fee for the remaining days."""
        sql = """
            SELECT (t.abonent_fee / (TO_DAYS(s.date_expire) - TO_DAYS(s.date_register)))
                   * (TO_DAYS(s.date_expire) - TO_DAYS(NOW())) AS abonFee
            FROM SERVICE s
            JOIN TARIF t ON (t.tid = :tid)
            WHERE s.uid = :uid
              AND s.`status` BETWEEN 1 AND 3
              AND s.parent_sid IS NULL
            GROUP BY s.uid
        """
        row = self._fetchone(sql, {"uid": uid, "tid": tid})
        return float((row or {}).get("abonFee") or 0.0)

    def is_set_service(self, uid: int, tid: int) -> int:
        """Return the resource id if the user already has the given tid, else 0."""
        sql = """
            SELECT rid
            FROM `RESOURCE`
            WHERE `tid` = :tid
              AND `date_block` IS NULL
              AND `uid` = :uid
        """
        row = self._fetchone(sql, {"uid": uid, "tid": tid})
        return int((row or {}).get("rid") or 0)

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #
    def update_service(self, sid: int, update_data: dict[str, Any]) -> bool:
        """Update arbitrary columns on the ``SERVICE`` table by ``sid``."""
        if not update_data:
            return False
        set_clause = ", ".join(f"`{c}` = :{c}" for c in update_data)
        params = dict(update_data)
        params["sid"] = sid
        sql = f"UPDATE `SERVICE` SET {set_clause} WHERE `sid` = :sid"
        return self._execute(sql, params) >= 0

    def update_service_add(self, parent_sid: int, update_data: dict[str, Any]) -> bool:
        """Update child services of the given parent ``sid``."""
        if not update_data:
            return False
        set_clause = ", ".join(f"`{c}` = :{c}" for c in update_data)
        params = dict(update_data)
        params["parent_sid"] = parent_sid
        sql = f"UPDATE `SERVICE` SET {set_clause} WHERE `parent_sid` = :parent_sid"
        return self._execute(sql, params) >= 0

    def update_resource(self, rid: int, update_data: dict[str, Any]) -> bool:
        """Update arbitrary columns on the ``RESOURCE`` table by ``rid``."""
        if not update_data:
            return False
        set_clause = ", ".join(f"`{c}` = :{c}" for c in update_data)
        params = dict(update_data)
        params["rid"] = rid
        sql = f"UPDATE `RESOURCE` SET {set_clause} WHERE `rid` = :rid"
        return self._execute(sql, params) >= 0

    def unsubscribe(self, parent_sid: int, tid: int) -> bool:
        """Schedule the given additional service for cancellation next period."""
        sql = """
            UPDATE `SERVICE`
            SET `tid_next` = 1000, `prolong` = 0
            WHERE `parent_sid` = :parent_sid AND `tid` = :tid
        """
        return self._execute(sql, {"parent_sid": parent_sid, "tid": tid}) >= 0

    def delete_service(self, uid: int, sid: int) -> bool:
        """Delete a service row."""
        sql = "DELETE FROM `SERVICE` WHERE `sid` = :sid AND `uid` = :uid"
        return self._execute(sql, {"sid": sid, "uid": uid}) > 0

    def insert_service(self, insert_data: dict[str, Any]) -> int | None:
        """Insert a new ``SERVICE`` row from a column → value map."""
        if not insert_data:
            return None
        cols = list(insert_data.keys())
        col_sql = ", ".join(f"`{c}`" for c in cols)
        val_sql = ", ".join(f":{c}" for c in cols)
        sql = f"INSERT INTO `SERVICE` ({col_sql}) VALUES ({val_sql})"
        self._execute(sql, insert_data)
        return self._last_insert_id()

    def insert_resource(self, insert_data: dict[str, Any]) -> int | None:
        """Insert a new ``RESOURCE`` row from a column → value map."""
        if not insert_data:
            return None
        cols = list(insert_data.keys())
        col_sql = ", ".join(f"`{c}`" for c in cols)
        val_sql = ", ".join(f":{c}" for c in cols)
        sql = f"INSERT INTO `RESOURCE` ({col_sql}) VALUES ({val_sql})"
        self._execute(sql, insert_data)
        return self._last_insert_id()


__all__ = ["ServiceRepository"]
