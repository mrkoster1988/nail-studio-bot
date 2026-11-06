"""Клиентские хендлеры: каталог, запись, мои записи, контакты, помощь."""
from datetime import date

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import config
import database as db

from bot import bot
import keyboards as kb
import scheduling
import webhooks
from states import ClientStates


def price(value) -> str:
    return "{:,}".format(int(value)).replace(",", " ")


@types.message.register(commands=["start", "help"])
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    # реферальная ссылка: /start ref_<tg_id>
    ref = None
    if message.get_args():
        arg = message.get_args().strip()
        if arg.startswith("ref_"):
            try:
                ref = int(arg[4:])
            except ValueError:
                ref = None

    db_user_id = db.upsert_user(
        message.from_user.id, message.from_user.full_name, message.from_user.username
    )

    if ref is not None and ref != message.from_user.id:
        if not db.has_any_booking(db_user_id):
            if db.set_referrer(db_user_id, ref):
                try:
                    await bot.send_message(
                        ref,
                        "🎁 По вашей ссылке записался новый клиент! "
                        "Начислено {} бонусов.".format(db.POINTS_PER_REFERRAL),
                    )
                except Exception:
                    pass
                db.add_points(
                    db.get_referrer_id(db_user_id),
                    db.POINTS_PER_REFERRAL,
                    "referral",
                )

    text = config.WELCOME_TEXT.format(
        name=message.from_user.first_name or "Добро пожаловать",
        studio=config.STUDIO_NAME,
    )
    await message.answer(text, reply_markup=kb.main_menu())


