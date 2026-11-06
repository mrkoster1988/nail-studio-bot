"""Уведомления админам в Telegram из внешних каналов (VK, MAX и т.д.).

Использует чистый Bot API через HTTP — не тянет aiogram в процесс VK/MAX.
"""
import json
import logging
import urllib.request

import config

logger = logging.getLogger(__name__)


def _send_text(chat_id: int, text: str) -> None:
    url = "https://api.telegram.org/bot{}/sendMessage".format(config.BOT_TOKEN)
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as exc:
        logger.warning("TG notify %s fail: %s", chat_id, exc)


def notify_admins_new_booking(title, name, phone, when, source="TG") -> None:
    """Уведомление админам о новой заявке (из любого канала)."""
    text = (
        "\U0001F514 *Новая заявка ({source})*\n\n"
        "\U0001F485 {}\n"
        "\U0001F464 {}\n"
        "\U0001F4F1 {}\n"
        "\U0001F4C5 {}\n\n"
        "Подтвердите в панели: /admin"
    ).format(title, name, phone or "нет", when)
    for admin_id in config.ADMIN_IDS:
        _send_text(int(admin_id), text)
