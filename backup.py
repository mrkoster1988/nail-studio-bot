"""Бэкап SQLite-базы: безопасная копия через backup API."""
import glob
import logging
import os
import sqlite3
import time

import config

logger = logging.getLogger(__name__)


def backup_db(keep: int = 14) -> str:
    """Копирует базу в backups/studio-YYYY-MM-DD.db, хранит последние keep копий."""
    folder = os.path.join(os.path.dirname(config.DB_PATH) or '.', 'backups')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, 'studio-{}.db'.format(time.strftime('%Y-%m-%d')))
    src = sqlite3.connect(config.DB_PATH)
    dst = sqlite3.connect(path)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()
    copies = sorted(glob.glob(os.path.join(folder, 'studio-*.db')))
    for old in copies[:-keep]:
        os.unlink(old)
    logger.info('backup -> %s', path)
    return path


if __name__ == '__main__':
    print(backup_db())
