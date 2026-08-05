# План інтеграції приватного сховища Google Drive

**Статус:** погоджено для реалізації.

## 1. Межі рішення

- Google Drive зберігає лише чеки та export audit-log; у Neon лишаються їхні
  метадані й `drive_file_id`.
- Файли не отримують permission `anyone` або `public` і не мають публічних URL.
- Для особистого проєкту використовується один Google-акаунт і OAuth 2.0 Web
  application з offline access. Це дає серверу змогу оновлювати access token
  через refresh token.
- Під час OAuth backend перевіряє одноразовий криптографічний параметр `state`.
  Refresh token не передається frontend-у та не потрапляє до логів.

## 2. Налаштування Google Cloud

1. Створити або обрати Google Cloud project і ввімкнути Google Drive API.
2. Налаштувати OAuth consent screen та OAuth client типу **Web application**.
3. Додати точні redirect URI для локального середовища і Render, наприклад
   `/api/admin/google-drive/callback`.
4. Створити окрему приватну папку `Orest private storage`. Її ID передається
   через змінну середовища або папка створюється застосунком під час першого
   підключення.
5. Використати мінімальний OAuth scope:
   `https://www.googleapis.com/auth/drive.file`.

Scope `drive.file` дає застосунку змогу створювати, читати, змінювати та
видаляти лише файли, з якими він працює. Докладніше: [Google Drive API
scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth).

## 3. OAuth-підключення

- Доступ до старту OAuth і callback має лише автентифікований Admin.
- Backend генерує `state`, зберігає його server-side або у захищеній сесії та
  звіряє значення в callback.
- Для фонових операцій запитується offline access; access token оновлюється
  server-side через refresh token.
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_DRIVE_REFRESH_TOKEN`,
  `GOOGLE_DRIVE_FOLDER_ID` і `GOOGLE_OAUTH_REDIRECT_URI` зберігаються лише в
  Render Environment Variables та локальному `.env`, але ніколи не в Git.
- Якщо refresh token відкликаний або недійсний (`invalid_grant`), Drive-операції
  завершуються контрольованою помилкою «потрібно повторно підключити Google
  Drive» без видалення даних із БД.

## 4. Adapter сховища та модель даних

- Наявне локальне receipt-сховище відокремлюється за інтерфейсом із методами
  `store`, `read` і `delete`.
- Реалізується `GoogleDriveReceiptStorage`: він завантажує перевірений файл у
  приватну папку Drive і повертає його ID.
- До `AIReceiptAttachment` додаються явне поле `drive_file_id` та ознака
  backend-а сховища. Наявний `storage_key` не використовується як ID Drive.
- Для зміни схеми створюється Alembic migration із перевіркою rollback.
- Порядок запису: завантаження в Drive, запис метаданих у БД, компенсаційне
  видалення Drive-файлу в разі помилки commit БД.
- Для передачі чеку в Gemini файл завантажується лише server-side за
  `drive_file_id`; frontend не отримує посилання на файл.

## 5. Retention, cleanup і audit export

- Чеки зберігаються 180 днів.
- Audit export зберігається 30 днів.
- Cleanup спершу видаляє приватний Drive-файл, а після успіху — його метадані
  з Neon. Повторний запуск має бути ідемпотентним.
- Audit JSONL експортується у приватну папку Drive за датою, наприклад
  `audit/YYYY-MM-DD/...`, і містить лише наявний безпечний audit-record.
- Для `429`, `5xx`, timeout і quota застосовуються обмежені повтори з backoff.
  За незворотної помилки неповний запис не створюється.

## 6. Конфігурація та документація

- `.env.example` оновлюється лише назвами змінних і фіктивними значеннями.
- Оновлюються `docs/ai/ai_prompt_deploy.md`, `docs/deploy/DEPLOY_NOTES.md` та
  README: OAuth setup, змінні Render, правила приватності й відновлення після
  відкликання токена.
- У документацію, Git, приклади й логи не потрапляють реальні ID папок,
  client secret або refresh token.

## 7. Перевірки

- Unit-тести Drive adapter-а: upload, download, delete, timeout, помилки API,
  `invalid_grant` та ідемпотентне cleanup.
- Інтеграційні тести: upload → метадані в БД → AI extraction → expiry cleanup,
  а також компенсаційне видалення після помилки commit БД.
- Smoke check з окремою тестовою папкою Drive: файл створений, не має
  публічного доступу і видаляється після строку retention.
- Перед завершенням: backend/frontend тести, міграції, `git diff --check` та
  secret scan.

## Погоджені параметри

| Параметр | Рішення |
| --- | --- |
| OAuth scope | `drive.file` |
| Retention чеків | 180 днів |
| Retention audit export | 30 днів |
| Спосіб OAuth | Одноразовий Admin-only маршрут у застосунку |

## Офіційні джерела

- [OAuth 2.0 для web server applications](https://developers.google.com/identity/protocols/oauth2/web-server?authuser=19)
- [OAuth 2.0 best practices](https://developers.google.com/identity/protocols/oauth2/resources/best-practices)
- [Google Drive API scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth)
