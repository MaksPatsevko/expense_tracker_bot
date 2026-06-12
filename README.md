# Expense Tracker Bot

Telegram-бот для контролю особистих фінансів з аналітикою витрат, прибутків, бюджетних лімітів, CSV-експортом та інтеграцією з Monobank.

## Можливості

- додавання витрат і прибутків через кнопки;
- розпізнавання фінансових операцій з тексту;
- перегляд витрат за день, тиждень, місяць або власний період;
- побудова графіків витрат і динаміки;
- встановлення бюджетних лімітів;
- експорт фінансового звіту у CSV;
- підключення Monobank через webhook.

## Технології

- Python
- Aiogram
- PostgreSQL
- AsyncPG
- Matplotlib
- OpenAI API
- Monobank API

## Налаштування

1. Створіть віртуальне середовище та встановіть залежності:

```bash
pip install -r requirements.txt
```

2. Створіть файл `.env` на основі `.env.example`:

```env
BOT_TOKEN=
DATABASE_URL=
OPENAI_API_KEY=
WEBHOOK_BASE_URL=
```

3. Запустіть бота:

```bash
python main.py
```

## Безпека

Файли `.env`, `serviceAccountKey.json`, `.venv`, кеші Python і тимчасові звіти не додаються до репозиторію.