@types.callback_query.register(lambda c: c.data == "cat:menu")
async def back_to_menu(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(config.MAIN_MENU_TEXT, reply_markup=kb.main_menu())
    await call.answer()


@types.callback_query.register(lambda c: c.data == "noop")
async def noop(call: types.CallbackQuery):
    await call.answer()


@types.callback_query.register(lambda c: c.data == "cat:catalog")
async def catalog(call: types.CallbackQuery):
    services = db.list_services()
    if not services:
        await call.message.edit_text(
            "Каталог пока пуст. Загляните позже!", reply_markup=kb.back_to_menu()
        )
        await call.answer()
        return

    lines = ["💅 *Каталог услуг и цен*\n"]
    current_cat = None
    for s in services:
        if s["category"] != current_cat:
            current_cat = s["category"]
            lines.append("\n*{}*".format(current_cat))
        lines.append(
            "• {} — {} ₽ ({} мин)".format(s["title"], price(s["price"]), s["duration"])
        )
        if s["description"]:
            lines.append("  _{}_".format(s["description"]))

    lines.append("\nВыберите услугу, чтобы записаться:")
    await call.message.edit_text("\n".join(lines), reply_markup=kb.services_kb())
    await call.answer()


@types.callback_query.register(lambda c: c.data == "cat:contacts")
async def contacts(call: types.CallbackQuery):
    text = (
        "📞 *{}*\n\n"
        "📍 Адрес: {}\n"
        "📞 Телефон: {}\n"
        "✉️ Почта: {}\n"
        "📱 Instagram: {}\n\n"
        "Нажмите кнопку ниже, чтобы позвонить."
    ).format(
        config.STUDIO_NAME,
        config.STUDIO_ADDRESS,
        config.STUDIO_PHONE,
        config.STUDIO_EMAIL,
        config.STUDIO_INSTAGRAM,
    )
    buttons = InlineKeyboardMarkup()
    buttons.add(
        InlineKeyboardButton(
            "📞 Позвонить {}".format(config.STUDIO_PHONE),
            url="tel:{}".format(config.STUDIO_PHONE),
        )
    )
    buttons.add(InlineKeyboardButton("⬅️ В меню", callback_data="cat:menu"))
    await call.message.edit_text(text, reply_markup=buttons)
    await call.answer()


@types.callback_query.register(lambda c: c.data == "cat:howto")
async def howto(call: types.CallbackQuery):
    text = (
        "🗺 *Как добраться*\n\nАдрес: {}\n\n"
        "Нажмите кнопку ниже, чтобы построить маршрут."
    ).format(config.STUDIO_ADDRESS)
    buttons = InlineKeyboardMarkup()
    buttons.add(InlineKeyboardButton("🗺 Открыть карту", url=config.STUDIO_MAP_URL))
    buttons.add(InlineKeyboardButton("⬅️ В меню", callback_data="cat:menu"))
    await call.message.edit_text(text, reply_markup=buttons)
    await call.answer()


HELP_TEXT = (
    "❓ *Помощь*\n\n"
    "**Как записаться?**\n"
    "Нажмите «📅 Записаться», выберите услугу, дату и время — и оставьте телефон. "
    "Как только администратор подтвердит запись, вы получите уведомление.\n\n"
    "**Можно ли отменить?**\n"
    "Да. Откройте «📋 Мои записи» и нажмите «Отменить запись».\n\n"
    "**За сколько до визита?**\n"
    "Запись открыта за {} дней вперёд. Минимальный запас до визита — {} ч.\n\n"
    "**Что если не пришли?**\n"
    "Сообщите нам заранее по телефону, чтобы мы освободили время.\n\n"
    "Вопросы: {}".format(
        config.BOOKING_HORIZON_DAYS,
        config.MIN_LEAD_MINUTES // 60,
        config.STUDIO_PHONE,
    )
)


@types.callback_query.register(lambda c: c.data == "cat:help")
async def help_cb(call: types.CallbackQuery):
    await call.message.edit_text(HELP_TEXT, reply_markup=kb.back_to_menu())
    await call.answer()


@types.callback_query.register(lambda c: c.data == "cat:book")
async def book_start(call: types.CallbackQuery, state: FSMContext):
    if not db.list_services():
        await call.answer("Каталог пуст", show_alert=True)
        return
    await state.set_state(ClientStates.choose_service)
    await call.message.edit_text("💅 *Выберите услугу*\n", reply_markup=kb.services_kb())
    await call.answer()


@types.callback_query.register(lambda c: c.data.startswith("svc:"))
async def service_selected(call: types.CallbackQuery, state: FSMContext):
    service_id = int(call.data.split(":")[1])
    service = db.get_service(service_id)
    if not service:
        await call.answer("Услуга не найдена", show_alert=True)
        return

    user = db.get_user_by_tg(call.from_user.id)
    if user and db.active_booking_count(user["id"]) >= config.MAX_ACTIVE_BOOKINGS:
        await call.answer(
            "У вас уже есть {} активные записи. Отмените одну, чтобы создать новую.".format(
                config.MAX_ACTIVE_BOOKINGS
            ),
            show_alert=True,
        )
        return

    await state.update_state(service_id=service_id)
    await state.set_state(ClientStates.choose_date)
    await call.message.edit_text(
        "Выбрано: *{}* — {} ₽ ({} мин)\n\n📅 Теперь выберите дату:".format(
            service["title"], price(service["price"]), service["duration"]
        ),
        reply_markup=kb.dates_kb(),
    )
    await call.answer()


@types.callback_query.register(lambda c: c.data.startswith("date:"))
async def date_selected(call: types.CallbackQuery, state: FSMContext):
    day_iso = call.data.split(":", 1)[1]
    data = await state.get_data()
    service = db.get_service(data.get("service_id"))
    if not service:
        await call.answer("Начните заново", show_alert=True)
        return

    await state.update_state(day=day_iso)
    await state.set_state(ClientStates.choose_time)
    await call.message.edit_text(
        "📅 *{}*\n\nВыберите свободное время:".format(
            scheduling.format_date(date.fromisoformat(day_iso))
        ),
        reply_markup=kb.times_kb(day_iso, service["duration"]),
    )
    await call.answer()


@types.callback_query.register(lambda c: c.data.startswith("time:"))
async def time_selected(call: types.CallbackQuery, state: FSMContext):
    slot = call.data.split(":", 1)[1]
    data = await state.get_data()
    service = db.get_service(data.get("service_id"))
    if not service:
        await call.answer("Начните заново", show_alert=True)
        return

    if db.is_slot_busy(slot, service["duration"]):
        await call.answer("Это время только что заняли. Выберите другое.", show_alert=True)
        await call.message.edit_text(
            "⏰ К сожалению, это время уже занято. Выберите другое:",
            reply_markup=kb.times_kb(data["day"], service["duration"]),
        )
        return

    await state.update_state(slot=slot)
    await state.set_state(ClientStates.phone)

    text = (
        "✅ *Вы выбрали:*\n"
        "Услуга: {}\n"
        "Дата и время: {}\n"
        "Стоимость: {} ₽\n\n"
        "📱 Оставьте телефон для подтверждения записи:"
    ).format(
        service["title"],
        scheduling.format_slot_long(slot),
        price(service["price"]),
    )
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup())
    await call.answer()


