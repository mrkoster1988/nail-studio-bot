"""Smoke-тесты базы: CRUD записи, баллы, защита от двойной записи."""

import os
import tempfile
import unittest

import database as db


class TestDatabase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        cls._tmp.close()
        import config
        config.DB_PATH = cls._tmp.name  # _connect() читает config.DB_PATH
        db.init_db()
        with db.db() as conn:
            cur = conn.execute(
                "INSERT INTO services (title, price, duration, category, is_active, created_at) VALUES ('Test', 100, 60, 'test', 1, '2026-11-03T00:00')")
            cls.service_id = cur.lastrowid
            cur = conn.execute(
                "INSERT OR REPLACE INTO users (tg_id, name, created_at) VALUES (?, 'Test', ?)", (999999, '2026-11-03T00:00'))
            cls.user_id = cur.lastrowid

    @classmethod
    def tearDownClass(cls):
        os.unlink(cls._tmp.name)

    def test_try_add_booking(self):
        slot = '2026-11-20T14:00'
        bid = db.try_add_booking(self.user_id, self.service_id, slot)
        self.assertIsNotNone(bid)

    def test_double_booking_blocked(self):
        slot = '2026-11-20T15:00'
        first = db.try_add_booking(self.user_id, self.service_id, slot)
        second = db.try_add_booking(self.user_id, self.service_id, slot)
        self.assertIsNotNone(first)
        self.assertIsNone(second, 'повторный слот должен быть отклонён')

    def test_slot_freed_after_cancel(self):
        slot = '2026-11-20T16:00'
        bid = db.try_add_booking(self.user_id, self.service_id, slot)
        db.set_booking_status(bid, db.STATUS_CANCELLED)
        again = db.try_add_booking(self.user_id, self.service_id, slot)
        self.assertIsNotNone(again, 'после отмены слот должен быть свободен')

    def test_points(self):
        self.assertEqual(db.get_points(self.user_id), 0)
        db.add_points(self.user_id, 50, 'test')
        self.assertEqual(db.get_points(self.user_id), 50)
        self.assertTrue(db.spend_points(self.user_id, 30))
        self.assertEqual(db.get_points(self.user_id), 20)
        self.assertFalse(db.spend_points(self.user_id, 100), 'баллов не хватает — отказ')


if __name__ == '__main__':
    unittest.main()
