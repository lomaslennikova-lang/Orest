# Security

## Секрети в проекті

Секрети - це приватні дані, які дають доступ до сервісів або бази даних.

Приклади секретів:

- Telegram bot token;
- `DATABASE_URL`;
- паролі;
- API keys.

Store secrets according to the runtime where they are used:

- local runtime secrets → `.env`;
- deployed runtime secrets → Render Environment Variables / secret settings;
- repository template → `.env.example` only, with no real values.

У GitHub треба додавати лише `.env.example`, де є назви змінних без реальних значень:

```env
BOT_TOKEN=your_telegram_bot_token_here
DATABASE_URL=your_database_url_here
```

Реальні секрети не можна комітити в GitHub, тому що їх можуть побачити інші люди. Якщо секрет потрапив у GitHub, його потрібно одразу змінити або відкликати.
