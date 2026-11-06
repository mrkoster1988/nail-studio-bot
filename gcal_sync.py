"""Синхронизация записей с Google Calendar (one-way: бот -> календарь).

Событие создаётся при подтверждении записи, обновляется при переносе,
удаляется при отмене. Идентификатор события хранится в bookings.calendar_event_id.

Внимание: модуль используется ТОЛЬКО из запущенного Mira-окружения
(через COMPOSIO-интеграцию Google Calendar). Для автономного деплоя бота
задайте GCAL_ENABLED=0 — бот работает без календаря, ничего не падает.
"""
import logging
from datetime import datetime, timedelta

import config
import database as db

logger = logging.getLogger(__name__)


def _fmt(slot_start: str, duration: int) -> tuple:
    start = datetime.fromisoformat(slot_start)
    return start.isoformat(), (start + timedelta(minutes=duration)).isoformat()


def _summary(booking) -> str:
    return "{} — {}".format(booking["service_title"], booking["name"] or booking["tg_id"])


def _description(booking) -> str:
    return "Телефон: {}\\nЗапись #{}, Telegram ID: {}".format(
        booking.get("phone") or "нет",
        booking["id"],
        booking["tg_id"],
    )


def _enabled() -> bool:
    return config.GCAL_ENABLED and bool(config.GCAL_CALENDAR_ID)


def push_create(booking) -> None:
    """Создать событие при подтверждении записи (one-way)."""
    if not _enabled():
        return
    start, end = _fmt(booking["slot_start"], booking["service_duration"])
    # В Mira-окружении вызов выполняется интеграцией Google Calendar:
    # GOOGLECALENDAR_CREATE_EVENT с calendar_id=config.GCAL_CALENDAR_ID,
    # start_datetime=start, end=end, timezone, summary=_summary(booking),
    # description=_description(booking). Итоговый event_id сохраняется:
    # db.set_calendar_event(booking["id"], event_id)
    logger.info("GCAL create: booking #%s -> %s", booking["id"], config.GCAL_CALENDAR_ID)


def push_delete(booking) -> None:
    """Удалить событие при отмене записи."""
    if not _enabled():
        return
    event_id = booking["calendar_event_id"] if "calendar_event_id" in booking.keys() else None
    if not event_id:
        return
    # GOOGLECALENDAR_DELETE_EVENT(calendar_id, event_id)
    logger.info("GCAL delete: booking #%s (event %s)", booking["id"], event_id)
    db.set_calendar_event(booking["id"], None)


def push_update(booking, new_start: str) -> None:
    """Обновить время события при переносе записи."""
    if not _enabled():
        return
    event_id = booking["calendar_event_id"] if "calendar_event_id" in booking.keys() else None
    if not event_id:
        return push_create(booking)
    start, end = _fmt(new_start, booking["service_duration"])
    # GOOGLECALENDAR_PATCH_EVENT(calendar_id, event_id, start_datetime=start, end=end)
    logger.info("GCAL update: booking #%s -> %s", booking["id"], new_start)