@types.message.register(ClientStates.phone)
async def phone_entered(message: types.Message, state: FSMContext):
    phone = (message.text or "").strip()
    digits = phone.replace("+", "").replace(" ", "").replace("-", "")
    if len(digits) < 10:
        await message.answer("Похоже, номер слишком короткий. Введите телефон полностью:")
        return

    data = await state.get_data()
    service = db.get_service(data.get("service_id"))
    if not service:
        await state.clear()
        await message.answer(
            "Что-то пошло не так. Начните заново:", reply_markup=kb.main_menu()
        )
        return

    user_id = db.upsert_user(
        message.from_user.id, message.from_user.full_name, message.from_user.username
    )
    db.set_user_phone(user_id, phone)

    booking_id = db.try_add_booking(user_id, service["id"], data["slot"], data.get("comment"))
    if booking_id is None:
        await message.answer(
            "😔 Увы, это время только что заняли. Выберите другое, пожалуйста.",
            reply_markup=kb.main_menu(),
        )
        await state.clear()
        return

    # Уведомляем внешнюю систему о новой записи
    booking = db.get_booking(booking_id)
    webhooks.send_webhook("booking.created", webhooks.booking_to_dict(booking))

    # Уведомляем админов о новой заявке
    admin_text = (
        "🔔 *Новая заявка!\n\n*"
        "💅 {title}\n"
        "👤 {name}{user}\n"
        "📱 {phone}\n"
        "📅 {when}\n\n"
        "Подтвердите в панели: /admin"
    ).format(
        title=service["title"],
        name=message.from_user.full_name,
        user=" (@{})".format(message.from_user.username) if message.from_user.username else "",
        phone=phone,
        when=booking["slot_start"][:16].replace("T", " "),
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text)
        except Exception:
            pass

    await state.set_state(ClientStates.confirm)
    await message.answer(
        "🎉 *Запись создана!*\n\n"
        "Мы получили ваш номер. Как только администратор подтвердит запись, "
        "вы получите уведомление.\n\n"
        "Если хотите оставить комментарий (например, пожелания по дизайну) — "
        "напишите его сейчас, иначе нажмите кнопку ниже.",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton(
                "Готово, без комментария", callback_data="done:{}".format(booking_id)
            ),
            InlineKeyboardButton(
                "💬 Добавить комментарий", callback_data="comment:{}".format(booking_id)
            ),
        ),
    )


@types.callback_query.register(lambda c: c.data.startswith("comment:"))
async def ask_comment(call: types.CallbackQuery, state: FSMContext):
    booking_id = int(call.data.split(":")[1])
    await state.update_state(booking_id=booking_id)
    await state.set_state(ClientStates.comment)
    await call.message.edit_text(
        "💬 Напишите ваш комментарий (например, пожелания по цвету или дизайну):"
    )
    await call.answer()


@types.message.register(ClientStates.comment)
async def save_comment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    booking_id = data.get("booking_id")
    with db.db() as conn:
        conn.execute(
            "UPDATE bookings SET comment = ? WHERE id = ?", (message.text, booking_id)
        )
    await state.clear()
    await message.answer("✅ Комментарий сохранён!", reply_markup=kb.main_menu())


@types.callback_query.register(lambda c: c.data.startswith("done:"))
async def booking_done(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "✅ Готово! Мы свяжемся с вами для подтверждения.\n\n"
        "Посмотреть свои записи можно в разделе «📋 Мои записи».",
        reply_markup=kb.main_menu(),
    )
    await call.answer()


