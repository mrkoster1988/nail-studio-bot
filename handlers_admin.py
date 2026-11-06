"""Админские хендлеры: статистика, записи, клиенты, услуги, рассылки."""
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import config
import database as db

from bot import bot
import keyboards as kb
import webhooks
from states import AdminStates


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


def fmt_dt(iso: str) -> str:
    return iso[:16].replace("T", " ")


def price(value) -> str:
    return "{:,}".format(int(value)).replace(",", " ")


@types.message.register(commands=["admin"])
async def admin_entry(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    await message.answer("👑 *Панель администратора*", reply_markup=kb.admin_menu())


@types.callback_query.register(lambda c: c.data == "adm:menu")
async def admin_menu_cb(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    await call.message.edit_text("👑 *Панель администратора*", reply_markup=kb.admin_menu())
    await call.answer()


@types.callback_query.register(lambda c: c.data == "adm:stats")
async def admin_stats(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return

    s = db.stats()
    lines = [
        "📊 *Статистика*\n",
        "👥 Клиентов: {}".format(s["total_users"]),
        "📋 Всего записей: {}".format(s["total_bookings"]),
        "⏳ Активных (ожидают + подтверждены): {}".format(s["active"]),
        "✅ Завершено: {}".format(s["done"]),
        "📆 Подтверждённых в будущем: {}".format(s["upcoming"]),
        "💰 Выручка по завершённым: {} ₽\n".format(price(s["revenue"])),
    ]
    if s["top_services"]:
        lines.append("*Топ услуг:*")
        for i, row in enumerate(s["top_services"], 1):
            lines.append("{}. {} — {} записей".format(i, row["title"], row["cnt"]))

    await call.message.edit_text("\n".join(lines), reply_markup=kb.admin_menu())
    await call.answer()


@types.callback_query.register(lambda c: c.data == "adm:bookings")
async def admin_bookings(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return

    bookings = db.all_bookings(limit=30)
    if not bookings:
        await call.message.edit_text("Записей пока нет.", reply_markup=kb.admin_menu())
        await call.answer()
        return

    await call.message.edit_text(
        "📋 *Последние записи*\n\nВыберите запись для управления:",
        reply_markup=kb.admin_bookings_kb(bookings),
    )
    await call.answer()


@types.callback_query.register(lambda c: c.data.startswith("adm:booking:"))
async def admin_booking_detail(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return

    booking_id = int(call.data.split(":")[2])
    b = db.get_booking(booking_id)
    if not b:
        await call.answer("Запись не найдена", show_alert=True)
        return

    status = db.STATUS_TITLES.get(b["status"], b["status"])
    text = (
        "📋 *Запись #{id}*\n\n"
        "👤 Клиент: {name}{user}\n"
        "📱 Телефон: {phone}\n"
        "💅 Услуга: {title} — {price} ₽\n"
        "📅 Когда: {when}\n"
        "⏱ Длительность: {dur} мин\n"
        "🔖 Статус: {status}\n"
    ).format(
        id=booking_id,
        name=b["name"] or "—",
        user=" (@{})".format(b["username"]) if b["username"] else "",
        phone=b["phone"] or "—",
        title=b["service_title"],
        price=price(b["service_price"]),
        when=fmt_dt(b["slot_start"]),
        dur=b["service_duration"],
        status=status,
    )
    if b["comment"]:
        text += "\n💬 Комментарий: _{}_".format(b["comment"])

    markup = kb.admin_booking_actions_kb(booking_id, b["status"])
    if b["phone"]:
        markup.add(
            InlineKeyboardButton(
                "📱 Позвонить {}".format(b["phone"]), url="tel:{}".format(b["phone"])
            )
        )
    await call.message.edit_text(text, reply_markup=markup)
    await call.answer()


@types.callback_query.register(lambda c: c.data.startswith("adm:set:"))
async def admin_set_status(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return

    parts = call.data.split(":")
    booking_id = int(parts[2])
    status = parts[3]

    booking = db.get_booking(booking_id)
    if not booking:
        await call.answer("Запись не найдена", show_alert=True)
        return

    db.set_booking_status(booking_id, status)

    # Завершённый визит: баллы + просьба оставить отзыв
    if status == db.STATUS_DONE and booking["status"] != db.STATUS_DONE:
        db.add_points(booking["user_id"], db.POINTS_PER_VISIT, "visit")
        try:
            await bot.send_message(
                booking["tg_id"],
                "🏁 *Спасибо за визит!*\n\n"
                "Вам начислено {} бонусных баллов.\n\n"
                "Оцените визит, пожалуйста:".format(db.POINTS_PER_VISIT),
                reply_markup=kb.review_rating_kb(booking_id),
            )
        except Exception:
            pass

    title = db.STATUS_TITLES.get(status, status)
    try:
        await call.bot.send_message(
            booking["tg_id"],
            "🔔 *Обновление записи*\n\n"
            "📅 {}\n"
            "💅 {}\n"
            "🔖 Статус: {}".format(
                fmt_dt(booking["slot_start"]), booking["service_title"], title
            ),
        )
    except Exception:
        pass

    # Уведомляем внешнюю систему о смене статуса
    updated = db.get_booking(booking_id)
    webhooks.send_webhook("booking.status_changed", webhooks.booking_to_dict(updated))

    await call.message.edit_text(
        "✅ Статус записи #{} изменён на *{}*. Клиент уведомлён.".format(booking_id, title),
        reply_markup=kb.admin_bookings_kb(db.all_bookings(limit=30)),
    )
    await call.answer()


@types.callback_query.register(lambda c: c.data == "adm:clients")
async def admin_clients(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return

    users = db.all_users()
    if not users:
        await call.message.edit_text("Клиентов пока нет.", reply_markup=kb.admin_menu())
        await call.answer()
        return

    lines = ["👥 *Клиенты* (последние 40)\n"]
    for u in users[-40:]:
        bookings = db.user_bookings(u["id"])
        active = sum(
            1 for b in bookings if b["status"] in (db.STATUS_PENDING, db.STATUS_CONFIRMED)
        )
        lines.append(
            "• *{}{user}* — {phone} | записей: {total}, активных: {active}".format(
                u["name"] or u["tg_id"],
                user=" (@{})".format(u["username"]) if u["username"] else "",
                phone=u["phone"] or "без телефона",
                total=len(bookings),
                active=active,
            )
        )

    await call.message.edit_text("\n".join(lines), reply_markup=kb.admin_menu())
    await call.answer()


@types.callback_query.register(lambda c: c.data == "adm:services")
async def admin_services(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    await call.message.edit_text("⚙️ *Услуги*\n", reply_markup=kb.admin_services_kb())
    await call.answer()


@types.callback_query.register(lambda c: c.data == "adm:add_service")
async def admin_add_service(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.add_service_name)
    await call.message.edit_text("➕ *Новая услуга*\n\nВведите название:")
    await call.answer()


@types.message.register(AdminStates.add_service_name)
async def add_service_name(message: types.Message, state: FSMContext):
    await state.update_state(title=message.text.strip())
    await state.set_state(AdminStates.add_service_price)
    await message.answer("💰 Укажите цену в рублях (только число):")


@types.message.register(AdminStates.add_service_price)
async def add_service_price(message: types.Message, state: FSMContext):
    try:
        value = int(message.text.strip().replace(" ", "").replace("₽", ""))
    except ValueError:
        await message.answer("Цена должна быть числом. Попробуйте ещё раз:")
        return
    await state.update_state(price=value)
    await state.set_state(AdminStates.add_service_duration)
    await message.answer("⏱ Сколько минут занимает услуга?")


@types.message.register(AdminStates.add_service_duration)
async def add_service_duration(message: types.Message, state: FSMContext):
    try:
        duration = int(message.text.strip())
    except ValueError:
        await message.answer("Укажите количество минут числом:")
        return
    await state.update_state(duration=duration)
    await state.set_state(AdminStates.add_service_category)
    await message.answer("🏷 Категория? (например: Маникюр, Педикюр, Дизайн)")


@types.message.register(AdminStates.add_service_category)
async def add_service_category(message: types.Message, state: FSMContext):
    await state.update_state(category=message.text.strip() or "Общее")
    await state.set_state(AdminStates.add_service_desc)
    await message.answer("📝 Описание (можно пропустить — отправьте «-»):")


@types.message.register(AdminStates.add_service_desc)
async def add_service_desc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    description = "" if message.text.strip() == "-" else message.text.strip()
    service_id = db.add_service(
        data["title"], data["price"], data["duration"], data["category"], description
    )
    await state.clear()
    await message.answer(
        "✅ Услуга «{}» добавлена.".format(data["title"]),
        reply_markup=kb.admin_service_actions_kb(service_id),
    )


@types.callback_query.register(lambda c: c.data.startswith("adm:svc:"))
async def admin_service_detail(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    service_id = int(call.data.split(":")[2])
    s = db.get_service(service_id)
    if not s:
        await call.answer("Услуга не найдена", show_alert=True)
        return

    text = (
        "⚙️ *{}*\n\n"
        "💰 Цена: {} ₽\n"
        "⏱ Длительность: {} мин\n"
        "🏷 Категория: {}\n"
        "📝 {}\n"
        "Статус: {}"
    ).format(
        s["title"],
        price(s["price"]),
        s["duration"],
        s["category"],
        s["description"] or "—",
        "активна" if s["is_active"] else "скрыта",
    )
    await call.message.edit_text(text, reply_markup=kb.admin_service_actions_kb(service_id))
    await call.answer()


@types.callback_query.register(lambda c: c.data.startswith("adm:edit:"))
async def admin_edit_service(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return

    parts = call.data.split(":")
    service_id = int(parts[2])
    field = parts[3]
    await state.update_state(service_id=service_id, field=field)
    await state.set_state(AdminStates.edit_service_field)

    prompts = {
        "title": "Введите новое название:",
        "price": "Введите новую цену (число):",
        "duration": "Введите новую длительность (минуты):",
        "category": "Введите новую категорию:",
        "description": "Введите новое описание (или «-» чтобы очистить):",
    }
    await call.message.edit_text("✏️ {}".format(prompts.get(field, "Введите значение:")))
    await call.answer()


@types.message.register(AdminStates.edit_service_field)
async def admin_save_edit(message: types.Message, state: FSMContext):
    data = await state.get_data()
    field = data["field"]
    value = message.text.strip()
    if value == "-" and field == "description":
        value = ""

    if field in ("price", "duration"):
        try:
            value = int(value.replace(" ", "").replace("₽", ""))
        except ValueError:
            await message.answer("Нужно число. Попробуйте ещё раз:")
            return

    db.update_service(data["service_id"], **{field: value})
    await state.clear()
    await message.answer(
        "✅ Изменения сохранены.",
        reply_markup=kb.admin_service_actions_kb(data["service_id"]),
    )


@types.callback_query.register(lambda c: c.data.startswith("adm:del:"))
async def admin_delete_service(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    service_id = int(call.data.split(":")[2])
    db.delete_service(service_id)
    await call.message.edit_text(
        "🗑 Услуга скрыта из каталога.", reply_markup=kb.admin_services_kb()
    )
    await call.answer()


@types.callback_query.register(lambda c: c.data == "adm:broadcast")
async def admin_broadcast(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.broadcast_text)
    await call.message.edit_text(
        "📢 *Рассылка*\n\nКому отправляем?", reply_markup=kb.broadcast_audience_kb()
    )
    await call.answer()


@types.callback_query.register(lambda c: c.data.startswith("adm:bc:"))
async def admin_broadcast_audience(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    audience = call.data.split(":")[2]
    await state.update_state(audience=audience)
    await state.set_state(AdminStates.broadcast_text)
    await call.message.edit_text("📝 Введите текст рассылки (HTML-разметка поддерживается):")
    await call.answer()


@types.message.register(AdminStates.broadcast_text)
async def admin_broadcast_send(message: types.Message, state: FSMContext):
    data = await state.get_data()
    audience = data.get("audience", "all")
    text = message.html_text

    if audience == "active":
        seen = set()
        targets = []
        for b in db.all_bookings(limit=1000):
            if b["status"] in (db.STATUS_PENDING, db.STATUS_CONFIRMED) and b["tg_id"] not in seen:
                seen.add(b["tg_id"])
                targets.append(b["tg_id"])
    else:
        targets = [u["tg_id"] for u in db.all_users()]

    sent = failed = 0
    for tg_id in targets:
        try:
            await message.bot.send_message(tg_id, text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

    db.save_broadcast(text, audience, sent, failed)
    await state.clear()
    await message.answer(
        "📢 Рассылка отправлена.\n\n"
        "✅ Доставлено: {}\n"
        "❌ Не доставлено: {}\n"
        "👥 Охват: {}".format(sent, failed, len(targets)),
        reply_markup=kb.admin_menu(),
    )
