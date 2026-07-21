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

### Docker admin dashboard

Запустити тільки web-адмінку:

```bash
docker compose up --build api frontend
```

Адмінка буде доступна за адресою:

```text
http://localhost:5173
```

API буде доступне за адресою:

```text
http://localhost:8000
```

Зупинити тільки web-адмінку:

```bash
docker compose stop api frontend
```

Зупинити всі сервіси:

```bash
docker compose down
```

У Docker Compose є кілька механізмів перезапуску:

- `restart: unless-stopped` перезапускає контейнер, якщо він впав або Docker daemon був перезапущений.
- `bot` запускається через `python -m app.dev`, тому `watchfiles` перезапускає бота при змінах у `app/`.
- `api` запускається через `uvicorn ... --reload`, тому API перезапускається при змінах у `app/`.
- `frontend` запускає Vite dev server, тому frontend оновлюється при змінах у `frontend/`.

## Web admin dashboard

Перед запуском web-адмінки додайте облікові дані адміністратора у `.env`:

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_admin_password_here
ADMIN_SESSION_SECRET=your_long_random_session_secret_here
```

`ADMIN_PASSWORD` - пароль для форми входу. `ADMIN_SESSION_SECRET` використовується API для підпису cookie-сесії адміністратора, тому зберігайте його приватно і не додавайте в git.

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

Вкладка dashboard:

- `Фінансовий стан` показує поточний фінансовий огляд українською мовою.
- Картки містять `Доходи`, `Витрати` і `Баланс`; баланс рахується як доходи мінус витрати.
- Картка фільтрів застосовується до всіх даних вкладки. Доступні фільтри за періодом дат (`Дата з`, `Дата по`), типом транзакції та користувачем.
- Таблиця `Transactions` використовує порядок стовпців: дата, сума, категорія, тип, користувач.

Вкладка `Редагування` доступна для admin-користувача:

- Таблиця `Transactions` підтримує inline-фільтри в заголовках стовпців `Дата`, `Тип` і `Користувач`.
- Перший рядок таблиці використовується для додавання нової транзакції.
- Нова транзакція завжди створюється від імені `admin`; користувач у рядку додавання показується як read-only значення.
- Поле дати для додавання приймає дату і час; дата та час не можуть бути пізніше поточного моменту.
- Сума має бути додатною, не більше `100 000 грн`, з кроком `1 грн`.
- Доданий рядок підсвічується блідо-зеленим до першого кліку в межах вкладки `Редагування`.
- Активний рядок підсвічується блідо-червоним після кліку по будь-якому полю або кнопці цього рядка; підсвітка переходить на інший рядок або зникає при кліку поза рядками.
- Існуючі транзакції можна видаляти кнопкою `Видалити`.

API endpoints:

```text
POST /api/login
POST /api/logout
GET /api/me
GET /api/summary
GET /api/transactions
POST /api/transactions
DELETE /api/transactions/{transaction_id}
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

## Перевірка LLM

Для використання Gemini додайте ключ до `.env`:

```env
LLM_API_KEY=your_gemini_api_key_here
```

Під час запуску Telegram-бот перевіряє доступність Gemini та записує результат у лог. Недоступність LLM не зупиняє бот: це дозволяє використовувати інші його можливості, поки ключ або мережа налаштовуються.

Для ручної перевірки з кореня проєкту виконайте:

```powershell
.\scripts\check-llm.ps1
```

Якщо PowerShell блокує запуск скрипта через execution policy:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check-llm.ps1
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
  api.py
  database.py
  dev.py
  llm.py
  main.py
  models.py
frontend/
  index.html
  package-lock.json
  package.json
  vite.config.js
  src/
    App.jsx
    main.jsx
    styles.css
docs/
  architecture.md
  architecture_example.md
  database.md
  security.md
scripts/
  check-llm.ps1
  scan-secrets.ps1
requirements.txt
.env.example
.gitignore
DEBUG.md
README.md
Dockerfile
docker-compose.yml
Orest.png
```
