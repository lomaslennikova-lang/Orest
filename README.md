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

## Розгортання в Render та реєстрація DNS

Production-версія застосунку розгортається як один Render Web Service: `Dockerfile.render` збирає React frontend, а FastAPI віддає SPA, `/api/*` та `/health` з одного HTTPS-домену.

- Детальна інструкція: [docs/deploy.md](docs/deploy.md).
- Результат підключення власного домену: [docs/domain.md](docs/domain.md).
- Результати перевірки та скріншоти live-деплою: [docs/deploy/DEPLOY_NOTES.md](docs/deploy/DEPLOY_NOTES.md).

Секрети зберігайте лише у локальному `.env` та Render Environment Variables; не додавайте їх до Git.

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
POST /api/ai/analyze-transactions
POST /api/ai/attachments
GET /api/ai/actions/{action_id}
GET /api/ai/actions/{action_id}/receipt
PUT /api/ai/actions/{action_id}/draft
POST /api/ai/actions/{action_id}/confirm
POST /api/ai/actions/{action_id}/cancel
POST /api/ai/conversations
GET /api/ai/conversations/last
GET /api/ai/conversations/{conversation_id}/messages
GET /api/ai/prompt-suggestions
POST /api/ai/prompt-suggestions
DELETE /api/ai/prompt-suggestions/{suggestion_id}
```

## Налагодження

Файл `docs/DEBUG.md` містить історію помилок, які виникали під час запуску бота, та їхні виправлення. Для кожної ситуації там вказано команду запуску, текст помилки, причину та спосіб виправлення.

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
GEMINI_MODEL=gemini-flash-latest
```

Під час запуску Telegram-бот перевіряє доступність Gemini та записує результат у лог. Недоступність LLM не зупиняє бот: це дозволяє використовувати інші його можливості, поки ключ або мережа налаштовуються.

Адмінка має кнопку `Аналіз фінансового стану` на вкладці `Фінансовий стан`. Вона аналізує записи, що відповідають активним фільтрам, і блокується до отримання відповіді. Дані агрегуються backend-ом, а Gemini повертає структурований JSON з полями `summary`, `top_expense_categories`, `risks` та `advice`. Шаблон промпту збережений у `promts/financial_analysis_gemini.md`.

### AI-помічник

На окремій вкладці `AI-помічник` доступний чат для запитів про доходи, витрати,
категорії та їхню динаміку. Він зберігає активний діалог (до 50 повідомлень)
і відновлює його після оновлення сторінки. Кнопка `Очистити чат` створює новий
порожній діалог, не видаляючи попередню історію.

Підказки для чату зберігаються спільно в БД та обираються з dropdown. Адміністратор
може додавати й видаляти їх у панелі `Керувати підказками`. У тексті підказки
можна використовувати `{{month}}`: перед надсиланням він автоматично замінюється
на вибраний місяць.
Для поточного admin діє обмеження: не більше 10 звернень до AI-помічника за
60 секунд. У разі перевищення API повертає `429 Too Many Requests` і заголовок
`Retry-After`. Ліміт зберігається в пам'яті поточного API-процесу, що відповідає
поточному Docker-запуску з однією реплікою API.

У першій версії чат доступний лише поточному `admin` і аналізує агреговані дані
всіх користувачів. До Gemini передаються тільки результати контрольованих
read-only агрегатів, а не `DATABASE_URL`, SQL-запити або повний перелік
фінансових операцій. Одноразовий аналіз і чат не можна виконувати одночасно.

Перед першим запуском AI-чату застосуйте міграцію:

```powershell
docker compose run --rm --no-deps bot alembic upgrade head
```

Чат використовує ті самі `LLM_API_KEY` і `GEMINI_MODEL`, що й інший Gemini-
функціонал. У логах не слід записувати cookie, ключі, URL підключення до БД,
SQL або деталізовані фінансові операції.

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
  prompts.py
  ai_actions/
    __init__.py
    audit.py
    pending.py
    prompts.py
    receipt_llm.py
    receipts.py
    runtime.py
    schemas.py
    transactions.py
  ai_chat/
    __init__.py
    gemini.py
    graph.py
    prompts.py
    rate_limit.py
    repository.py
    schemas.py
    tools.py
