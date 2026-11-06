"""Точка входа. Запуск: python bot.py

Два режима:
  - polling (по умолчанию): бот сам опрашивает Telegram;
  - webhook: бот принимает апдейты по HTTPS и отправляет события в вашу систему.

Переключение — переменными окружения:
  WEBHOOK_MODE=1
  WEBHOOK_HOST=bot.example.ru
  WEBHOOK_SECRET=<случайная строка>
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

import config
import database as db
import reminders

import handlers_client  # noqa: F401  регистрация клиентских хендлеров
import handlers_admin   # noqa: F401  регистрация админских хендлеров

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)


async def on_startup():
    db.init_db()
    commands = [
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="admin", description="Панель администратора"),
    ]
    await bot.set_my_commands(commands)
    logger.info("Бот запущен. Админы: %s", config.ADMIN_IDS)


def webhook_path() -> str:
    """Путь входящего вебхука: /webhook/<secret>."""
    path = config.WEBHOOK_PATH.rstrip("/") or "/webhook"
    if config.WEBHOOK_SECRET:
        path = "{}/{}".format(path, config.WEBHOOK_SECRET)
    return path


async def start_polling():
    """Режим polling: подходит для разработки и простого деплоя."""
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Режим: polling")
    await dp.start_polling(bot)


async def start_webhook():
    """Режим webhook: бот слушает HTTPS и не делает исходящих запросов к API."""
    if not config.WEBHOOK_HOST:
        raise RuntimeError("WEBHOOK_MODE=1 требует WEBHOOK_HOST (домен с HTTPS)")

    url = "https://{}{}".format(config.WEBHOOK_HOST, webhook_path())
    await bot.set_webhook(
        url,
        drop_pending_updates=True,
        max_connections=config.WEBHOOK_MAX_CONNECTIONS,
    )
    logger.info("Режим: webhook, url=%s", url)

    await dp.start_webhook(
        host="0.0.0.0",
        port=config.WEBHOOK_PORT,
        ssl_cert=config.WEBHOOK_SSL_CERT or None,
        ssl_key=config.WEBHOOK_SSL_KEY or None,
        allowed_updates=dp.resolve_used_update_types(),
    )


async def start_background_tasks():
    """Планировщик напоминаний и ежедневный дайджест админу."""
    tasks = [
        asyncio.create_task(
            reminders.reminder_loop(bot, interval=config.REMINDER_CHECK_INTERVAL)
        ),
        asyncio.create_task(
            reminders.daily_digest(bot, hour=config.DIGEST_HOUR)
        ),
    ]
    logger.info("Фоновые задачи запущены: %s", len(tasks))
    return tasks


async def main():
    await on_startup()
    await start_background_tasks()
    if config.WEBHOOK_MODE:
        await start_webhook()
    else:
        await start_polling()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")
