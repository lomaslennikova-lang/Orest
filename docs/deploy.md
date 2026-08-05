# Розгортання Orest у Render

## Призначення

Цей документ описує розгортання web-частини Orest як одного Render Web Service.
Поточне середовище є навчальним **Free demo**, а не production-середовищем.

## Архітектура

```text
Браузер
  │ HTTPS
  ▼
https://orest.onrender.com
  │ Render Web Service, Dockerfile.render
  ▼
FastAPI
  ├─ /health, /api/*
  └─ React SPA і /assets
  │
  ├─ Neon PostgreSQL: транзакції, діалоги, LangGraph checkpoints
  └─ Gemini API: фінансовий аналіз, AI-чат, receipt-to-draft
```

React і FastAPI працюють з одного домену. Це дає same-origin API-запити й
`HttpOnly` session cookie без production CORS між окремими frontend/backend
доменами.

`Dockerfile.render` — multi-stage image: Node збирає `frontend/dist`, Python
запускає FastAPI на `0.0.0.0:$PORT`. Render задає `PORT`; його не потрібно
створювати як Environment Variable. Папка `promts/` копіюється в image, бо
шаблон одноразового AI-аналізу читається сервером під час запиту.

## Змінні середовища

Додавати змінні в Render Dashboard → **Environment**. Реальні значення не
потрапляють до Git, Dockerfile, документації, screenshot-ів або логів.

| Змінна | Обов'язкова | Призначення |
| --- | --- | --- |
| `DATABASE_URL` | так | URL Neon PostgreSQL; для asyncpg потрібен TLS-параметр, наприклад `sslmode=require`. |
| `ADMIN_USERNAME` | так | Ім'я адміністратора. |
| `ADMIN_PASSWORD` | так | Пароль адміністратора. |
| `ADMIN_SESSION_SECRET` | так | Випадковий секрет підпису cookie сесії. |
| `LLM_API_KEY` | так для AI | Ключ Gemini API. |
| `GEMINI_MODEL` | так для AI | Назва моделі. Для поточного Free demo використовується `gemini-flash-lite-latest` через доступні квоти. |
| `LOG_LEVEL` | ні | Рівень логування; стандартне значення `INFO`. |
| `AI_RECEIPT_RETENTION_DAYS` | ні | Строк зберігання receipt metadata; стандартно 180. |
| `AI_AUDIT_LOG_RETENTION_DAYS` | ні | Строк зберігання audit metadata; стандартно 30. |

`ADMIN_SESSION_COOKIE_SECURE=true`, `AI_RECEIPT_STORAGE_DIR` та
`AI_AUDIT_LOG_DIR` установлюються у `Dockerfile.render`. Не перевизначайте
`ADMIN_SESSION_COOKIE_SECURE` значенням `false` у Render.

Локальний шаблон без секретів: [`.env.example`](../.env.example).

## Локальна перевірка перед deploy

Поточний development stack:

```powershell
docker compose up --build -d
```

Перевірки:

```powershell
Invoke-WebRequest http://localhost:8000/health
Invoke-WebRequest http://localhost:5173/
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
Set-Location frontend
npm.cmd run build
```

Збірка production image:

```powershell
docker build --file Dockerfile.render --tag orest-render-check .
docker run --rm --env-file .env -e PORT=10000 -p 10000:10000 orest-render-check
```

У другому терміналі:

```powershell
Invoke-WebRequest http://localhost:10000/health
```

Після перевірки зупиніть контейнер через `Ctrl+C`. Не передавайте `.env` у Git
або в повідомленнях.

## Налаштування Render

1. Створити **New → Web Service** з GitHub-репозиторію.
2. Вибрати гілку `deploy/render` і runtime **Docker**.
3. Указати Docker Build Context Directory: `.` та Dockerfile Path:
   `Dockerfile.render`.
4. Не вказувати Docker Command: використовується `CMD` Dockerfile.
5. Указати HTTP Health Check Path: `/health`.
6. Не задавати Pre-Deploy Command: міграції виконуються контрольовано, а не
   автоматично при кожному старті контейнера.
7. Додати Environment Variables вручну та створити сервіс.
8. У Render Deploys порівняти SHA live deploy з:

```powershell
git rev-parse HEAD
```

## Public-перевірка після deploy

```text
GET https://orest.onrender.com/health       → 200 {"status":"ok"}
GET https://orest.onrender.com/openapi.json → 200
GET https://orest.onrender.com/api/me       → 401 без session cookie
GET https://orest.onrender.com/              → React SPA, 200
```

`/health` виконує `SELECT 1` через підключення застосунку, тому його `200`
одночасно підтверджує доступність FastAPI та Neon.

Для AI перевірити login, одноразовий фінансовий аналіз та короткий запит у
AI-чаті. У Render Logs дивитися лише HTTP-коди, deploy SHA та технічні
повідомлення; не копіювати в документацію секрети, cookie, URL підключення до
БД або фінансові дані користувачів.

## Типові помилки

