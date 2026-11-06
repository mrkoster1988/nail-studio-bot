"""Smoke-тесты планировщика: генерация слотов, рабочие дни, доступность."""

import unittest
from datetime import date, datetime, timedelta

import config
import scheduling


class TestScheduling(unittest.TestCase):

    def test_working_day(self):
        # ожидания выводим из конфига, а не из предположений о студии
        mon, sat, sun = date(2026, 11, 9), date(2026, 11, 7), date(2026, 11, 8)
        for d, name in ((mon, "пн"), (sat, "сб"), (sun, "вс")):
            expected = d.isoweekday() in config.WORKING_DAYS
            self.assertEqual(
                scheduling.is_working_day(d), expected,
                "{}: is_working_day должен совпадать с WORKING_DAYS".format(name),
            )
        # дефолт конфига: пн-сб рабочие, вс выходной
        self.assertIn(6, config.WORKING_DAYS)
        self.assertNotIn(7, config.WORKING_DAYS)

    def test_available_dates_no_past(self):
        dates = scheduling.available_dates()
        self.assertTrue(dates, 'список дат не пуст')
        self.assertGreaterEqual(dates[0], date.today())

    def test_slot_durations(self):
        # слоты укладываются в рабочие часы
        day = date(2026, 11, 10)  # вторник
        slots = scheduling.slots_for_date(day, 60)
        self.assertTrue(slots)
        start, end = config.WORKING_HOURS.split('-')
        for s in slots:
            t = datetime.fromisoformat(s)
            self.assertGreaterEqual(t.strftime('%H:%M'), start.strip())
            self.assertLessEqual((t + timedelta(minutes=60)).strftime('%H:%M'), end.strip())

    def test_format_date(self):
        d = date(2026, 11, 3)
        self.assertIn('ноября', scheduling.format_date(d))

    def test_parse_hours_fallback(self):
        # кривой формат не падает, а откатывается к 10:00-20:00
        orig = config.WORKING_HOURS
        config.WORKING_HOURS = 'мусор'
        try:
            self.assertEqual(scheduling._parse_hours(), (datetime.strptime('10:00', '%H:%M').time(), datetime.strptime('20:00', '%H:%M').time()))
        finally:
            config.WORKING_HOURS = orig


if __name__ == '__main__':
    unittest.main()
