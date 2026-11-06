"""Исходящие webhook-уведомления в внешние системы.

Модуль не зависит от aiogram: его можно использовать и из обычного Python.
Использует стандартную библиотеку (urllib), чтобы не тянуть зависимости.
"""
import hashlib
import hmac
import json
import logging
from urllib import error as urlerror
from urllib import request as urlrequest

import config

logger = logging.getLogger(__name__)


def sign_payload(payload: bytes, secret: str) -> str:
    """HMAC-SHA256 подпись тела запроса в hex."""
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Проверка подписи входящего запроса (constant-time сравнение)."""
    if not secret:
        return True
    if not signature:
        return False
    expected = sign_payload(payload, secret)
    return hmac.compare_digest(expected, signature.strip())


def build_payload(event: str, booking: dict) -> dict:
    """Единый формат тела исходящего webhook."""
    return {
        "event": event,
        "booking": booking,
        "studio": {
            "name": config.STUDIO_NAME,
            "address": config.STUDIO_ADDRESS,
            "phone": config.STUDIO_PHONE,
        },
    }


def send_webhook(event: str, booking: dict) -> bool:
    """Отправляет POST с событием. Возвращает True при успехе.

    Никогда не бросает исключений: сбой внешнего вебхука не должен ломать
    сценарий записи у клиента.
    """
    url = config.OUTGOING_WEBHOOK_URL
    if not url:
        return False

    body = json.dumps(build_payload(event, booking), ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"}

    secret = config.OUTGOING_WEBHOOK_SECRET
    if secret:
        headers["X-Signature-SHA256"] = sign_payload(body, secret)
        headers["X-Signature"] = "sha256=" + headers["X-Signature-SHA256"]

    req = urlrequest.Request(url, data=body, headers=headers, method="POST")
    try:
        with urlrequest.urlopen(req, timeout=config.OUTGOING_WEBHOOK_TIMEOUT) as resp:
            ok = 200 <= resp.status < 300
            if not ok:
                logger.warning("Webhook %s ответил %s", event, resp.status)
            return ok
    except urlerror.HTTPError as exc:
        logger.warning("Webhook %s: HTTP %s", event, exc.code)
    except Exception as exc:
        logger.warning("Webhook %s не доставлен: %s", event, exc)
    return False


def booking_to_dict(booking) -> dict:
    """Приводит строку из БД к словарю для JSON."""
    if booking is None:
        return {}
    if isinstance(booking, dict):
        return booking
    return {
        "id": booking["id"],
        "status": booking["status"],
        "slot_start": booking["slot_start"],
        "comment": booking["comment"],
        "created_at": booking["created_at"],
        "client": {
            "tg_id": booking["tg_id"],
            "name": booking["name"],
            "phone": booking["phone"],
            "username": booking["username"],
        },
        "service": {
            "id": booking["service_id"],
            "title": booking["service_title"],
            "price": booking["service_price"],
            "duration": booking["service_duration"],
        },
    }