| Симптом | Імовірна причина | Дія |
| --- | --- | --- |
| `404` для `/api/*` одразу після створення сервісу | Render ще не завершив routing нового deploy або використано неправильний URL. | Дочекатися статусу **Live**, відкрити URL з Dashboard і перевірити SHA. |
| Health check не проходить | Неправильний `DATABASE_URL`, TLS, змінні admin/LLM або застосунок не слухає `$PORT`. | Перевірити Logs, `/health`, `Dockerfile.render` і Environment без розкриття значень. |
| `500` під час фінансового AI-аналізу | У production image відсутній prompt template. | Перевірити, що Dockerfile містить `COPY promts ./promts`. |
| `429 RESOURCE_EXHAUSTED` від Gemini | Вичерпано RPM/RPD/quota моделі. | Зупинити повторні запити, дочекатися відновлення ліміту, перевірити квоти в AI Studio й модель у `GEMINI_MODEL`. |
| `503` від Gemini | Тимчасова недоступність провайдера, timeout або перевантаження. | Повторити пізніше; retry має бути обмеженим. |
| `503` AI-чату при доступному `/health` | Може бути тимчасово недоступний LangGraph checkpointer у Neon. | Перевірити application logs і не змішувати цю помилку з quota Gemini. |
| `401` `/api/me` | Немає або завершилась cookie-сесія. | Увійти знову; без сесії це очікувана відповідь. |
| Receipt upload/AI дія працює лише тимчасово | Free Render не зберігає локальні файли. | Не вважати upload-и сталими; наступний етап — приватне зовнішнє сховище. |

## Обмеження Free Render

- Web Service засинає після 15 хвилин без вхідного трафіку; перший запит після
  цього може чекати близько хвилини на запуск.
- Файлова система тимчасова: зміни й файли зникають після restart, redeploy або
  sleep. Persistent disk недоступний на Free Web Service.
- Є місячні ліміти instance hours, bandwidth і build minutes; Render може
  перезапускати Free instance під час обслуговування.
- Free demo не є середовищем для сталого receipt storage, audit-log backup або
  гарантій доступності.

Офіційні джерела: [Render Web Services](https://render.com/docs/web-services),
[Docker on Render](https://render.com/docs/docker),
[Render Free](https://render.com/docs/free),
[Gemini API errors](https://ai.google.dev/gemini-api/docs/api-errors).

## Git-гігієна перед PR

```powershell
git status
git diff
git diff --check
powershell -ExecutionPolicy Bypass -File .\scripts\scan-secrets.ps1
```

Перед push перегляньте `git diff --cached`. `.env` має бути ігнорованим, а
`.env.example` — містити лише фіктивні шаблонні значення.

## Google Drive для приватних AI-чеків

Google Drive використовується лише для нових receipt-вкладень після повного
налаштування OAuth. У Neon залишаються метадані вкладення, зокрема
`drive_file_id`; посилання на файл не повертається frontend-у та файл не
робиться публічним. Існуючі локальні вкладення лишаються доступними.

### Environment Variables

У Render Dashboard → **Environment** збережіть лише як secrets:

| Змінна | Призначення |
| --- | --- |
| `GOOGLE_CLIENT_ID` | OAuth client ID типу Web application. |
| `GOOGLE_CLIENT_SECRET` | Секрет цього OAuth client. |
| `GOOGLE_DRIVE_FOLDER_ID` | ID приватної папки для чеків, не її URL. |
| `GOOGLE_OAUTH_REDIRECT_URI` | `https://orest.onrender.com/api/admin/google-drive/callback`. |
| `GOOGLE_DRIVE_REFRESH_TOKEN` | Довготривалий token, отриманий у завершенні OAuth. |

Не задавайте ці значення у Dockerfile, Git або screenshots.

### Підключення без Render Shell

Render Free не надає Shell, тому міграцію треба запускати контрольовано локально
з кореня проєкту. Перед командою переконайтеся, що локальний `.env` містить URL
цільової Neon-бази:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
```

Поточний head для Drive-метаданих — `20260804_04`. Не додавайте `alembic upgrade
head` до Docker command: перезапуски Free-сервісу не мають виконувати міграції.

### OAuth і smoke check

1. У Google Cloud увімкніть Google Drive API, створіть OAuth Web client і
   зареєструйте точний callback URI.
2. Додайте у Render усі змінні, крім refresh token, та задеплойте код.
3. Увійдіть в Orest як Admin і відкрийте
   `/api/admin/google-drive/connect` на домені Render.
4. Після згоди Google callback показує token лише для початкового перенесення в
   Render Environment. Додайте його, закрийте сторінку й перезапустіть сервіс.
5. Завантажте тестовий чек: файл має з'явитися у приватній папці Drive без
   доступу `anyone`/public, а AI-аналіз має прочитати його server-side.

`401` для `/api/admin/google-drive/connect` означає відсутню або прострочену
admin-сесію. `503` до першого OAuth-переходу означає, що одна з чотирьох
початкових Google-змінних відсутня або порожня.
