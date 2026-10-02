"""Репозиторий тарифов (порт ``App/Service/Tariff.php``)."""

from __future__ import annotations

from typing import Any

from app.repositories.base import BaseRepository


class TariffRepository(BaseRepository):
    """Чтение/запись таблиц ``TARIF`` / ``BUNDLE`` / ``RESPROTO``."""

    # ------------------------------------------------------------------ #
    # Lookups
    # ------------------------------------------------------------------ #
    def is_blocked_change_tariff(self, uid: int) -> int:
        """Вернуть ``1``, если пользователю запрещена смена тарифов, иначе ``0``."""
        sql = """
            SELECT `data`
            FROM `CUSTOMER_OPTIONS`
            WHERE `uid` = :uid
              AND `type` = 20
              AND `data` = '1'
        """
        row = self._fetchone(sql, {"uid": uid})
        return 1 if row else 0

    def find_tariff_without_realip(self, tid: int) -> int:
        """Вернуть ``tid`` того же тарифа *без* ``[real]`` в названии."""
        sql = """
            SELECT `tid`
            FROM `TARIF`
            WHERE `name` = TRIM(REPLACE(
                (SELECT `name` FROM `TARIF` WHERE tid = :tid), '[real]', ''
            ))
        """
        row = self._fetchone(sql, {"tid": tid})
        return int((row or {}).get("tid") or 0)

    def find_tariff_with_realip(self, tid: int) -> int:
        """Вернуть ``tid`` того же тарифа *с* ``[real]`` в названии."""
        sql = """
            SELECT `tid`
            FROM `TARIF`
            WHERE `name` = CONCAT(TRIM((SELECT `name` FROM `TARIF` WHERE tid = :tid)), ' [real]')
        """
        row = self._fetchone(sql, {"tid": tid})
        return int((row or {}).get("tid") or 0)

    def get_tariff_by_tid(self, tid: int) -> dict[str, Any] | None:
        """Вернуть одну строку тарифа по ``tid``."""
        sql = "SELECT * FROM TARIF WHERE `tid` = :tid"
        return self._fetchone(sql, {"tid": tid})

    def get_details_by_tid(self, tid: int) -> dict[str, Any] | None:
        """Вернуть детальную проекцию тарифа (коэффициент / расписание / ...)."""
        sql = """
            SELECT t.name            AS tariffName,
                   t.tid             AS tariffId,
                   t.abonent_fee,
                   t.duration,
                   !t.switch_allowed AS tariffArchive,
                   t.speedlimit      AS speedIn,
                   t.speedlimitout   AS speedOut,
                   ts.speed          AS speedBonus,
                   t.hybrid          AS trafficBonus,
                   tc.mblimit        AS trafficLimit,
                   tc.coeff          AS trafficCoef,
                   t.type
            FROM TARIF t
            LEFT JOIN TARIF_COEFF tc   ON t.tid = tc.tid
            LEFT JOIN TARIF_SCHEDULE ts ON t.tid = ts.tid
            WHERE t.tid = :tid
        """
        return self._fetchone(sql, {"tid": tid})

    def get_details_active_tarifs(self) -> list[dict[str, Any]]:
        """Вернуть все переключаемые основные тарифы (для эндпоинта списка тарифов)."""
        sql = """
            SELECT t.name           AS tariffName,
                   t.duration,
                   t.tid            AS tariffId,
                   t.abonent_fee    AS abonent_fee,
                   t.speedlimit     AS speedIn,
                   t.speedlimitout  AS speedOut,
                   t.hybrid         AS trafficBonus,
                   tc.mblimit       AS trafficLimit,
                   tc.coeff         AS trafficCoef
            FROM TARIF t
            JOIN TARIF_COEFF tc ON (t.tid = tc.tid)
            WHERE t.switch_allowed = 1
              AND t.is_primary = 1
              AND t.name NOT LIKE '%U%'
            ORDER BY t.name
        """
        return self._fetchall(sql)

    def get_private_switch_allowed_list(self) -> list[dict[str, Any]]:
        """Вернуть облегчённый список тарифов, разрешённых для самостоятельного переключения."""
        sql = """
            SELECT tid, name, abonent_fee
            FROM TARIF
            WHERE switch_allowed = 1
              AND is_primary = 1
              AND name NOT LIKE '%U%'
        """
        return self._fetchall(sql)

    def get_services_tariffs(
        self,
        tids: list[int] | None = None,
        type_: int | None = None,
        sw_al: bool = False,
    ) -> list[dict[str, Any]]:
        """Вернуть каталог тарифов дополнительных услуг.

        Args:
            tids: Необязательный список tid для фильтрации.
            type_: Необязательное значение ``TARIF.type`` для фильтрации.
            sw_al: При ``True`` возвращаются только строки с ``switch_allowed = 1``.

        Returns:
            Список словарей тарифов.
        """
        where = ["1 = 1"]
        params: dict[str, Any] = {}
        if type_ is not None:
            where.append("t.`type` = :type")
            params["type"] = type_
        if tids:
            # Build a safe IN-list with named params (avoid SQL injection).
            placeholders = []
            for i, t in enumerate(tids):
                key = f"tid{i}"
                placeholders.append(f":{key}")
                params[key] = t
            where.append(f"t.`tid` IN ({', '.join(placeholders)})")
        if sw_al:
            where.append("t.`switch_allowed` = 1")

        sql = f"""
            SELECT t.`tid`         AS serviceTid,
                   t.`type`        AS serviceType,
                   t.`name`        AS serviceName,
                   t.`abonent_fee` AS serviceFee,
                   t.`comment`,
                   'manual'        AS typeAddService,
                   tt.vcCaption    AS tariffType,
                   IF(t.`type` IN (1,8), 'type_inet',
                      IF(t.`type` IN (28,29), 'type_tv',
                         IF(t.`type` IN (9,24,31), 'type_serv', 'type_misc'))) AS type
            FROM `TARIF` t
            LEFT JOIN `TARIF_TYPES` tt ON (tt.typeid = t.type)
            WHERE {' AND '.join(where)}
        """
        return self._fetchall(sql, params)

    def is_tids_from_bundle(self, tid: int, tid_next: int) -> int:
        """Вернуть ``bundle.bid``, если оба tid принадлежат одному bundle, иначе 0."""
        sql = """
            SELECT BUNDLE.bid
            FROM `TARIF`
            JOIN `BUNDLE_TARIF` ON (BUNDLE_TARIF.tid = TARIF.tid)
            JOIN `BUNDLE`       ON (BUNDLE.bid = BUNDLE_TARIF.bid)
            WHERE TARIF.tid IN (:tid, :tid_next)
            LIMIT 1
        """
        row = self._fetchone(sql, {"tid": tid, "tid_next": tid_next})
        return int((row or {}).get("bid") or 0)

    def get_resproto(self, tid: int) -> list[dict[str, Any]]:
        """Вернуть строки RESPROTO для данного tid (используется в потоках Smotreshka)."""
        sql = """
            SELECT RESPROTO.*
            FROM RESPROTO
            JOIN TARIF_RESPROTO ON RESPROTO.pid = TARIF_RESPROTO.pid
            WHERE TARIF_RESPROTO.tid = :tid
        """
        return self._fetchall(sql, {"tid": tid})

    def find_by_main_promo(self, tid: int) -> int:
        """Вернуть tid основного тарифа промо (0, если нет)."""
        sql = """
            SELECT tid
            FROM TARIF
            WHERE name = TRIM(REPLACE(
                (SELECT `name` FROM TARIF WHERE tid = :tid), '[promo]', ''
            ))
            LIMIT 1
        """
        row = self._fetchone(sql, {"tid": tid})
        return int((row or {}).get("tid") or 0)

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #
    def set_tariff(self, sid: int, tid_next: int) -> bool:
        """Запланировать смену тарифа на следующий расчётный период."""
        sql = """
            UPDATE `SERVICE`
            SET `tid_next` = :tid_next
            WHERE `sid` = :sid
        """
        return self._execute(sql, {"sid": sid, "tid_next": tid_next}) >= 0

    def set_tariff_now(self, sid_old: int, sid_cur: int, tid: int) -> bool:
        """Применить смену тарифа немедленно (также пересчитывает стоимость).

        Args:
            sid_old: id предыдущей услуги (обновляется ``tid_next``).
            sid_cur: id текущей услуги (обновляются и ``tid``, и ``tid_next``).
            tid: Целевой идентификатор тарифа.

        Returns:
            ``True`` при успехе.
        """
        self._execute(
            "UPDATE `SERVICE` SET tid_next = :tid WHERE `sid` = :sid_old",
            {"sid_old": sid_old, "tid": tid},
        )
        self._execute(
            "UPDATE `SERVICE` SET tid_next = :tid_next, tid = :tid WHERE `sid` = :sid_cur",
            {"sid_cur": sid_cur, "tid_next": tid, "tid": tid},
        )
        self._execute(
            "UPDATE `RESOURCE` SET tid = :tid WHERE `sid` = :sid_cur",
            {"sid_cur": sid_cur, "tid": tid},
        )
        self._execute(
            "CALL recalcCost(:sid)",
            {"sid": sid_cur},
        )
        return True


__all__ = ["TariffRepository"]
