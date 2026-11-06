"""Конфигурация бота студии маникюра.

Все параметры переопределяются переменными окружения (см. .env.example).
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

BASE_DIR = Path(__file__).resolve().parent

# --- Telegram -------------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "PASTE_BOT_TOKEN_HERE")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").replace(",", " ").split() if x.strip()]

# --- Database -------------------------------------------------------------
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "data" / "studio.db"))

# --- Студия ---------------------------------------------------------------
STUDIO_NAME = os.getenv("STUDIO_NAME", "Студия маникюра «Лотос»")
STUDIO_ADDRESS = os.getenv("STUDIO_ADDRESS", "Москва, ул. Цветочная, 15")
STUDIO_PHONE = os.getenv("STUDIO_PHONE", "+7 (999) 123-45-67")
STUDIO_EMAIL = os.getenv("STUDIO_EMAIL", "hello@lotos-nails.ru")
STUDIO_INSTAGRAM = os.getenv("STUDIO_INSTAGRAM", "@lotos_nails")
STUDIO_MAP_URL = os.getenv(
    "STUDIO_MAP_URL", "https://yandex.ru/maps/?text=Москва, ул. Цветочная, 15"
)

# --- Расписание -----------------------------------------------------------
WORKING_HOURS = os.getenv("WORKING_HOURS", "10:00-20:00")
# 1 = понедельник ... 7 = воскресенье
WORKING_DAYS = [int(d) for d in os.getenv("WORKING_DAYS", "1,2,3,4,5,6").split(",") if d.strip()]
SLOT_STEP_MIN = int(os.getenv("SLOT_STEP_MIN", "15"))
BOOKING_HORIZON_DAYS = int(os.getenv("BOOKING_HORIZON_DAYS", "30"))
DEFAULT_SERVICE_DURATION = int(os.getenv("DEFAULT_SERVICE_DURATION", "60"))
MIN_LEAD_MINUTES = int(os.getenv("MIN_LEAD_MINUTES", "120"))
MAX_ACTIVE_BOOKINGS = int(os.getenv("MAX_ACTIVE_BOOKINGS", "3"))

# --- Тексты кнопок -------------------------------------------------------
BTN_CATALOG = "💅 Услуги и цены"
BTN_BOOK = "📅 Записаться"
BTN_MY = "📋 Мои записи"
BTN_CONTACTS = "📞 Контакты"
BTN_HOWTO = "📍 Как добраться"
BTN_HELP = "❓ Помощь"

MAIN_MENU_TEXT = f"💅 {STUDIO_NAME}\n\nВыберите, что вам нужно:"

# --- Webhook: входящий (запуск бота вместо polling) ----------------------
# Включите, если бот работает за HTTPS-доменом. Для прода — предпочтительнее polling.
WEBHOOK_MODE = os.getenv("WEBHOOK_MODE", "0").lower() in ("1", "true", "yes")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "")            # например bot.example.ru
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8080"))
# Секрет в пути: /webhook/<secret> — защита от чужих запросов
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
# SSL: путь к сертификату и ключу (если terminates на nginx — оставьте пустым)
WEBHOOK_SSL_CERT = os.getenv("WEBHOOK_SSL_CERT", "")
WEBHOOK_SSL_KEY = os.getenv("WEBHOOK_SSL_KEY", "")
# Сколько секунд Telegram будет повторять доставку апдейта при ошибке
WEBHOOK_MAX_CONNECTIONS = int(os.getenv("WEBHOOK_MAX_CONNECTIONS", "40"))

# --- Webhook: исходящий (уведомления в вашу систему) ---------------------
# POST уходит при создании записи и при каждой смене статуса.
OUTGOING_WEBHOOK_URL = os.getenv("OUTGOING_WEBHOOK_URL", "")
OUTGOING_WEBHOOK_SECRET = os.getenv("OUTGOING_WEBHOOK_SECRET", "")
OUTGOING_WEBHOOK_TIMEOUT = int(os.getenv("OUTGOING_WEBHOOK_TIMEOUT", "10"))

# --- Напоминания ----------------------------------------------------------
# Как часто планировщик проверяет расписание (секунды)
REMINDER_CHECK_INTERVAL = int(os.getenv("REMINDER_CHECK_INTERVAL", "60"))
# Час отправки ежедневного дайджеста админу (по локальному времени сервера)
DIGEST_HOUR = int(os.getenv("DIGEST_HOUR", "9"))
# Напоминать за 24 часа и за 2 часа до визита
REMINDER_HOURS_BEFORE = [int(x) for x in os.getenv("REMINDER_HOURS_BEFORE", "24,2").split(",") if x.strip()]


# --- Внешний вид (гибко настраивается через env) --------------------------
# Эмодзи-темы: их можно менять без правок кода
EMOJI_STYLE = os.getenv("EMOJI_STYLE", "default")
EMOJI_MENU_BOOK = os.getenv("EMOJI_MENU_BOOK", "📅")
EMOJI_MENU_CATALOG = os.getenv("EMOJI_MENU_CATALOG", "💅")
EMOJI_MENU_MY = os.getenv("EMOJI_MENU_MY", "📋")
EMOJI_MENU_CONTACTS = os.getenv("EMOJI_MENU_CONTACTS", "📞")
EMOJI_MENU_HELP = os.getenv("EMOJI_MENU_HELP", "❓")
EMOJI_MENU_HOWTO = os.getenv("EMOJI_MENU_HOWTO", "📍")
EMOJI_NEUTRAL_MODE = os.getenv("EMOJI_NEUTRAL_MODE", "0").lower() in ("1", "true", "yes")
# Приветственный текст меню (можно полностью заменить)
MENU_WELCOME_TEXT = os.getenv("MENU_WELCOME_TEXT", "")
# Длина сообщения «Ваша запись создана» — экономия внимания клиента
BRIEF_CONFIRMATIONS = os.getenv("BRIEF_CONFIRMATIONS", "0").lower() in ("1", "true", "yes")

# --- VPN-промо (вкл/выкл, настраиваемое) ----------------------------------
VPN_PROMO_ENABLED = os.getenv("VPN_PROMO_ENABLED", "0").lower() in ("1", "true", "yes")
VPN_PROMO_TITLE = os.getenv("VPN_PROMO_TITLE", "🎁 Скидка на VPN")
VPN_PROMO_TEXT = os.getenv(
    "VPN_PROMO_TEXT",
    "Пока вы на маникюре — подключите надёжный VPN со скидкой!",
)
VPN_PROMO_URL = os.getenv("VPN_PROMO_URL", "")
VPN_PROMO_DISCOUNT_PCT = int(os.getenv("VPN_PROMO_DISCOUNT_PCT", "15"))
VPN_PROTOCOLS = [p.strip() for p in os.getenv("VPN_PROTOCOLS", "VLESS,WireGuard").split(",") if p.strip()]

# --- VK: бот + сообщество (заготовка под будущую интеграцию) ---------------
VK_ENABLED = os.getenv("VK_ENABLED", "0").lower() in ("1", "true", "yes")
VK_COMMUNITY_TOKEN = os.getenv("VK_COMMUNITY_TOKEN", "")
VK_API_VERSION = os.getenv("VK_API_VERSION", "5.199")
VK_CONFIRMATION_CODE = os.getenv("VK_CONFIRMATION_CODE", "")

# --- MAX: уведомления и чат-бот --------------------------------------------
MAX_ENABLED = os.getenv("MAX_ENABLED", "0").lower() in ("1", "true", "yes")
MAX_BOT_TOKEN = os.getenv("MAX_BOT_TOKEN", "")
MAX_API_BASE = os.getenv("MAX_API_BASE", "https://platform-api2.max.ru")
MAX_WEBHOOK_SECRET = os.getenv("MAX_WEBHOOK_SECRET", "")

# --- Google Calendar: синхронизация записей -------------------------------
GCAL_ENABLED = os.getenv("GCAL_ENABLED", "0").lower() in ("1", "true", "yes")
# ID отдельного календаря студии (создан Mira): записи не смешиваются с личным
GCAL_CALENDAR_ID = os.getenv(
    "GCAL_CALENDAR_ID",
    "6b9abee989affe0d5e9f2f9a342f84c0fc2557749446b6fe7177febd392fe54b@group.calendar.google.com",
)
