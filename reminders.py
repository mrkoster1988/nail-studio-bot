"""Планировщик напоминаний: проверяет записи и шлёт уведомления.

Работает как фоновой asyncio-таск: раз в N секунд смотрит в базу,
находит записи, которым пора напомнить, и отправляет сообщения.
Отметки о том, что напоминание уже отправлено, хранятся в БД —
повторов не будет даже после перезапуска.
"""
import asyncio
import logging
from datetime import datetime, timedelta

import config
import database as db

logger = logging.getLogger(__name__)

# Сколько заранее слать напоминания: (ключ, часов до визита, текст)
REMINDER_PLAN = (
    ("day_before", 24, "🌅 *Напоминание*\n\nЗавтра в {when} — {title}.\n\nДо встречи!"),
    ("two_hours", 2, "⏰ *Через 2 часа*\n\nСегодня в {when} — {title}.\n\nЖдём вас!"),
)


def _parse(slot: str) -> datetime:
    return datetime.fromisoformat(slot)


def due_reminders(now: datetime = None) -> list:
    """Записи, которым пора напомнить. Возвращает список (booking, kind, text)."""
    now = now or datetime.now()
    out = []

    for booking in db.all_bookings(limit=500):
        if booking["status"] != db.STATUS_CONFIRMED:
            continue

        try:
            slot = _parse(booking["slot_start"])
        except (TypeError, ValueError):
            continue

        for kind, hours_before, template in REMINDER_PLAN:
            send_at = slot - timedelta(hours=hours_before)
            if send_at <= now < slot:
                if db.reminder_sent(booking["id"], kind):
                    continue
                when = slot.strftime("%d.%m.%Y в %H:%M")
                out.append(
                    (
                        booking,
                        kind,
                        template.format(when=when, title=booking["service_title"]),
                    )
                )
                break
    return out


async def reminder_loop(bot, interval: int = 60):
    """Фоновый цикл: проверяет расписание и шлёт напоминания."""
    logger.info("Планировщик напоминаний запущен (интервал %s c)", interval)
    await asyncio.sleep(5)

    while True:
        try:
            for booking, kind, text in due_reminders():
                tg_id = booking["tg_id"]
                try:
                    await bot.send_message(tg_id, text, parse_mode="HTML")
                    db.mark_reminder_sent(booking["id"], kind)
                    logger.info(
                        "Напоминание %s отправлено: запись #%s",
                        kind, booking["id"],
                    )
                except Exception as exc:
                    logger.warning(
                        "Не удалось отправить напоминание %s для записи #%s: %s",
                        kind, booking["id"], exc,
                    )
        except Exception as exc:
            logger.error("Ошибка в цикле напоминаний: %s", exc)

        await asyncio.sleep(interval)


async def daily_digest(bot, hour: int = 9):
    """Ежедневный дайджест админу: записи на сегодня и завтра."""
    logger.info("Дайджест админа запущен (час %s)", hour)

    while True:
        now = datetime.now()
        if now.hour == hour and now.minute < 2:
            await _send_digest(bot, now)
            # ежедневный бэкап базы сразу после дайджеста
            try:
                import backup
                backup.backup_db()
            except Exception as exc:
                logger.error("Бэкап не удался: %s", exc)
            await asyncio.sleep(120)
        else:
            await asyncio.sleep(30)


async def _send_digest(bot, now: datetime):
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    rows = db.bookings_for_date(today) + db.bookings_for_date(tomorrow)
    if not rows:
        text = "🗓 *Расписание на сегодня*\n\nНа сегодня и завтра записей нет."
    else:
        lines = ["🗓 *Расписание на сегодня и завтра*\n"]
        revenue = 0
        today = now.strftime("%Y-%m-%d")
        for b in rows:
            lines.append(
                "{} {} — {} ({} ₽)".format(
                    db.STATUS_ICONS.get(b["status"], "•"),
                    b["slot_start"][11:16],
                    b["service_title"],
                    b["service_price"],
                )
            )
            if b["status"] == db.STATUS_CONFIRMED and str(b["slot_start"])[:10] == today:
                revenue += b["service_price"]
        if revenue:
            lines.append("\n💰 Ожидаемая выручка сегодня: *{} ₽*".format(revenue))
        text = "\n".join(lines)

    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception as exc:
            logger.warning("Не удалось отправить дайджест админу %s: %s", admin_id, exc)
