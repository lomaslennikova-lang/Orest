# Orest Telegram Bot

Каркас Telegram-бота на Python.

## Швидкий старт

1. Створіть файл `.env` на основі прикладу:

```bash
cp .env.example .env
```

2. Додайте токен бота у `.env`:

```env
BOT_TOKEN=your_telegram_bot_token_here
```

3. Запустіть локально:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app/main.py
```

На Windows замість `source .venv/bin/activate` використайте:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Docker

```bash
docker compose up --build
```

## Структура

```text
app/
  main.py
requirements.txt
.env.example
.gitignore
README.md
Dockerfile
docker-compose.yml
```
