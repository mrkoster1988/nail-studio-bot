# Pushok Sketch Icons v1 — Студия услуг

Единый фирменный стиль: карандашная бирюзовая линия 24×24, янтарные детали, прозрачный фон, собственные значения вместо копирования Crypto Bot.

## Назначение по действующим функциям

- `booking`: `pi-calendar`
- `services`: `pi-scissors`
- `prices`: `pi-price`
- `my_bookings`: `pi-receipt`
- `bonuses`: `pi-gift`
- `reviews`: `pi-star`
- `masters`: `pi-users`
- `admin`: `pi-settings`
- `locations`: `pi-location`

SVG: `assets/pushok-icons.svg`. Для будущего веб-интерфейса можно использовать `<svg aria-hidden="true"><use href="/assets/pushok-icons.svg#pi-home"/></svg>` (после настройки маршрута статики).

**Нативные кнопки Telegram:** SVG нельзя отправлять в параметр `icon_custom_emoji_id`. Нужна отдельно зарегистрированная коллекция Telegram Custom Emoji и её реальные идентификаторы; до регистрации сохраняем текстовые кнопки без фиктивных ID. VK/MAX и Mini App — только после проверки доступного API и тестов.

Статус: подготовлен ресурс для внедрения, исходные обработчики и меню не изменены.