alembic/
  env.py
  script.py.mako
  versions/
    20260726_01_add_ai_chat_tables.py
    20260730_02_add_ai_receipt_actions.py
    20260730_03_add_ai_action_execution_result.py
    20260804_04_add_google_drive_receipt_metadata.py
    20260809_05_add_ai_prompt_suggestions.py
    20260809_06_seed_ai_prompt_suggestions.py
promts/
  financial_analysis_gemini.md
  template.md
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
  ai/
    AI_ACTION_0.PNG
    AI_ACTION_1.PNG
    AI_ACTION_2.PNG
    ai_chat_prompt.md
    ai_plan_action.md
    ai_prompt_deploy.md
    AI_ASSISTANT_NOTES.md
    AI_ACTIONS_NOTES.md
    AI_CHAT_0.PNG
    AI_CHAT_1.PNG
    AI_CHAT_2.PNG
    AI_PROMT_NOTES.md
  deploy/
    DEPLOY_NOTES.md
    DEPLOY_0.PNG
    DEPLOY_1.PNG
    DEPLOY_2.PNG
    DEPLOY_3.PNG
    DEPLOY_4.PNG
  architecture.md
  architecture_example.md
  database.md
  DEBUG.md
  deploy.md
  homework/
    VibeCoding_Masliennikova_HW03.txt
    VibeCoding_Masliennikova_HW04.txt
    VibeCoding_Masliennikova_HW05.txt
    VibeCoding_Masliennikova_HW06.txt
    VibeCoding_Masliennikova_HW07.pdf
    VibeCoding_Masliennikova_HW08.pdf
    VibeCoding_Masliennikova_HW09.pdf
    VibeCoding_Masliennikova_HW10.pdf
    VibeCoding_Masliennikova_HW11.txt
    VibeCoding_Masliennikova_HW12.txt
  security.md
scripts/
  check-llm.ps1
  scan-secrets.ps1
tests/
  test_ai_action_pending.py
  test_ai_action_receipt_llm.py
  test_ai_action_runtime.py
  test_ai_chat_api.py
  test_ai_chat_gemini.py
  test_ai_chat_graph.py
  test_ai_chat_rate_limit.py
  test_ai_chat_tools.py
requirements.txt
.env.example
.gitignore
.dockerignore
README.md
Dockerfile
Dockerfile.render
docker-compose.yml
alembic.ini
Orest.png
```

Службові та секретні файли не наведені: `.env`, `.venv/`, `frontend/node_modules/`, frontend build-артефакти, `__pycache__/` і Git-метадані. Вони або ігноруються Git, або створюються локально.

## Приватне сховище чеків у Google Drive

Orest може зберігати нові AI-вкладення чеків у приватній папці Google Drive. За
замовчуванням, до повного налаштування Drive, застосунок використовує локальне
runtime-сховище; це зберігає сумісність із локальною розробкою. Після додавання
refresh token нові чеки завантажуються у Drive, а в Neon зберігаються лише їхні
метадані, хеш та `drive_file_id`. Файли не отримують публічних URL.

Для інтеграції потрібні `Google Drive API`, OAuth client типу **Web application**
і вузький scope `https://www.googleapis.com/auth/drive.file`.

1. У Google Cloud додайте redirect URI:
   `https://orest.onrender.com/api/admin/google-drive/callback`.
2. У Render Environment додайте `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
   `GOOGLE_DRIVE_FOLDER_ID` і `GOOGLE_OAUTH_REDIRECT_URI`.
3. Застосуйте Alembic-міграцію до Neon контрольовано з локальної машини:

   ```powershell
   .\.venv\Scripts\python.exe -m alembic upgrade head
   ```

4. Після deploy увійдіть як Admin та відкрийте
   `https://orest.onrender.com/api/admin/google-drive/connect`.
5. Після дозволу Google додайте одноразово показаний token як
   `GOOGLE_DRIVE_REFRESH_TOKEN` у Render Environment та перезапустіть сервіс.

Не передавайте жодне з цих значень у Git, логи або повідомлення. Докладна
інструкція та діагностика — у [документації інтеграції Drive](docs/deploy/google_drive_integration.md).