@types.callback_query.register(lambda c: c.data == "cat:my")
async def my_bookings(call: types.CallbackQuery, state: FSMContext):
    user = db.get_user_by_tg(call.from_user.id)
    bookings = db.user_bookings(user["id"]) if user else []
    if not bookings:
        await call.message.edit_text(
            "У вас пока нет записей.\n\nНажмите «📅 Записаться», чтобы создать первую.",
            reply_markup=kb.main_menu(),
        )
        await call.answer()
        return

    user_points = db.get_points(user["id"]) if user else 0
    await call.message.edit_text(
        "📋 *Ваши записи*\n\nВыберите запись, чтобы подробности или отмену:\n\n"
        "💎 Баллы: *{}* (1 балл = 1 ₽ скидки)".format(user_points),
        reply_markup=kb.my_bookings_kb(bookings),
    )
    await call.answer()


@types.callback_query.register(lambda c: c.data.startswith("my:"))
async def my_booking_detail(call: types.CallbackQuery):
    booking_id = int(call.data.split(":")[1])
    booking = db.get_booking(booking_id)
    if not booking:
        await call.answer("Запись не найдена", show_alert=True)
        return

    status = db.STATUS_TITLES.get(booking["status"], booking["status"])
    text = (
        "📋 *Запись #{id}*\n\n"
        "Услуга: {title}\n"
        "Дата: {when}\n"
        "Стоимость: {price} ₽\n"
        "Статус: {status}\n"
    ).format(
        id=booking_id,
        title=booking["service_title"],
        when=booking["slot_start"][:16].replace("T", " "),
        price=price(booking["service_price"]),
        status=status,
    )
    if booking["comment"]:
        text += "Комментарий: _{}_\n".format(booking["comment"])

    if booking["status"] in (db.STATUS_PENDING, db.STATUS_CONFIRMED):
        await call.message.edit_text(text, reply_markup=kb.booking_actions_kb(booking_id))
    else:
        await call.message.edit_text(text, reply_markup=kb.back_to_menu())
    await call.answer()


# --- Перенос записи на другое время ---------------------------------------

@types.callback_query.register(lambda c: c.data.startswith("resched:"))
async def reschedule_start(call: types.CallbackQuery, state: FSMContext):
    booking_id = int(call.data.split(":")[1])
    booking = db.get_booking(booking_id)
    if not booking:
        await call.answer("Запись не найдена", show_alert=True)
        return
    if booking["tg_id"] != call.from_user.id:
        await call.answer("Это не ваша запись", show_alert=True)
        return
    if booking["status"] not in (db.STATUS_PENDING, db.STATUS_CONFIRMED):
        await call.answer("Эту запись уже нельзя перенести", show_alert=True)
        return

    await state.update_state(resched_booking_id=booking_id)
    await state.set_state(ClientStates.resched_date)
    await call.message.edit_text(
        "🔄 *Перенос записи*\n\nСейчас: {}\n\nВыберите новую дату:".format(
            booking["slot_start"][:16].replace("T", " ")
        ),
        reply_markup=kb.dates_kb(prefix="rdate"),
    )
    await call.answer()


@types.callback_query.register(lambda c: c.data.startswith("rdate:"))
async def reschedule_date(call: types.CallbackQuery, state: FSMContext):
    day_iso = call.data.split(":", 1)[1]
    data = await state.get_data()
    booking = db.get_booking(data.get("resched_booking_id"))
    if not booking:
        await call.answer("Запись не найдена", show_alert=True)
        return

    await state.update_state(resched_day=day_iso)
    await state.set_state(ClientStates.resched_time)
    await call.message.edit_text(
        "📅 Новая дата: {}\n\nВыберите время:".format(
            scheduling.format_date(date.fromisoformat(day_iso))
        ),
        reply_markup=kb.times_kb(day_iso, booking["service_duration"], prefix="rtime"),
    )
    await call.answer()


