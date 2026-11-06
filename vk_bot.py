"""VK-бот для сообщества студии: бот + сообщество.

Два режима приёма сообщений (VK_ENABLED=1):
  - long poll (по умолчанию, проще для старта);
  - callback (VK_CONFIRMATION_CODE, сервер должен быть доступен извне).

Использует ту же базу данных, что и Telegram-бот: common ядро database.py.
"""
import json
import logging
import urllib.parse
import urllib.request

import config
import database as db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("vk")


def vk_api(method: str, **params) -> dict:
    """Вызов метода VK API от имени сообщества."""
    if not config.VK_COMMUNITY_TOKEN:
        raise RuntimeError("VK_COMMUNITY_TOKEN не задан")
    params.update(access_token=config.VK_COMMUNITY_TOKEN, v=config.VK_API_VERSION)
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen("https://api.vk.com/method/{}".format(method), data=data, timeout=15) as resp:
        payload = json.loads(resp.read().decode())
    if "error" in payload:
        raise RuntimeError("VK API error: {}".format(payload["error"]))
    return payload["response"]


def send_message(user_id: int, text: str, keyboard: dict = None) -> None:
    """Отправка сообщения участнику сообщества."""
    kwargs = {"peer_id": user_id, "message": text, "random_id": 0}
    if keyboard:
        kwargs["keyboard"] = json.dumps(keyboard, ensure_ascii=False)
    try:
        vk_api("messages.send", **kwargs)
    except Exception as exc:
        logger.warning("Не удалось отправить VK сообщение %s: %s", user_id, exc)


def main_keyboard() -> dict:
    """Главное меню VK-бота (inline-подобные кнопки сообщений сообщества)."""
    return {
        "inline": True,
        "buttons": [
            [{"action": {"type": "callback", "payload": "{\"cmd\":\"book\"}", "label": "📅 Записаться"}}],
            [{"action": {"type": "callback", "payload": "{\"cmd\":\"catalog\"}", "label": "💅 Каталог"}}],
            [{"action": {"type": "callback", "payload": "{\"cmd\":\"contacts\"}", "label": "📞 Контакты"}}],
        ],
    }


# --- FSM-zapis v VK (v pamyati; bot dlya odnoy studii) ----------------------
USER_STATE = {}


def vk_start_booking(user_id):
    USER_STATE[user_id] = {"step": "service"}
    lines = ["\U0001F485 Vyberite uslugu:\n"]
    current = None
    for s in db.list_services():
        if s["category"] != current:
            current = s["category"]
            lines.append("\n{}".format(current))
        lines.append("- {} ({} R)".format(s["title"], s["price"]))
    send_message(user_id, "\n".join(lines), services_keyboard())


def services_keyboard():
    buttons = []
    for s in db.list_services():
        buttons.append([button(s["title"], {"cmd": "pick_service", "service_id": s["id"]})])
    buttons.append([button("Otmena", {"cmd": "cancel_booking"})])
    return buttons


def dates_keyboard(service_id):
    import scheduling
    buttons = []
    for d in scheduling.available_dates()[:14]:
        buttons.append([button(
            scheduling.format_date(d), {"cmd": "pick_date", "service_id": service_id, "day": d.isoformat()}
        )])
    buttons.append([button("Otmena", {"cmd": "cancel_booking"})])
    return buttons


def times_keyboard(service_id, day_iso):
    import scheduling
    from datetime import date
    duration = db.get_service(service_id)["duration"]
    slots = scheduling.slots_for_date(date.fromisoformat(day_iso), duration)
    buttons = [[button(scheduling.format_slot(s), {"cmd": "pick_time", "service_id": service_id, "slot": s})]
               for s in slots[:24]]
    buttons.append([button("Nazad", {"cmd": "pick_service", "service_id": service_id})])
    buttons.append([button("Otmena", {"cmd": "cancel_booking"})])
    return buttons


def vk_confirm(user_id, service_id, slot):
    import scheduling
    svc = db.get_service(service_id)
    USER_STATE[user_id] = {"step": "confirm", "service_id": service_id, "slot": slot}
    text = (
        "Proverte zapis:\n\n"
        "{}\n"
        "{} R\n"
        "{}\n\n"
        "Podtverdit?".format(
            svc["title"], svc["price"], scheduling.format_slot_long(slot)
        )
    )
    send_message(user_id, text, [[
        button("Da", {"cmd": "confirm_yes"}),
        button("Otmena", {"cmd": "cancel_booking"}),
    ]])


def handle_message(user_id: int, text: str) -> None:
    """Простой роутер сообщений: единая точка входа сценариев."""
    t = (text or "").strip().lower()

    if t in ("начать", "start", "меню", "/start"):
        send_message(user_id, "💅 Добро пожаловать в {}! Выберите действие:".format(config.STUDIO_NAME), main_keyboard())
        return
    if t in ("каталог", "услуги"):
        lines = ["💅 Каталог услуг\n"]
        current = None
        for s in db.list_services():
            if s["category"] != current:
                current = s["category"]
                lines.append("\n{}".format(current))
            lines.append("• {} — {} ₽".format(s["title"], s["price"]))
        send_message(user_id, "\n".join(lines), main_keyboard())
        return
    if t in ("контакты", "адрес"):
        send_message(
            user_id,
            "📞 {}\n📍 {}\n📱 {}".format(config.STUDIO_NAME, config.STUDIO_ADDRESS, config.STUDIO_PHONE),
            main_keyboard(),
        )
        return

    send_message(user_id, "Не понял сообщение. Напишите «меню», чтобы увидеть кнопки.", main_keyboard())


