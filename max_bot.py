"""Чат-бот студии в мессенджере MAX.

Два режима (MAX_ENABLED=1):
  - long poll (GET /updates) — для разработки и теста;
  - webhook (POST /subscriptions) — production, HTTPS:443, сертификат
    доверенного центра/Минцифры, secret в заголовке X-Max-Bot-Api-Secret.

Общая база с Telegram и VK ботами: database.py один и тот же.
Документация: https://dev.max.ru/docs-api
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

import config
import database as db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("max")

API = config.MAX_API_BASE.rstrip("/")


def max_api(method: str, payload: dict = None, query: dict = None) -> dict:
    """Вызов метода MAX Bot API. Токен — в заголовке Authorization."""
    if not config.MAX_BOT_TOKEN:
        raise RuntimeError("MAX_BOT_TOKEN не задан")
    url = "{}/{}".format(API, method.lstrip("/"))
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": config.MAX_BOT_TOKEN,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        logger.error("MAX API %s -> HTTP %s", method, exc.code)
        raise


def send_message(user_id: int, text: str, keyboard: list = None) -> None:
    """Отправка сообщения пользователю (не более 2 сообщ/сек — лимит MAX)."""
    payload = {"text": text}
    if keyboard:
        payload["attachments"] = [
            {
                "type": "inline_keyboard",
                "payload": {"buttons": [[b for b in row] for row in keyboard]},
            }
        ]
    try:
        max_api("messages", payload, query={"user_id": user_id})
    except Exception as exc:
        logger.warning("Не удалось отправить MAX сообщение %s: %s", user_id, exc)


def button(text_: str, payload: dict):
    return {"type": "callback", "text": text_, "payload": json.dumps(payload, ensure_ascii=False)}


def link_button(text_: str, url: str):
    return {"type": "link", "text": text_, "url": url}


def main_keyboard() -> list:
    return [
        [button("📅 Записаться", {"cmd": "book"})],
        [button("💅 Каталог", {"cmd": "catalog"})],
        [button("📞 Контакты", {"cmd": "contacts"})],
        [link_button("💬 Telegram-бот студии", "https://t.me/{}".format(config.BOT_USERNAME or "")),
         ],
    ]


def catalog_text() -> str:
    lines = ["💅 Каталог услуг"]
    current = None
    for s in db.list_services():
        if s["category"] != current:
            current = s["category"]
            lines.append("\n{}".format(current))
        lines.append("• {} — {} ₽".format(s["title"], s["price"]))
    return "\n".join(lines)


def contacts_text() -> str:
    return "📞 {}\n📍 {}\n📱 {}".format(
        config.STUDIO_NAME, config.STUDIO_ADDRESS, config.STUDIO_PHONE
    )


def handle_text(user_id: int, text: str) -> None:
    t = (text or "").strip().lower()
    if t in ("start", "начать", "меню"):
        send_message(user_id, "💅 Добро пожаловать в {}! Выберите действие:".format(config.STUDIO_NAME), main_keyboard())
    elif "каталог" in t or "услуг" in t:
        send_message(user_id, catalog_text(), main_keyboard())
    elif "контакт" in t or "адрес" in t:
        send_message(user_id, contacts_text(), main_keyboard())
    else:
        send_message(user_id, "Напишите «меню», чтобы увидеть кнопки.", main_keyboard())


def handle_callback(user_id: int, payload: str) -> None:
    try:
        cmd = json.loads(payload).get("cmd")
    except (json.JSONDecodeError, TypeError):
        cmd = None
    if cmd == "catalog":
        send_message(user_id, catalog_text(), main_keyboard())
    elif cmd == "contacts":
        send_message(user_id, contacts_text(), main_keyboard())
    else:
        send_message(user_id, "Запись открывается в Telegram-боте студии — там удобнее выбирать время.", main_keyboard())


def run_long_poll() -> None:
    """Режим для разработки: GET /updates."""
    db.init_db()
    marker = None
    logger.info("MAX-бот запущен в режиме long poll")
    import time

    while True:
        try:
            query = {"timeout": 30}
            if marker:
                query["marker"] = marker
            resp = max_api("updates", query=query)
            marker = resp.get("marker", marker)
            for update in resp.get("updates", []):
                _dispatch(update)
        except Exception as exc:
            logger.error("MAX long poll error: %s", exc)
            time.sleep(5)


def _dispatch(update: dict) -> None:
    kind = update.get("update_type")
    if kind == "message_created":
        msg = update.get("message", {})
        handle_text(int(msg.get("from", {}).get("user_id", 0)), msg.get("text", ""))
    elif kind == "message_callback":
        cb = update.get("callback", {})
        handle_callback(int(cb.get("user", {}).get("user_id", 0)), cb.get("payload", "{}"))
    elif kind == "bot_started":
        chat = update.get("chat", {}).get("chat_id", 0)
        user_id = update.get("user", {}).get("user_id", chat)
        send_message(user_id, "💅 Спасибо, что начали! Нажмите «меню» или выберите действие.", main_keyboard())


def run_webhook(host: str = "0.0.0.0", port: int = 443) -> None:
    """Production: webhook на HTTPS:443 (сертификат доверенного ЦС/Минцифры).

    Подписка устанавливается методом POST /subscriptions — например:
      curl -X POST "https://platform-api2.max.ru/subscriptions" \\
        -H "Authorization: <token>" \\
        -d '{"url": "https://your-domain.com/webhook",
             "update_types": ["message_created", "bot_started"],
             "secret": "..."}'
    """
    from http.server import BaseHTTPRequestHandler, HTTPServer

    db.init_db()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode()

            if config.MAX_WEBHOOK_SECRET:
                got = self.headers.get("X-Max-Bot-Api-Secret", "")
                if got != config.MAX_WEBHOOK_SECRET:
                    logger.warning("MAX webhook: неверный секрет от %s", self.client_address)
                    self._respond(401, "forbidden")
                    return

            try:
                _dispatch(json.loads(body))
            except Exception as exc:
                logger.error("MAX webhook dispatch error: %s", exc)
            self._respond(200, "ok")

        def _respond(self, code, text):
            data = text.encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    logger.info("MAX webhook-сервер на %s:%s", host, port)
    HTTPServer((host, port), Handler).serve_forever()


def main() -> None:
    if not config.MAX_ENABLED:
        logger.info("MAX отключён (MAX_ENABLED=0)")
        return
    if not config.MAX_BOT_TOKEN:
        logger.error("MAX_BOT_TOKEN не задан")
        return
    # webhook, если задан секрет, иначе long poll
    if config.MAX_WEBHOOK_SECRET:
        run_webhook()
    else:
        run_long_poll()


if __name__ == "__main__":
    main()
