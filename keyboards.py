"""Клавиатуры клиента и администратора."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import config
import database as db


def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(config.BTN_CATALOG, callback_data="cat:catalog"),
        InlineKeyboardButton(config.BTN_BOOK, callback_data="cat:book"),
        InlineKeyboardButton(config.BTN_MY, callback_data="cat:my"),
        InlineKeyboardButton(config.BTN_CONTACTS, callback_data="cat:contacts"),
        InlineKeyboardButton(config.BTN_HOWTO, callback_data="cat:howto"),
        InlineKeyboardButton(config.BTN_HELP, callback_data="cat:help"),
    )
    if config.VPN_PROMO_ENABLED and config.VPN_PROMO_URL:
        kb.add(
            InlineKeyboardButton(
                "{} -{}%".format(config.VPN_PROMO_TITLE, config.VPN_PROMO_DISCOUNT_PCT),
                url=config.VPN_PROMO_URL,
            )
        )
    return kb


def back_to_menu():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⬅️ В меню", callback_data="cat:menu"))
    return kb


def services_kb(category: str = None):
    kb = InlineKeyboardMarkup()
    for s in db.list_services():
        if category and s["category"] != category:
            continue
        kb.add(
            InlineKeyboardButton(
                "{} — {} ₽".format(s["title"], s["price"]),
                callback_data="svc:{}".format(s["id"]),
            )
        )
    kb.add(InlineKeyboardButton("⬅️ В меню", callback_data="cat:menu"))
    return kb


def dates_kb(prefix: str = "date"):
    from scheduling import available_dates, format_date

    kb = InlineKeyboardMarkup(row_width=3)
    for d in available_dates()[:21]:
        kb.add(
            InlineKeyboardButton(
                format_date(d),
                callback_data="{}:{}".format(prefix, d.isoformat()),
            )
        )
    kb.add(InlineKeyboardButton("⬅️ В меню", callback_data="cat:menu"))
    return kb


def times_kb(day_iso: str, duration: int, prefix: str = "time"):
    from datetime import date

    from scheduling import format_slot, slots_for_date

    kb = InlineKeyboardMarkup(row_width=3)
    slots = slots_for_date(date.fromisoformat(day_iso), duration)
    for s in slots:
        kb.add(
            InlineKeyboardButton(
                format_slot(s), callback_data="{}:{}".format(prefix, s)
            )
        )
    if not slots:
        kb.add(InlineKeyboardButton("На этот день мест нет", callback_data="noop"))
    kb.add(InlineKeyboardButton("⬅️ В меню", callback_data="cat:menu"))
    return kb


def my_bookings_kb(bookings):
    kb = InlineKeyboardMarkup()
    for b in bookings:
        kb.add(
            InlineKeyboardButton(
                "{} {} — {}".format(
                    db.STATUS_ICONS.get(b["status"], "•"),
                    b["slot_start"][5:16].replace("T", " "),
                    b["service_title"],
                ),
                callback_data="my:{}".format(b["id"]),
            )
        )
    kb.add(InlineKeyboardButton("⬅️ В меню", callback_data="cat:menu"))
    return kb


def booking_actions_kb(booking_id: int):
    """Отмена и перенос — для активных записей."""
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(
            "🔄 Перенести на другое время", callback_data="resched:{}".format(booking_id)
        )
    )
    kb.add(
        InlineKeyboardButton(
            "❌ Отменить запись", callback_data="cancel:{}".format(booking_id)
        )
    )
    kb.add(InlineKeyboardButton("⬅️ В меню", callback_data="cat:menu"))
    return kb


def cancel_booking_kb(booking_id: int):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton(
            "❌ Отменить запись", callback_data="cancel:{}".format(booking_id)
        )
    )
    kb.add(InlineKeyboardButton("⬅️ В меню", callback_data="cat:menu"))
    return kb


def admin_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📊 Статистика", callback_data="adm:stats"),
        InlineKeyboardButton("📋 Записи", callback_data="adm:bookings"),
        InlineKeyboardButton("👥 Клиенты", callback_data="adm:clients"),
        InlineKeyboardButton("⚙️ Услуги", callback_data="adm:services"),
        InlineKeyboardButton("📢 Рассылка", callback_data="adm:broadcast"),
        InlineKeyboardButton("⬅️ В меню", callback_data="cat:menu"),
    )
    return kb


def admin_bookings_kb(bookings):
    kb = InlineKeyboardMarkup()
    for b in bookings:
        kb.add(
            InlineKeyboardButton(
                "{} {} — {} ({})".format(
                    db.STATUS_ICONS.get(b["status"], "•"),
                    b["slot_start"][5:16].replace("T", " "),
                    b["service_title"],
                    b["name"] or b["tg_id"],
                ),
                callback_data="adm:booking:{}".format(b["id"]),
            )
        )
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="adm:menu"))
    return kb


def admin_booking_actions_kb(booking_id: int, status: str):
    kb = InlineKeyboardMarkup(row_width=2)
    if status == db.STATUS_PENDING:
        kb.add(
            InlineKeyboardButton(
                "✅ Подтвердить",
                callback_data="adm:set:{}:confirmed".format(booking_id),
            ),
            InlineKeyboardButton(
                "❌ Отклонить",
                callback_data="adm:set:{}:cancelled".format(booking_id),
            ),
        )
    if status == db.STATUS_CONFIRMED:
        kb.add(
            InlineKeyboardButton(
                "🏁 Завершить",
                callback_data="adm:set:{}:done".format(booking_id),
            ),
            InlineKeyboardButton(
                "❌ Отменить",
                callback_data="adm:set:{}:cancelled".format(booking_id),
            ),
        )
    kb.add(InlineKeyboardButton("⬅️ К записям", callback_data="adm:bookings"))
    return kb


def admin_services_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ Добавить услугу", callback_data="adm:add_service"))
    for s in db.list_services(only_active=False):
        mark = "🟢" if s["is_active"] else "🔴"
        kb.add(
            InlineKeyboardButton(
                "{} {} — {} ₽".format(mark, s["title"], s["price"]),
                callback_data="adm:svc:{}".format(s["id"]),
            )
        )
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="adm:menu"))
    return kb


def admin_service_actions_kb(service_id: int):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✏️ Название", callback_data="adm:edit:{}:title".format(service_id)),
        InlineKeyboardButton("💰 Цена", callback_data="adm:edit:{}:price".format(service_id)),
        InlineKeyboardButton(
            "⏱ Длительность", callback_data="adm:edit:{}:duration".format(service_id)
        ),
        InlineKeyboardButton(
            "🏷 Категория", callback_data="adm:edit:{}:category".format(service_id)
        ),
        InlineKeyboardButton(
            "📝 Описание", callback_data="adm:edit:{}:description".format(service_id)
        ),
        InlineKeyboardButton("🗑 Удалить", callback_data="adm:del:{}".format(service_id)),
    )
    kb.add(InlineKeyboardButton("⬅️ К услугам", callback_data="adm:services"))
    return kb


def broadcast_audience_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("👥 Всем клиентам", callback_data="adm:bc:all"))
    kb.add(
        InlineKeyboardButton(
            "📋 Только с активными записями", callback_data="adm:bc:active"
        )
    )
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="adm:menu"))
    return kb


def review_rating_kb(booking_id: int):
    kb = InlineKeyboardMarkup(row_width=5)
    kb.add(*[InlineKeyboardButton("⭐" * n, callback_data="rev:rate:{}:{}".format(booking_id, n)) for n in range(1, 6)])
    return kb


def review_skip_kb(booking_id: int):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Пропустить", callback_data="rev:skip:{}".format(booking_id)))
    return kb


def vpn_promo_kb():
    """Полный экран VPN-промо: протоколы и ссылка."""
    kb = InlineKeyboardMarkup()
    protocols = ", ".join(config.VPN_PROTOCOLS)
    kb.add(
        InlineKeyboardButton(
            "Подключить VPN (-{}%)".format(config.VPN_PROMO_DISCOUNT_PCT),
            url=config.VPN_PROMO_URL,
        )
    )
    kb.add(InlineKeyboardButton("⬅️ В меню", callback_data="cat:menu"))
    return protocols, kb
