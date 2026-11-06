from aiogram.dispatcher.filters.state import State, StatesGroup


class ClientStates(StatesGroup):
    """Состояния клиентского сценария записи."""

    choose_service = State()
    choose_date = State()
    choose_time = State()
    confirm = State()
    phone = State()
    comment = State()
    resched_date = State()
    resched_time = State()
    review_rating = State()
    review_text = State()


class AdminStates(StatesGroup):
    """Состояния административных сценариев."""

    add_service_name = State()
    add_service_price = State()
    add_service_duration = State()
    add_service_category = State()
    add_service_desc = State()
    edit_service_field = State()
    broadcast_text = State()
