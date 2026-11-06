"""Логика расписания: рабочие дни, генерация слотов, доступность."""
from datetime import date, datetime, time, timedelta

import config
import database as db

RU_WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
RU_MONTHS = [
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


def _parse_hours() -> tuple:
    """Разбирает WORKING_HOURS вида '10:00-20:00' в (time, time)."""
    try:
        start_s, end_s = config.WORKING_HOURS.split("-")
        sh, sm = [int(x) for x in start_s.strip().split(":")]
        eh, em = [int(x) for x in end_s.strip().split(":")]
        return time(sh, sm), time(eh, em)
    except Exception:
        return time(10, 0), time(20, 0)


def is_working_day(day: date) -> bool:
    return day.isoweekday() in config.WORKING_DAYS


def available_dates() -> list:
    """Рабочие дни на горизонте бронирования, начиная с сегодня."""
    today = date.today()
    out = []
    for offset in range(config.BOOKING_HORIZON_DAYS):
        day = today + timedelta(days=offset)
        if is_working_day(day):
            out.append(day)
    return out


def _all_slots(day: date, duration: int) -> list:
    """Все теоретические слоты дня с шагом SLOT_STEP_MIN."""
    start_t, end_t = _parse_hours()
    cursor = datetime.combine(day, start_t)
    closing = datetime.combine(day, end_t)
    step = timedelta(minutes=config.SLOT_STEP_MIN)

    slots = []
    while cursor + timedelta(minutes=duration) <= closing:
        slots.append(cursor)
        cursor += step
    return slots


def slots_for_date(day: date, duration: int) -> list:
    """Свободные слоты (ISO-строки) на дату: без занятых и без слишком близких."""
    now = datetime.now()
    min_start = now + timedelta(minutes=config.MIN_LEAD_MINUTES)

    out = []
    for cursor in _all_slots(day, duration):
        if cursor < min_start:
            continue
        iso = cursor.isoformat(timespec="minutes")
        if db.is_slot_busy(iso, duration):
            continue
        out.append(iso)
    return out


def format_date(day: date) -> str:
    return "{} {} {}".format(RU_WEEKDAYS[day.weekday()], day.day, RU_MONTHS[day.month])


def format_slot(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%H:%M")


def format_slot_long(iso: str) -> str:
    dt = datetime.fromisoformat(iso)
    return "{} в {}".format(format_date(dt.date()), dt.strftime("%H:%M"))
