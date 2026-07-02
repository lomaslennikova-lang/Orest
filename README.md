<img src="https://github.com/lomaslennikova-lang/Orest/blob/main/Orest.png" width="200">

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

Для запуску з автоматичним перезапуском при змінах у `app/`:

```bash
python -m app.dev
```

Якщо бот був запущений через `python app/main.py`, після зміни коду зупиніть його через `Ctrl + C` і запустіть знову.

На Windows замість `source .venv/bin/activate` використайте:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Docker

```bash
docker compose up --build
```

У Docker Compose бот також перезапускається при змінах у `app/`.

## Налагодження

Файл `DEBUG.md` містить історію помилок, які виникали під час запуску бота, та їхні виправлення. Для кожної ситуації там вказано команду запуску, текст помилки, причину та спосіб виправлення.

## Команди

- `/start` — запустити бота
- `/about` — коротко про бота
- `/help` — показати список команд

## Структура

```text
app/
  __init__.py
  dev.py
  main.py
requirements.txt
.env.example
.gitignore
DEBUG.md
README.md
Dockerfile
docker-compose.yml
```
