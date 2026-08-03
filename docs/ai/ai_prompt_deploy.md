# План розгортання Orest у Render

> Статус: **погоджено для реалізації Free demo**. Сховище receipt/audit файлів
> не входить до Lesson 13 і винесене в окремий наступний етап.

## 1. Мета й межі першого розгортання

Розгорнути поточну web-частину Orest як **один Render Web Service**:

```text
Користувач у браузері
        │ HTTPS
        ▼
Render public URL
        │ один Docker-контейнер
        ▼
FastAPI ──► віддає зібраний React (SPA) і `/api/*`
   │                 │
   │                 └── cookie сесії працює в межах того самого домену
   ▼
Neon PostgreSQL ──► постійні дані застосунку
   │
   └──► Gemini API (лише коли користувач викликає AI-функції)
```

Браузер звертається до одного HTTPS URL Render. FastAPI обробляє запити до
`/api/*` та `/health`, а для інших маршрутів повертає production-збірку React.
Тому не потрібно відкривати окремий Vite-сервер, налаштовувати міждоменний
CORS для production або передавати URL API в коді React. Cookie адміністратора
залишається same-origin, `HttpOnly` і не доступна JavaScript.

Цей урок не включає Telegram-бота як окремий Render service. Його запуск і
довготривале зберігання receipt/audit файлів треба спланувати окремо, бо
локальна файлова система Free Render не є постійною.

## 2. Що потрібно передбачити в проєкті

### Docker і запуск

- Додати окремий multi-stage `Dockerfile.render`: Node-етап збирає React,
  Python-етап установлює залежності та містить лише production-артефакти.
- Додати `.dockerignore`, щоб не надсилати в build context `.env`, `.git`,
  `.venv`, `frontend/node_modules`, `frontend/dist`, runtime-файли та інші
  локальні артефакти.
- Запускати Uvicorn на `0.0.0.0` і значенні `${PORT}`, яке Render задає для
  Web Service (типове значення Render — `10000`). Не використовувати
  `--reload` у production.
- Не запускати `alembic upgrade head` автоматично в кожному старті контейнера.
  Міграції запускаються контрольовано перед/під час deploy відповідно до
  погодженого способу, щоб уникнути паралельних або непомітних змін схеми.

### FastAPI і React

- Додати production-віддавання зібраного React через FastAPI: статичні assets
  з `frontend/dist/assets` і SPA fallback для не-API маршрутів. API-маршрути,
  `/health` та документація API не повинні перехоплюватися fallback-ом.
- Зберегти `/health` як швидкий endpoint готовності. Нині він перевіряє Neon
  через `SELECT 1` і повертає `{"status":"ok"}`; це відповідає перевірці
  доступності застосунку й БД.
- Залишити локальну розробку через `docker compose` без змін її поведінки;
  production Dockerfile має бути незалежним від volume-монтувань і Vite dev
  server.
- Перевірити налаштування cookie для HTTPS production (зокрема `Secure=True`)
  так, щоб локальний HTTP-режим не зламався. Оскільки frontend і backend мають
  один домен, `SameSite=Lax` є достатньою початковою політикою.
- Визначити production CORS явно або вимкнути його для same-origin сценарію;
  не додавати `*` разом із credentials.

### Дані та runtime-файли

- Передавати `DATABASE_URL` Neon лише через Render Environment Variables.
  Для `asyncpg` має зберігатися TLS-параметр, потрібний Neon (наприклад,
  `sslmode=require`), який поточний код уже перетворює на SSL-з'єднання.
- Вказати Render-змінні для admin-автентифікації та Gemini лише в Dashboard,
  не в Git, Dockerfile, логах, документації чи screenshot-ах.
- На Free Render не покладатися на `AI_RECEIPT_STORAGE_DIR` та
  `AI_AUDIT_LOG_DIR`: файлова система очищується після restart, redeploy або
  sleep. У Lesson 13 upload/action flow є лише тимчасовою демонстраційною
  функцією: його файли не вважаються збереженими. Стале приватне сховище
  винесене в наступний етап.

### Git-гігієна секретів

- До початку роботи перевірити `.gitignore`, `.env.example` та історію staged
  змін. `.env` має залишатися ігнорованим; `.env.example` містить тільки
  назви змінних і очевидно фіктивні значення.
- Не копіювати реальні значення з `.env` у commit, PR-опис, Render Blueprint,
  Docker build args, shell history або логи.
- Перед кожним commit запускати `./scripts/scan-secrets.ps1`, переглядати
  `git diff --cached` і за потреби скасовувати випадково додані секрети до
  commit. Якщо секрет уже потрапив у GitHub, його потрібно негайно відкликати
  та замінити, а не лише видалити з останнього файла.

## 3. План налаштування Render

Після появи й локальної перевірки `Dockerfile.render`:

1. Увійти в Render через GitHub та створити **New → Web Service**.
2. Вибрати репозиторій Orest, гілку `deploy/render`, регіон, найближчий до
   Neon, і runtime **Docker**.
3. Указати шлях Dockerfile: `Dockerfile.render`. Root directory — корінь
   репозиторію; Docker Command не перевизначати, якщо запуск описано в `CMD`.
4. Вибрати Free instance лише для навчального демо; production потребує
   платного тарифу та окремого рішення для файлів і backup.
5. У **Environment** додати секретні змінні вручну:
   `DATABASE_URL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`,
   `ADMIN_SESSION_SECRET`, `LLM_API_KEY`; за потреби — несекретні
   `GEMINI_MODEL`, retention-параметри та production-ознаку середовища.
   Значення `PORT` зазвичай задає Render; не фіксувати його у Git.
6. Установити HTTP health check path: `/health`.
7. Створити сервіс, дочекатися build/deploy і порівняти SHA в Render з
   `git rev-parse HEAD` гілки, яку було розгорнуто.
8. Перевірити public HTTPS URL: React SPA, `/health`, login, `GET /api/me`
   після login, базові API-операції та збереження даних у Neon. Проаналізувати
   build/runtime logs без виведення секретів.

Render автоматично надає HTTPS для Web Service й вимагає, щоб застосунок
слухав `0.0.0.0:$PORT`. Для HTTP health check Render перевіряє заданий маршрут
перед тим, як спрямувати трафік на новий deploy. Офіційні джерела:
[Web Services](https://render.com/docs/web-services),
[Docker on Render](https://render.com/docs/docker),
[Health Checks](https://render.com/docs/health-checks) і
[Environment Variables](https://render.com/docs/configure-environment-variables).

## 4. Відомі обмеження Free Render

- Після 15 хвилин без вхідного трафіку Free Web Service засинає; перший запит
  після цього може чекати приблизно хвилину на старт.
- Файлова система тимчасова: upload-и, audit JSONL і будь-які локальні зміни
  зникають після restart, redeploy або sleep; persistent disk недоступний на
  Free Web Service.
- Безкоштовний сервіс має місячні ліміти instance hours, bandwidth і build
  minutes; Render може перезапускати його під час обслуговування.
- Neon є зовнішньою БД, тому доступність deploy залежить також від правильної
  `DATABASE_URL`, TLS і мережевої доступності Neon.

Джерело обмежень: [Render Free](https://render.com/docs/free).

## 5. Послідовність реалізації після погодження

| № | Дія | Виконавець | Результат / перевірка |
| --- | --- | --- | --- |
| 1 | Підтвердити межі роботи: **Free demo**; AI upload/action flow має тимчасове локальне сховище без гарантії збереження. | Користувач | Зафіксовані межі Lesson 13. |
| 2 | Перевірити чистоту репозиторію, `.gitignore`, `.env.example` та запустити secret scan. | Codex | Відсутні реальні секрети в індексі й diff. |
| 3 | Створити гілку `deploy/render` від актуального `main`. | Користувач | `git branch --show-current` → `deploy/render`. |
| 4 | Запустити наявний стек через `docker compose`; перевірити frontend, API, `/health` і БД локально. | Codex | Локальний baseline до deployment-змін. |
| 5 | Реалізувати й перевірити `Dockerfile.render`, `.dockerignore`, production-збірку React, FastAPI static serving, `$PORT`, cookie/CORS production-конфігурацію. | Codex | Один контейнер віддає SPA, API та health. |
| 6 | Оновити `.env.example` тільки переліком необхідних змінних і безпечними прикладами. | Codex | `git diff` не містить реальних значень. |
| 7 | Зібрати Render image локально та повторно запустити `docker compose`; виконати backend-тести, frontend build, health/API smoke checks. | Codex | Відтворювані результати перевірок. |
| 8 | Створити Render Web Service і безпечно додати Environment Variables у Dashboard. | Користувач | Секрети є тільки в Render / локальному `.env`. |
| 9 | Дочекатися deploy, звірити commit SHA, перевірити HTTPS URL, `/health`, API/login, Neon і logs. | Користувач + Codex | Підтверджений deploy або список діагностованих помилок. |
| 10 | Написати `docs/deploy.md`: архітектура, перелік змінних без значень, команди запуску, health endpoint, типові помилки й Free-обмеження. | Codex | Інструкція відтворює deploy без розкриття секретів. |
| 11 | Виконати фінальну Git-гігієну: `git status`, `git diff`, `git diff --check`, tests/build та secret scan. | Codex | Чистий, перевірений diff. |
| 12 | Створити змістовні commit-и, push `deploy/render`, відкрити PR, перевірити diff і після вашого схвалення виконати merge у `main`. | Користувач | Історія змін і main відповідають успішному deploy. |

## 6. Критерії готовності Lesson 13

- Render розгортає конкретний commit з `deploy/render` через `Dockerfile.render`.
- Public HTTPS URL показує React, а `GET /health` повертає `200` і
  `{"status":"ok"}`.
- API після login працює з cookie на тому самому домені, а тестові зміни даних
  видно в Neon.
- Secrets відсутні в Git, diff, Docker image instructions, документації та
  logs; `.env.example` придатний як безпечний шаблон.
- `docs/deploy.md` містить інструкцію експлуатації й обмеження Free Render.
- PR перевірений і merge у `main` виконано тільки після підтвердження успішного
  deploy та вашого погодження.

## 7. Наступний етап: приватне сховище Google Drive

Після завершення Lesson 13 окремо спланувати й погодити інтеграцію Google
Drive API для receipt-файлів та audit-експорту. Для особистого навчального
проєкту рекомендовано OAuth 2.0 і окрему приватну папку Drive. Backend
завантажуватиме файли, а в Neon зберігатимуться лише `drive_file_id`, хеш,
розмір, тип і дата. Файли не мають ставати публічними за посиланням.

Секрети `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, refresh token і ID папки
зберігатимуться тільки в Render Environment Variables. Конкретні scopes,
retention-політика, видалення файлів, обробка квот і тести будуть предметом
окремого плану; вони не є частиною цього deploy.

## 8. Стійкість Gemini після першого deploy

Під час перевірки Free demo Gemini періодично повертав тимчасові помилки
`429`, `500`, `502`, `503`, `504`, а також міг не відповідати в межах timeout.
Для receipt-to-draft і текстового AI-чату реалізовано однакову обмежену
політику: до трьох спроб із паузами 0,5 с і 1 с. Не повторюються невалідний
запит, неправильна конфігурація, невалідний JSON або відповідь, що не пройшла
валідацію.

Для AI-чату вичерпаний retry-budget тепер повертає HTTP `503`, а frontend
показує помилку та дозволяє повторити запит. Неуспішня відповідь Gemini не
зберігається як повідомлення assistant зі статусом `200`. Натомість
контрольований ліміт у чотири tool-кроки лишається відповіддю `200`, бо це
коректно завершений запит у межах політики графа.

Для receipt-to-draft після вичерпання спроб API також повертає `503`; чернетка
дії та транзакції не створюються. Усі retry-тести ізольовані від зовнішнього
Gemini API й перевіряють успіх після одного тимчасового `503`.
