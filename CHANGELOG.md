# CHANGELOG

## 1.2.2 — 2026-11-03
- LICENSE (MIT)
- README: CI-бейдж пайплайна, ссылка на лицензию

## 1.2.1 — 2026-11-03
- README.md: полное описание проекта, скриншоты интерфейса
- docs/screenshots: 4 скриншота (приветствие, запись, мои записи, админ-панель)

## 1.2.0 — 2026-11-03
- backup.py: безопасный бэкап SQLite (backup API), ротация 14 копий
- Бэкап запускается автоматически после утреннего дайджеста (9:00)
- Дайджест админу: ожидаемая выручка за день
- docker-compose: healthcheck (живость процесса, работает в обоих режимах)

## 1.1.0 — 2026-11-03
- CI: .gitlab-ci.yml — тесты при каждом пуше и в merge request
- Приветствие: WELCOME_TEXT в конфиге, персонализация по имени клиента
- .env.example: WELCOME_TEXT вместо MENU_WELCOME_TEXT

## 1.0.0 — 2026-11-03
- Тесты: 9/9 зелёные (test_scheduling — планировщик, test_database — база)
- test_database: изолированная временная база (подмена config.DB_PATH)
- VK: запись через try_add_booking (защита от двойной записи)
- VK: уведомление админам в Telegram о заявках из VK
- telegram_notify: уведомления админам из внешних каналов без aiogram

## 0.9.0 — 2026-11-03
- Zashchita ot dvoynoy zapisi: unique partial index na aktivnyy slot + try_add_booking
- Otmena zapisi klientom: sbros napominaniy i sobytiya kalendarya
- Ball -> skidka: spend_points, balans v «Moi zapisi» (1 ball = 1 R skidki)

## 0.8.0 — 2026-11-03
- VPN-promo knopka v glavnom menyuy Telegram-bota (GCAL vmeste s etim)
- VK: polnaya FSM-zapis — usluga -> data -> vremya -> podtverzhdenie
- VK: klienty popadayut v obschuyu bazu (tg_id = -vk_id)
- database: get_service, upsert_user_vk

## 0.7.0 — 2026-11-03
- Google Calendar: создан отдельный календарь «Студия маникюра», интеграция подключена
- gcal_sync.py: one-way синхронизация бот -> календарь (создание/обновление/удаление событий)
- bookings.calendar_event_id: ключ дедупликации события
- GCAL_ENABLED/GCAL_CALENDAR_ID в конфиге (по умолчанию выключено, бот не зависит от календаря)

## 0.6.0 — 2026-11-03
- MAX-бот (max_bot.py): long poll для разработки + webhook для production
- MAX: поддержка inline-кнопок, каталог/контакты, POST /answers-совместимая логика
- MAX: проверка секрета в X-Max-Bot-Api-Secret (webhook), лимит 30 rps учтён

## 0.5.0 — 2026-11-03
- Dockerfile + docker-compose: деплой одной командой, volume для SQLite
- VK-бот (vk_bot.py): long poll и Callback API, общая база с Telegram-ботом
- VK: меню (запись/каталог/контакты), маршрут к Telegram для записи
- .env.example: VK_GROUP_ID

## 0.4.0 — 2026-11-03
- Уведомление админу о новой заявке сразу при создании записи
- Бонусные баллы: +10 за визит, +5 за отзыв, +50 за приведённого друга
- Автосбор отзывов: оценка 1–5 звёзд после завершения визита
- Реферальные ссылки вида /start ref_<tg_id> с уведомлением пригласившему
- Таблицы: reviews, points_ledger, referrals

## 0.3.0 — 2026-11-03
- КРИТИЧЕСКИЙ ФИКС: восстановлен scheduling.py — бот падал на старте (ModuleNotFoundError)
- Версионирование: VERSION, versioning.py, теги релиза vMAJOR.MINOR.PATCH
- Заведён CHANGELOG

## 0.2.0 — 2026-11-02
- Напоминания за 24ч и 2ч до визита (reminders.py, отметки в БД)
- Ежедневный дайджест админу (расписание на сегодня и завтра)
- Перенос записи на другое время (со сбросом напоминаний)
- Исходящие webhook-уведомления с HMAC-SHA256 подписью
- Режим запуска webhook вместо polling

## 0.1.0 — 2026-11-01
- Первый релиз: запись онлайн, каталог, FSM, админ-панель, SQLite
