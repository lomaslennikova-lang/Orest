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

## Web admin dashboard

Backend API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api:app --reload
```

React frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

API endpoints:

```text
GET /api/summary
GET /api/transactions
```

## Налагодження

Файл `DEBUG.md` містить історію помилок, які виникали під час запуску бота, та їхні виправлення. Для кожної ситуації там вказано команду запуску, текст помилки, причину та спосіб виправлення.

## Перевірка секретів

Для пошуку випадково доданих токенів, паролів або інших секретів використовується `detect-secrets`.

Встановіть або оновіть залежності:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Після цього запустіть сканування:

```powershell
.\scripts\scan-secrets.ps1
```

Скрипт виводить стислий результат: кількість знахідок і список `файл:рядок - тип`.
Для вибору файлів використовується `git ls-files --cached --others --exclude-standard`, тому сканування враховує `.gitignore` і не аналізує `.env`, `.venv/`, `venv/`, `frontend/node_modules/`, `frontend/dist/` та інші проігноровані файли.
Додатково зі сканування виключено `.env.example`, бо це файл-приклад конфігурації.

Якщо PowerShell блокує запуск скрипта через execution policy, запустіть:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\scan-secrets.ps1
```

## Команди

- `/start` — запустити бота
- `/about` — коротко про бота
- `/help` — показати список команд
- `/expense <amount> <category>` — додати витрату
- `/income <amount> <category>` — додати дохід
- `/daily_expenses <YYYY-MM>` — показати суму денних витрат за місяць

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
scripts/
  scan-secrets.ps1
```