def handle_callback(user_id: int, payload: str) -> None:
    """Obrabotka nazhatiy knopok: polnaya FSM-zapis v VK."""
    try:
        data = json.loads(payload)
        cmd = data.get("cmd")
    except (json.JSONDecodeError, TypeError):
        cmd, data = None, {}

    st = USER_STATE.get(user_id)

    if cmd == "book":
        vk_start_booking(user_id)
    elif cmd == "pick_service":
        USER_STATE[user_id] = {"step": "date", "service_id": int(data["service_id"])}
        send_message(user_id, "Vyberite datu:", dates_keyboard(int(data["service_id"])))
    elif cmd == "pick_date":
        USER_STATE[user_id] = {"step": "time", "service_id": int(data["service_id"]), "day": data["day"]}
        send_message(user_id, "Vyberite vremya:", times_keyboard(int(data["service_id"]), data["day"]))
    elif cmd == "pick_time":
        vk_confirm(user_id, int(data["service_id"]), data["slot"])
    elif cmd == "confirm_yes" and st:
        # zapis sozdayotsya v obschuyu bazu (VK-klienty vidny adminu)
        user = db.upsert_user_vk(user_id)
        booking_id = db.try_add_booking(user["id"], st["service_id"], st["slot"], None)
        if booking_id is None:
            send_message(user_id, "Eto vremya tolko chto zanyali. Vyberite drugoe, pozhaluysta.", main_keyboard())
            USER_STATE.pop(user_id, None)
            return
        # uvedomlenie adminam v Telegram o VK-zapisi
        import telegram_notify
        import scheduling
        svc = db.get_service(st["service_id"])
        telegram_notify.notify_admins_new_booking(
            svc["title"], user["name"], None, scheduling.format_slot_long(st["slot"]), source="VK"
        )
        import scheduling
        svc = db.get_service(st["service_id"])
        send_message(
            user_id,
            "Zapis sozdana!\n\n{}\n{}\n\nZhdem vas!".format(
                svc["title"], scheduling.format_slot_long(st["slot"])
            ),
            main_keyboard(),
        )
        USER_STATE.pop(user_id, None)
    elif cmd == "cancel_booking":
        USER_STATE.pop(user_id, None)
        send_message(user_id, "Zapis otmenena. Napishite \"menu\".", main_keyboard())
    elif cmd == "catalog":
        handle_message(user_id, "katalog")
    elif cmd == "contacts":
        handle_message(user_id, "kontakty")
    elif st:
        send_message(user_id, "Prodolzhim ili napishite \"menu\".", main_keyboard())
    else:
        send_message(user_id, "Napishite \"menu\".", main_keyboard())


def run_long_poll() -> None:
    """Режим Long Poll: сервер сам опрашивает VK."""
    db.init_db()
    server, key, ts = None, None, None
    logger.info("VK-бот запущен в режиме long poll")

    while True:
        try:
            if not server:
                resp = vk_api(
                    "groups.getLongPollServer", group_id=_group_id_from_token_env()
                )
                server, key, ts = resp["server"], resp["key"], resp["ts"]

            url = "{}?act=a_check&key={}&ts={}&wait=25&mode=2&version=3".format(server, key, ts)
            with urllib.request.urlopen(url, timeout=30) as r:
                data = json.loads(r.read().decode())

            if data.get("failed") is not None:
                server = None
                continue

            ts = data["ts"]
            for update in data.get("updates", []):
                kind = update.get("type")
                obj = update.get("object", {})
                if kind == "message_new":
                    msg = obj.get("message", obj)
                    handle_message(int(msg["from_id"]), msg.get("text"))
                elif kind == "message_event":
                    handle_callback(int(obj["user_id"]), obj.get("payload", "{}"))
        except Exception as exc:
            logger.error("VK long poll error: %s", exc)
            server = None
            import time
            time.sleep(5)


def _group_id_from_token_env() -> int:
    import os as _os
    return int(_os.getenv("VK_GROUP_ID", "0"))


def run_callback(host: str = "0.0.0.0", port: int = 8081) -> None:
    """Режим Callback API: VK сам присылает события (нужен VK_CONFIRMATION_CODE)."""
    from http.server import BaseHTTPRequestHandler, HTTPServer

    db.init_db()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode()
            try:
                event = json.loads(body)
            except json.JSONDecodeError:
                self._respond("bad request")
                return

            if event.get("type") == "confirmation":
                self._respond(config.VK_CONFIRMATION_CODE or "ok")
                return

            obj = event.get("object", {})
            if event.get("type") == "message_new":
                handle_message(int(obj.get("from_id", 0)), obj.get("text"))
            elif event.get("type") == "message_event":
                handle_callback(int(obj.get("user_id", 0)), obj.get("payload", "{}"))

            self._respond("ok")

        def _respond(self, text: str):
            data = text.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    logger.info("VK Callback API на %s:%s", host, port)
    HTTPServer((host, port), Handler).serve_forever()


def main() -> None:
    if not config.VK_ENABLED:
        logger.info("VK отключён (VK_ENABLED=0). Запустите с VK_ENABLED=1.")
        return
    if not config.VK_COMMUNITY_TOKEN:
        logger.error("VK_COMMUNITY_TOKEN не задан")
        return

    if config.VK_CONFIRMATION_CODE:
        run_callback()
    else:
        run_long_poll()


if __name__ == "__main__":
    main()