@types.callback_query.register(lambda c: c.data.startswith("rtime:"))
async def reschedule_time(call: types.CallbackQuery, state: FSMContext):
    slot = call.data.split(":", 1)[1]
    data = await state.get_data()
    booking_id = data.get("resched_booking_id")
    booking = db.get_booking(booking_id)
    if not booking:
        await call.answer("Запись не найдена", show_alert=True)
        return

    if db.is_slot_busy(slot, booking["service_duration"]):
        await call.answer("Это время занято. Выберите другое.", show_alert=True)
        await call.message.edit_text(
            "⏰ Это время уже занято. Выберите другое:",
            reply_markup=kb.times_kb(
                data["resched_day"], booking["service_duration"], prefix="rtime"
            ),
        )
        return

    old_slot = booking["slot_start"]
    with db.db() as conn:
        conn.execute(
            "UPDATE bookings SET slot_start = ? WHERE id = ?", (slot, booking_id)
        )
    # Снимаем старые напоминания — они относятся к прежнему времени
    db.clear_reminders(booking_id)

    updated = db.get_booking(booking_id)
    webhooks.send_webhook("booking.rescheduled", webhooks.booking_to_dict(updated))

    try:
        await call.bot.send_message(
            booking["tg_id"],
            "🔄 *Запись перенесена*\n\n"
            "Было: {}\n"
            "Стало: {}\n\n"
            "Напомним вам о визите.".format(
                old_slot[:16].replace("T", " "),
                slot[:16].replace("T", " "),
            ),
        )
    except Exception:
        pass

    await state.clear()
    await call.message.edit_text(
        "✅ *Запись перенесена!*\n\nНовое время: {}".format(
            scheduling.format_slot_long(slot)
        ),
        reply_markup=kb.main_menu(),
    )
    await call.answer()

@types.callback_query.register(lambda c: c.data.startswith("cancel:"))
async def cancel_booking(call: types.CallbackQuery):
    booking_id = int(call.data.split(":")[1])
    booking = db.get_booking(booking_id)
    if not booking:
        await call.answer("Запись не найдена", show_alert=True)
        return
    if booking["tg_id"] != call.from_user.id:
        await call.answer("Это не ваша запись", show_alert=True)
        return

    db.cancel_booking(booking_id)

    # сброс запланированных напоминаний и события календаря
    db.cancel_reminders(booking_id)
    import gcal_sync
    gcal_sync.push_delete(db.get_booking(booking_id))

    # Уведомляем внешнюю систему об отмене
    updated = db.get_booking(booking_id)
    webhooks.send_webhook("booking.cancelled", webhooks.booking_to_dict(updated))

    await call.message.edit_text(
        "❌ Запись отменена.\n\nЕсли передумаете — запишитесь заново.",
        reply_markup=kb.main_menu(),
    )
    await call.answer()


# --- Отзывы ----------------------------------------------------------------

@types.callback_query.register(lambda c: c.data.startswith("rev:rate:"))
async def review_rate(call: types.CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    booking_id = int(parts[2])
    rating = int(parts[3])

    booking = db.get_booking(booking_id)
    if not booking or booking["tg_id"] != call.from_user.id:
        await call.answer("Запись не найдена", show_alert=True)
        return

    await state.update_state(review_booking_id=booking_id, review_rating=rating)
    await state.set_state(ClientStates.review_text)
    await call.message.edit_text(
        "⭐ Спасибо! Оценка {} из 5.\n\n"
        "Хотите оставить пару слов о визите? Напишите отзыв, или нажмите кнопку ниже.".format(rating),
        reply_markup=kb.review_skip_kb(booking_id),
    )
    await call.answer()


@types.message.register(ClientStates.review_text)
async def review_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    db.add_review(data["review_booking_id"], data["user_id"], data["review_rating"], message.text)
    await state.clear()
    db.add_points(data["user_id"], 5, "review")
    await message.answer("✅ Спасибо за отзыв! +5 бонусов за обратную связь.")


@types.callback_query.register(lambda c: c.data.startswith("rev:skip:"))
async def review_skip(call: types.CallbackQuery, state: FSMContext):
    booking_id = int(call.data.split(":")[2])
    user = db.get_user_by_tg(call.from_user.id)
    if user:
        db.add_review(booking_id, user["id"], 0, None)
    await state.clear()
    await call.message.edit_text("✅ Спасибо! Хорошего дня!", reply_markup=kb.main_menu())
    await call.answer()
