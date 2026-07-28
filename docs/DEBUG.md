# Історія налагодження

## 1. Невалідний токен Telegram-бота

**Команда:**

```powershell
.\.venv\Scripts\python.exe -m app.main
```

**Текст помилки:**

```text
telegram.error.InvalidToken: The token `<BOT_TOKEN>` was rejected by the server.
```

**Причина:**

Токен бота був у файлі `.env` і мав очікуваний формат Telegram-токена, але Telegram його відхилив. Зазвичай це означає, що токен неправильний, відкликаний, перевипущений або більше не є дійсним.

**Виправлення:**

Було згенеровано новий токен у Telegram через `@BotFather`, оновлено `BOT_TOKEN` у `.env` і перезапущено бота.

## 2. BOT_TOKEN не встановлено

**Команда:**

```powershell
.\.venv\Scripts\python.exe -m app.main
```

**Текст помилки:**

```text
2026-07-01 20:26:54,428 - __main__ - ERROR - BOT_TOKEN is not set
RuntimeError: BOT_TOKEN is not set. Add it to your .env file.
```

**Причина:**

Файл `.env` містив `BOT_TOKEN`, але в `app/main.py` більше не викликався `load_dotenv()`. Через це під час локального запуску Python не завантажував змінні з `.env`, а `os.getenv("BOT_TOKEN")` повертав `None`.

**Виправлення:**

У `app/main.py` було повернуто завантаження `.env` і зроблено його явним: файл `.env` визначається відносно кореня проєкту.

```python
project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")
```

Перевірено, що `BOT_TOKEN` успішно завантажується без виведення секретного значення.
