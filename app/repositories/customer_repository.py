"""Репозиторий клиентов (порт ``App/Service/Customer.php``).

Каждый метод — прямой порт исходных SQL-запросов, типизированный для
возврата обычных Python-словарей (вместо PHP-объектов ``stdClass``).
``None`` используется там, где оригинал возвращал пустой ``stdClass``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository):
    """Чтение/запись таблиц ``CUSTOMER`` и связанных."""

    # ------------------------------------------------------------------ #
    # Lookups
    # ------------------------------------------------------------------ #
    def find_customer_by_pin(self, pin: str) -> dict[str, Any] | None:
        """Вернуть одного клиента по 6-значному PIN.

        Args:
            pin: 6-значный PIN-код.

        Returns:
            Строка клиента как словарь или ``None``, если не найден.
        """
        sql = """
            SELECT *
            FROM `CUSTOMER`
            WHERE `pin` = :pin
              AND `ctype` IN (0, 3, 4)
              AND `status` != 4
        """
        return self._fetchone(sql, {"pin": pin})

    def find_customer_by_uid(self, uid: int) -> dict[str, Any] | None:
        """Вернуть одного клиента по ``uid`` со склеенными адресом / телефонами.

        Args:
            uid: Уникальный идентификатор клиента.

        Returns:
            Строка клиента как словарь или ``None``, если не найден.
        """
        sql = """
            SELECT *,
                   CONCAT(street, ', ', house, ', ', flat) AS address,
                   CONCAT(phone, ', ', phoneMob)            AS phones
            FROM `CUSTOMER`
            WHERE `uid` = :uid
              AND `ctype` IN (0, 3, 4)
              AND `status` != 4
        """
        return self._fetchone(sql, {"uid": uid})

    def find_subscriber_by_uid(self, uid: int) -> dict[str, Any] | None:
        """Вернуть расширенную проекцию абонента, используемую большинством эндпоинтов.

        Args:
            uid: Уникальный идентификатор клиента.

        Returns:
            Словарь с данными абонента + услуги + тарифа + обещанного платежа
            или ``None``, если абонент не существует.
        """
        sql = """
            SELECT c.uid,
                   c.pin,
                   c.login,
                   c.balance,
                   c.ign_balance,
                   c.name,
                   c.status              AS user_status,
                   c.admin_block,
                   c.date_freeze,
                   c.date_unfreeze,
                   c.is_frozen,
                   c.ctype,
                   c.nvpn,
                   c.email,
                   MAX(f.date_pay)      AS date_promised_pay,
                   (SELECT DATE_FORMAT(MAX(date_pay), '%d-%m-%Y')
                      FROM FEE WHERE uid = c.uid AND method = 5) AS last_pay,
                   s.sid,
                   s.date_register,
                   s.date_expire,
                   s.cost                AS cost_service,
                   s.`status`,
                   t.name                AS tarif_name,
                   t.abonent_fee         AS tarif_cost,
                   t.duration            AS tarif_type,
                   (SELECT SUM(cost) FROM SERVICE
                      WHERE uid = c.uid AND (sid = s.sid OR parent_sid = s.sid)) AS sum_cost_services,
                   ROUND(SUM(IF(t.is_primary = 1,
                                t.abonent_fee * (100 - IFNULL(d.discount, 0)) / 100,
                                t.abonent_fee)) / 30 * 4, 2) AS `promised_pay`,
                   rf.sum                AS rec_fee
            FROM CUSTOMER c
            LEFT JOIN FEE  f  ON (c.uid = f.uid
                                  AND f.comment = 'абон. плата за 4 дня(обещанный платеж)')
            LEFT JOIN SERVICE s ON (c.uid = s.uid)
            LEFT JOIN TARIF t   ON (t.tid = s.tid)
            LEFT JOIN RECOMMENDED_FEE rf ON (c.uid = rf.uid)
            LEFT JOIN (
                SELECT uid, MAX(discount) AS discount
                FROM DISCOUNT
                WHERE uid = :uid2
            ) d ON (c.uid = d.uid)
            WHERE s.sid = (SELECT MAX(sid) FROM SERVICE
                            WHERE uid = c.uid AND parent_sid IS NULL)
              AND c.uid = :uid
              AND c.ctype IN (0, 3, 4)
              AND c.status != 4
        """
        return self._fetchone(sql, {"uid": uid, "uid2": uid})

    # ------------------------------------------------------------------ #
    # Promised pay
    # ------------------------------------------------------------------ #
    def find_op_by_uid(self, uid: int) -> dict[str, Any] | None:
        """Вернуть активную (неоплаченную) строку обещанного платежа, если есть.

        Args:
            uid: Уникальный идентификатор клиента.

        Returns:
            Строка ``OPLATEZH`` как словарь или ``None``.
        """
        sql = """
            SELECT *
            FROM `OPLATEZH`
            WHERE `uid` = :uid
              AND `pogasheno` = 0
        """
        return self._fetchone(sql, {"uid": uid})

    def find_opq_by_sid(self, sid: int) -> dict[str, Any] | None:
        """Вернуть ожидающий запрос обещанного платежа (``OPLATEZHQ``).

        Args:
            sid: Идентификатор услуги.

        Returns:
            Строка ``OPLATEZHQ`` как словарь или ``None``.
        """
        sql = """
            SELECT *
            FROM `OPLATEZHQ`
            WHERE `sid` = :sid
        """
        return self._fetchone(sql, {"sid": sid})

    def insert_oplatezhq(
        self,
        uid: int,
        sid: int,
        date_expire: str,
        promised_pay: float,
        subtype: int,
        average_pay: float,
    ) -> int | None:
        """Вставить новый запрос обещанного платежа.

        Args:
            uid: Идентификатор клиента.
            sid: Идентификатор услуги.
            date_expire: Текущая дата истечения услуги.
            promised_pay: Обещанная сумма.
            subtype: Подтип тарифа.
            average_pay: Средний исторический платёж.

        Returns:
            id новой строки ``OPLATEZHQ`` или ``None`` при неудаче.
        """
        sql = """
            INSERT INTO `OPLATEZHQ` (`uid`, `sid`, `de`, `abon`, `subtype`, `srplatezh`)
            VALUES (:uid, :sid, :date_expire, :promised_pay, :subtype, :average_pay)
        """
        self._execute(
            sql,
            {
                "uid": uid,
                "sid": sid,
                "date_expire": date_expire,
                "promised_pay": promised_pay,
                "subtype": subtype,
                "average_pay": average_pay,
            },
        )
        return self._last_insert_id()

    def get_average_pay(self, uid: int) -> float:
        """Вернуть средний положительный платёж за последние 6 месяцев.

        Args:
            uid: Идентификатор клиента.

        Returns:
            Средний платёж (0, если данных нет).
        """
        sql = """
            SELECT SUM(sum_paid) / 1 AS sum_paid
            FROM `FEE`
            WHERE `uid` = :uid
              AND `date_pay` > DATE_SUB(NOW(), INTERVAL 6 MONTH)
              AND `sum_paid` > 0
              AND `method` <> 6
        """
        row = self._fetchone(sql, {"uid": uid})
        return float((row or {}).get("sum_paid") or 0.0)

    # ------------------------------------------------------------------ #
    # Recurrent (auto) payments
    # ------------------------------------------------------------------ #
    def get_recurrent_pay(self, uid: int) -> dict[str, Any] | None:
        """Вернуть активную привязку рекуррентного платежа RSB, если есть.

        Args:
            uid: Идентификатор клиента.

        Returns:
            Строка ``RECURRENT_PAYS`` как словарь или ``None``.
        """
        sql = """
            SELECT *
            FROM `RECURRENT_PAYS`
            WHERE `uid` = :uid
              AND `provider` = 'RSB'
              AND `confirmed` = 1
        """
        return self._fetchone(sql, {"uid": uid})

    def delete_recurrent_pay(self, uid: int) -> bool:
        """Удалить привязку рекуррентного платежа RSB для пользователя.

        Args:
            uid: Идентификатор клиента.

        Returns:
            ``True``, если удалена хотя бы одна строка.
        """
        sql = """
            DELETE FROM `RECURRENT_PAYS`
            WHERE `uid` = :uid
              AND `provider` = 'RSB'
        """
        return self._execute(sql, {"uid": uid}) > 0

    # ------------------------------------------------------------------ #
    # Freeze / block helpers
    # ------------------------------------------------------------------ #
    def exist_freeze_current_rp(
        self, uid: int, start: str | None, end: str | None
    ) -> int:
        """Посчитать записи о заморозке в текущем расчётном периоде.

        Args:
            uid: Идентификатор клиента.
            start: Начало периода (YYYY-MM-DD).
            end: Конец периода (YYYY-MM-DD).

        Returns:
            Количество соответствующих записей о заморозке.
        """
        sql = """
            SELECT COUNT(`id`) AS count
            FROM `FREEZING`
            WHERE `uid` = :uid
              AND `state` = 2
              AND `date_freeze` >= :start
              AND `date_unfreeze` <= :end
              AND `date_freeze` < `date_unfreeze`
        """
        row = self._fetchone(sql, {"uid": uid, "start": start, "end": end})
        return int((row or {}).get("count") or 0)

    def disallow_freeze_current_rp(
        self, uid: int, start: str | None, end: str | None
    ) -> int:
        """Посчитать записи о заморозке, запрещённо перекрывающие период.

        Args:
            uid: Идентификатор клиента.
            start: Начало периода.
            end: Конец периода.

        Returns:
            Количество запрещённых записей о заморозке.
        """
        sql = """
            SELECT COUNT(`id`) AS count
            FROM `FREEZING`
            WHERE `uid` = :uid
              AND `state` = 2
              AND `date_unfreeze` >= :start
              AND `date_unfreeze` <= :end
              AND `date_freeze` < `date_unfreeze`
        """
        row = self._fetchone(sql, {"uid": uid, "start": start, "end": end})
        return int((row or {}).get("count") or 0)

    def disallow_frozen_current_rp(
        self, uid: int, start: str, end: str
    ) -> int:
        """Посчитать записи freeze_block_log, перекрывающие период.

        Args:
            uid: Идентификатор клиента.
            start: Начало периода.
            end: Конец периода.

        Returns:
            Количество запрещённых замороженных записей.
        """
        sql = """
            SELECT COUNT(`id`) AS count
            FROM `freeze_block_log`
            WHERE `uid` = :uid
              AND `is_term` = 1
              AND (
                (`date_unfreeze` >= :start  AND `date_unfreeze` <= :end)
                OR (`date_freeze` >= :start2 AND `date_freeze`  <= :end2)
              )
              AND `date_freeze` <= `date_unfreeze`
        """
        row = self._fetchone(
            sql,
            {"uid": uid, "start": start, "end": end, "start2": start, "end2": end},
        )
        return int((row or {}).get("count") or 0)

    def is_blocked(self, uid: int) -> int:
        """Вернуть ``1``, если пользователь заблокирован, иначе ``0``."""
        sql = """
            SELECT COUNT(`id`) AS count
            FROM `FREEZING`
            WHERE `uid` = :uid
              AND `state` = 1
        """
        row = self._fetchone(sql, {"uid": uid})
        return int((row or {}).get("count") or 0)

    def is_block_ordered(self, uid: int) -> int:
        """Вернуть ``1``, если запланирована будущая блокировка, иначе ``0``."""
        sql = """
            SELECT `id`
            FROM `FREEZING`
            WHERE `uid` = :uid
              AND `state` = 0
              AND `date_freeze` > :date_freeze
        """
        row = self._fetchone(sql, {"uid": uid, "date_freeze": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        return 1 if row else 0

    def unblock(self, uid: int) -> bool:
        """Завершить текущую заморозку немедленно."""
        sql = """
            UPDATE `FREEZING`
            SET `date_unfreeze` = :date_unfreeze
            WHERE `uid` = :uid
              AND `state` != 2
        """
        return self._execute(
            sql,
            {
                "uid": uid,
                "date_unfreeze": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        ) >= 0

    def allow_unfrozen_now(self, uid: int) -> int:
        """Вернуть ``1``, если клиента можно разморозить прямо сейчас, иначе ``0``."""
        sql = """
            SELECT COUNT(`uid`) AS count
            FROM `CUSTOMER`
            WHERE `uid` = :uid
              AND `date_freeze` IS NOT NULL
              AND `date_unfreeze` IS NOT NULL
              AND `date_freeze` < `date_unfreeze`
        """
        row = self._fetchone(sql, {"uid": uid})
        return int((row or {}).get("count") or 0)

    def get_suspend_from(self, uid: int) -> dict[str, Any] | None:
        """Вернуть ``date_freeze`` / ``date_unfreeze`` из строки ``CUSTOMER``."""
        sql = """
            SELECT `date_freeze`, `date_unfreeze`
            FROM `CUSTOMER`
            WHERE `uid` = :uid
        """
        return self._fetchone(sql, {"uid": uid})

    def get_date_block(self, uid: int) -> dict[str, Any] | None:
        """Вернуть активную/запланированную блокировку заморозки из ``FREEZING``."""
        sql = """
            SELECT `date_freeze`, `date_unfreeze`
            FROM `FREEZING`
            WHERE `uid` = :uid
              AND state < 2
        """
        return self._fetchone(sql, {"uid": uid})

    # ------------------------------------------------------------------ #
    # Discounts
    # ------------------------------------------------------------------ #
    def get_planning_discounts(self, uid: int) -> dict[str, int]:
        """Вернуть максимальную текущую/следующую скидку для пользователя."""
        sql = """
            SELECT IFNULL(MAX(DISCOUNT.discount), 0)     AS discount,
                   IFNULL(MAX(DISCOUNT.next_discount), 0) AS next_discount
            FROM `DISCOUNT`
            WHERE `uid` = :uid
        """
        row = self._fetchone(sql, {"uid": uid})
        return {
            "discount": int((row or {}).get("discount") or 0),
            "next_discount": int((row or {}).get("next_discount") or 0),
        }

    def get_personal_discount(self, uid: int) -> int:
        """Вернуть текущий процент скидки ``usual``."""
        sql = """
            SELECT `discount`
            FROM DISCOUNT
            WHERE `uid` = :uid
              AND `type` = 'usual'
        """
        row = self._fetchone(sql, {"uid": uid})
        return int((row or {}).get("discount") or 0)

    def set_next_personal_discount(self, uid: int, percent: int = 0) -> bool:
        """Установить скидку ``usual`` на следующий период."""
        sql = """
            UPDATE `DISCOUNT`
            SET `next_discount` = :percent
            WHERE `uid` = :uid
              AND `type` = 'usual'
        """
        return self._execute(sql, {"uid": uid, "percent": percent}) >= 0

    # ------------------------------------------------------------------ #
    # Generic updates
    # ------------------------------------------------------------------ #
    def update_customer(self, uid: int, update_data: dict[str, Any]) -> bool:
        """Обновить произвольные столбцы в таблице ``CUSTOMER``.

        Записываются только ключи, присутствующие в :attr:`update_data`;
        значения ``None`` становятся ``NULL``.

        Args:
            uid: Идентификатор клиента.
            update_data: Соответствие столбец → значение.

        Returns:
            ``True``, если инструкция была выполнена (независимо от количества
            затронутых строк).
        """
        if not update_data:
            return False
        set_clause = ", ".join(
            f"`{col}` = :{col}" for col in update_data.keys()
        )
        params = dict(update_data)
        params["uid"] = uid
        sql = f"UPDATE `CUSTOMER` SET {set_clause} WHERE `uid` = :uid"
        return self._execute(sql, params) >= 0

    def set_block(self, uid: int, date_freeze: str, date_unfreeze: str) -> int | None:
        """Вставить новую строку ``FREEZING``, представляющую запланированную блокировку.

        Args:
            uid: Идентификатор клиента.
            date_freeze: Начало заморозки.
            date_unfreeze: Конец заморозки.

        Returns:
            Новый ``FREEZING.id`` или ``None`` при неудаче.
        """
        sql = """
            INSERT INTO `FREEZING` (`uid`, `date_freeze`, `date_unfreeze`, `state`)
            VALUES (:uid, :date_freeze, :date_unfreeze, 0)
        """
        self._execute(
            sql,
            {"uid": uid, "date_freeze": date_freeze, "date_unfreeze": date_unfreeze},
        )
        return self._last_insert_id()

    # ------------------------------------------------------------------ #
    # Real-IP helpers
    # ------------------------------------------------------------------ #
    def get_free_ip_one(self, nid: int | str) -> str:
        """Вернуть свободный IP из MySQL-функции ``getFreeipOne``.

        Args:
            nid: Идентификатор сети.

        Returns:
            IP-адрес как строка (``"0"``, если доступных нет).
        """
        sql = "SELECT getFreeipOne(:nid) AS ip"
        row = self._fetchone(sql, {"nid": nid})
        return str((row or {}).get("ip") or "0")

    def is_ip_exist(self, ip: str) -> int:
        """Вернуть количество ресурсов, уже использующих данный IP."""
        sql = """
            SELECT COUNT(r.rid) AS count
            FROM RESOURCE r
            JOIN TARIF t    ON (t.`tid` = r.`tid` AND t.`name` LIKE '%real%')
            JOIN CUSTOMER c ON (c.`uid` = r.`uid` AND c.`ctype` IN (0,3,4) AND c.`nvpn` = 4)
            WHERE r.`status` < 3
              AND (r.`service_info`  = :ip OR r.`client_address` = :ip)
        """
        row = self._fetchone(sql, {"ip": ip})
        return int((row or {}).get("count") or 0)

    def set_ip(self, sid: int, ip: str) -> bool:
        """Привязать данный IP к ресурсам ``sid``."""
        sql1 = """
            UPDATE `RESOURCE`
            SET `service_info` = :ip
            WHERE `sid` = :sid
              AND `pid` = 1
        """
        sql2 = """
            UPDATE `RESOURCE`
            SET `client_address` = :ip
            WHERE `sid` = :sid
              AND `pid` = 12
        """
        self._execute(sql1, {"sid": sid, "ip": ip})
        self._execute(sql2, {"sid": sid, "ip": ip})
        return True

    def find_email_smotreshka_by_uid(self, uid: int) -> str:
        """Вернуть сохранённый email Smotreshka для пользователя (``''``, если нет)."""
        sql = """
            SELECT `data` AS smotreshkaMail
            FROM `CUSTOMER_OPTIONS`
            WHERE `uid` = :uid
              AND `type` = 42
        """
        row = self._fetchone(sql, {"uid": uid})
        return str((row or {}).get("smotreshkaMail") or "")


__all__ = ["CustomerRepository"]
