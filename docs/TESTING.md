# Orest — Testing and Verification

> This document defines how changes to Orest are verified.
>
> The goal is not to run every possible check after every task.
> The goal is to run the smallest sufficient set of checks that provides credible evidence for the affected behavior and risk.
>
> AI-agent completion rules are defined in `AGENTS.md`.
> This document provides the concrete verification policy and commands.
>

---

## 1. Verification principle

Verification should be proportional to:

- the area changed;
- the number of affected components;
- the risk of regression;
- the presence of persistent or external side effects;
- whether shared logic or a stable contract changed.

Use this model:

```text
small isolated change
        ↓
targeted verification

shared / cross-cutting change
        ↓
broader automated verification

runtime / deployment change
        ↓
integration or deployment-like verification
```

Implementation is not completion.

A task is considered verified only when:

```text
relevant automated checks
        +
required build/runtime checks
        +
final diff review
        +
known gaps explicitly reported
```

---

## 2. Current testing baseline

### Backend / Python

The repository currently uses Python `unittest`.

Current test modules are concentrated primarily around:

- AI pending actions;
- receipt LLM processing;
- AI action runtime;
- AI chat API;
- Gemini adapter behavior;
- LangGraph/chat flow;
- AI rate limiting;
- AI tools;
- Google Drive integration.

Current automated coverage is not uniform across the whole application.

In particular, there is currently no equivalent dedicated test coverage for every area such as:

- all admin auth flows;
- all manual transaction CRUD flows;
- Telegram command behavior;
- React UI behavior.

Do not claim those areas are automatically verified unless appropriate tests were actually added and run.

### Frontend

The current frontend package provides:

```text
npm run dev
npm run build
npm run preview
```

There is currently no configured automated frontend test command.

Therefore, the current frontend verification baseline is:

```text
production build
        +
relevant manual UI check
```

If frontend automated tests are added later, update this document.

---

## 3. Verification levels

### Level 0 — Diff-only verification

Use for:

- documentation-only changes;
- comments;
- non-functional text edits;
- changes that cannot affect runtime behavior.

Minimum:

```bash
git status
git diff
git diff --check
```

Also run the secret scan if documentation/configuration touches:

- environment variables;
- credentials;
- authentication;
- deployment;
- provider configuration.

---

### Level 1 — Targeted verification

Use for:

- isolated backend changes;
- changes with a clearly bounded module;
- fixes with an existing focused regression test.

Example:

```bash
python -m unittest tests.test_ai_chat_rate_limit
```

Targeted verification is acceptable when the changed logic is not shared across multiple unrelated flows.

---

### Level 2 — Broad backend verification

Use when changing:

- shared validation;
- shared schemas;
- database models;
- reusable financial/domain logic;
- authentication helpers;
- shared API behavior;
- common AI workflow foundations.

Run the full Python test suite:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

Windows virtual-environment form:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

---

### Level 3 — Integration/runtime verification

Use when the change affects interaction between major components, for example:

```text
FastAPI <-> database
React <-> FastAPI
AI runtime <-> provider
receipt storage <-> Google Drive
Docker <-> application
```

Possible checks include:

- API smoke test;
- authenticated flow;
- browser UI flow;
- database connectivity;
- Docker Compose service startup;
- external-provider smoke where justified.

Only run the integration checks relevant to the changed behavior.

---

### Level 4 — Deployment-like verification

Use for changes involving:

- `Dockerfile.render`;
- production frontend build;
- `requirements.txt`;
- runtime entrypoint;
- deployed static/SPA serving;
- production paths;
- environment/configuration changes;
- Render-specific behavior.

Typical minimum:

```bash
docker build --file Dockerfile.render --tag orest-render-check .
```

Runtime smoke should use safe development/test configuration only.

---

## 4. Universal Git preflight

For every code task, before completion:

```bash
git status
git diff
git diff --check
```

Review the final diff for:

- unrelated files;
- accidental refactors;
- temporary debug code;
- `print()` statements left by debugging;
- conflict markers;
- generated files;
- secret leakage;
- accidental contract changes;
- changes outside task scope.

`git diff --check` passing does not replace code/runtime testing.

---

## 5. Backend / Python tests

### Targeted tests first

For an isolated change, run the closest relevant module(s).

Examples:

```bash
python -m unittest tests.test_ai_chat_rate_limit
python -m unittest tests.test_google_drive
python -m unittest tests.test_ai_action_pending
```

### Full suite

Run the full suite when:

- shared logic changed;
- several backend modules changed;
- database models changed;
- API foundations changed;
- AI workflow foundations changed;
- the change is cross-cutting;
- targeted scope is uncertain.

Command:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

### Shared logic and parallel-runtime rule

When shared logic changes, test all materially affected consumers.

Example:

```text
shared transaction validation
        │
        ├── manual transaction creation
        └── AI-confirmed transaction creation
```

A passing test for only one consumer is not sufficient if the shared behavior affects both.

Also note that Telegram transaction creation currently uses separate command logic in `app/main.py` rather than the web/AI shared transaction helper. If a task changes a **product-level transaction rule**, inspect and verify the Telegram path as well, even when the shared web/AI helper itself is unchanged.

---

## 6. Tests must protect intended behavior

When behavior changes:

- add or update relevant regression tests;
- include important failure cases.

Do not weaken or rewrite a valid test merely to make failing implementation code pass.

If a test appears outdated:

1. determine the intended contract;
2. compare with code, API contracts, decisions, and task requirements;
3. only then update the test if the expected behavior has intentionally changed.

---

## 7. Frontend verification

For changes under `frontend/`, run:

```bash
cd frontend
npm run build
```

Use `npm install` / `npm ci` only when dependencies are missing or the task changes dependency state.

A successful build verifies that the production frontend compiles.

Because automated frontend tests are not currently configured, user-facing behavior changes also require a focused manual UI check.

### Example manual UI check

For a transaction form change:

```text
1. Login.
2. Open the relevant transaction UI.
3. Perform the changed action.
4. Verify expected state.
5. Reload if persistence matters.
6. Verify persisted result remains correct.
```

Document only the flow relevant to the change.

Do not report `frontend tests passed` unless actual frontend tests exist and were run.

Use:

```text
PASS — frontend production build
PASS — relevant manual UI flow
```

when those checks were actually performed.

---

## 8. API verification

When an API contract or endpoint behavior changes, verify three areas:

```text
backend provider
        +
consumer compatibility
        +
documented contract
```

Check:

1. backend behavior;
2. frontend/Telegram/internal consumers as relevant;
3. `docs/API_CONTRACTS.md`.

For STABLE or PROTECTED STABLE endpoints:

- preserve auth semantics unless intentionally changed;
- preserve ownership semantics;
- preserve response field meanings;
- preserve stable status/state behavior;
- update consumers and tests for intentional breaking changes.

---

## 9. Authentication verification

Authentication changes require explicit regression evidence.

Current baseline smoke flow:

```text
without session
GET /api/me
-> 401

valid credentials
POST /api/login
-> success + session cookie

with valid session
GET /api/me
-> authenticated admin

logout
POST /api/logout
-> session no longer valid
```

Because auth-specific automated coverage is not currently comprehensive, an auth behavior change should normally add regression tests when practical.

Do not claim authentication is verified only because unrelated backend tests pass.

---

## 10. Database and Alembic

For a persistent schema change:

```text
SQLAlchemy model change
        +
new Alembic migration
        +
migration review
        +
safe verification
```

Useful read-only checks:

```bash
alembic heads
alembic history
alembic current
```

`alembic current` requires a configured database.

### Migration verification rules

- do not edit an already-applied migration to represent a new schema change;
- review generated/manual migration code;
- check for unintended destructive operations;
- verify upgrade behavior against a safe development/test database when available.

Do not use production Neon as disposable migration test data.

Do not run:

```text
alembic upgrade head
```

against production merely to prove a task is complete.

Production migration execution is a deployment operation.

---

## 11. Legacy database bootstrap check

The project currently retains a deprecated legacy bootstrap path for original financial tables.

If changing:

```text
app/database.py
```

explicitly check that the change:

- does not introduce a new startup-time schema mutation pattern;
- does not conflict with Alembic-managed schema evolution;
- does not silently expand the deprecated bootstrap approach.

New schema evolution should follow DEC-002.

---

## 12. AI chat verification

Current AI chat automated coverage is split by responsibility.

Use the closest tests for the changed module.

Typical mapping:

```text
ai_chat/rate_limit.py
    -> rate-limit tests

ai_chat/tools.py
    -> tool tests
    -> graph tests if workflow interaction changed

ai_chat/gemini.py
    -> Gemini adapter tests
    -> graph/API tests if response behavior changed

ai_chat/graph.py
    -> graph tests
    -> API tests if external behavior changed

ai_chat/schemas.py
    -> API and graph tests as relevant
```

For shared AI-chat changes, run the full related suite or full Python suite.

---

## 13. Live Gemini connectivity

The project contains a live provider smoke script:

```powershell
.\scripts\check-llm.ps1
```

Treat this as an **external-service smoke check**, not a unit test.

Run it when the task involves:

- provider configuration;
- API key/config loading;
- model configuration;
- LLM connectivity;
- provider-runtime behavior.

Do not require a real Gemini call after every AI code change.

Separate the result in reports:

```text
PASS — AI unit tests
NOT RUN — live Gemini connectivity check
```

when a live call was not needed or was unavailable.

Do not expose provider credentials in output.

---

## 14. AI write-action verification

Changes to AI financial write-actions require a stronger safety/state-machine review.

Verify applicable behavior:

```text
draft creation
    -> no financial DB write

clarification
    -> no financial DB write

draft edit
    -> no execution

cancel
    -> no financial DB write

valid confirm
    -> expected financial write

repeated confirm
    -> no duplicate write

expired action
    -> no write

wrong owner
    -> no access / no execution

invalid payload
    -> rejected

successful execution
    -> execution result persisted

audited execution
    -> audit behavior preserved
```

Current implementation note: the JSONL audit append occurs before the surrounding DB transaction commits. If confirm/audit coordination changes, explicitly test rollback/error behavior and do not assume filesystem audit output and PostgreSQL commit are atomically coupled.

If the task changes:

- pending-action state transitions;
- confirm;
- execution;
- ownership;
- draft validation;
- audit behavior;

run the relevant action tests and broaden to the full Python suite when shared behavior is affected.

---

## 15. Google Drive verification

For local Google Drive integration code changes, run:

```bash
python -m unittest tests.test_google_drive
```

A real OAuth flow or real Drive file creation is only required when the task specifically concerns live integration behavior.

Do not create real external files merely to test a local helper that is already covered by unit tests.

Keep live integration side effects minimal and controlled.

---

## 16. Secret scanning

The project includes:

```powershell
.\scripts\scan-secrets.ps1
```

Run it when changes involve:

- `.env.example`;
- auth;
- provider configuration;
- Google OAuth;
- logging;
- Docker/deployment;
- documentation containing configuration examples;
- code that handles secrets/tokens/headers/cookies.

If PowerShell execution policy blocks the script:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\scan-secrets.ps1
```

Do not run secret scans only as ritual after unrelated visual/text changes.

---

## 17. Docker Compose verification

Current local Compose includes:

```text
bot
api
frontend
```

Use only the relevant services.

For web/backend changes:

```powershell
docker compose up --build api frontend
```

Include `bot` when Telegram behavior is affected.

Typical local URLs:

```text
frontend: http://localhost:5173
API:      http://localhost:8000
```

For backend runtime smoke:

```powershell
Invoke-WebRequest http://localhost:8000/health
```

Stop normal development services with:

```powershell
docker compose down
```

Do not use:

```text
docker compose down -v
```

as routine cleanup because persistent volumes may contain receipt/audit data.

---

## 18. Render / production-like verification

When changing:

- `Dockerfile.render`;
- production dependencies;
- frontend production build;
- FastAPI SPA/static serving;
- deployed runtime paths;
- files copied into the Render image;

build the production-like image:

```powershell
docker build --file Dockerfile.render --tag orest-render-check .
```

A successful image build verifies:

- Node dependency installation;
- frontend production build;
- Python dependency installation;
- Docker copy paths;
- final container assembly.

### Runtime smoke

Run only with safe development/test configuration.

Example:

```powershell
docker run --rm --env-file .env -e PORT=10000 -p 10000:10000 orest-render-check
```

Then:

```powershell
Invoke-WebRequest http://localhost:10000/health
```

Because `/health` checks database connectivity, a safe accessible development/test DB is required for a meaningful runtime health smoke.

If a safe DB is not available:

```text
PASS — Render image build
NOT RUN — local Render /health smoke; safe DB unavailable
```

Do not connect to production solely for test convenience.

---

## 19. Health verification

Current health contract:

```text
GET /health
-> 200 {"status":"ok"}
```

includes database readiness.

Run a health smoke when the task changes:

- FastAPI startup;
- database initialization/connectivity;
- application lifespan;
- production runtime;
- deployment image;
- database config.

Do not treat `/health` as a pure process-liveness check.

---

## 20. Test result statuses

Use only explicit statuses in completion reports:

### PASS

The check was actually run and succeeded.

Example:

```text
PASS — python -m unittest tests.test_ai_chat_rate_limit
```

### FAIL

The check was run and failed due to current implementation/task changes or unresolved behavior.

Example:

```text
FAIL — frontend production build
```

### NOT RUN

The check was not executed.

Include the reason when relevant.

Example:

```text
NOT RUN — live Google Drive OAuth flow; not required by this task
```

### PRE-EXISTING FAILURE

Use only when there is credible evidence that the failure existed before the current task.

Example:

```text
PRE-EXISTING FAILURE — unrelated Google Drive integration test
```

Do not label a failure pre-existing merely because it appears unrelated.

---

## 21. Handling failing tests

If a relevant test fails:

1. determine whether it is related to the changed code;
2. inspect the failure;
3. compare with the intended contract;
4. if practical, compare with baseline behavior;
5. classify honestly.

Do not report overall success while a relevant introduced failure remains unresolved.

A pre-existing unrelated failure may be reported without blocking an otherwise valid task, provided the distinction is credible and explicit.

---

## 22. New behavior without automated coverage

If a non-trivial backend behavior has no appropriate automated coverage, adding a regression test should normally be part of the implementation.

High-value areas for regression tests include:

- authentication;
- authorization;
- financial validation;
- API state transitions;
- ownership;
- AI write-actions;
- destructive/write side effects.

Do not create large unrelated test suites as incidental cleanup.

---

## 23. Documentation consistency check

When behavior changes, verify whether any of these must be updated:

```text
AGENTS.md
docs/ARCHITECTURE.md
docs/API_CONTRACTS.md
docs/DECISIONS.md
docs/TESTING.md
docs/DEPLOYMENT.md
.env.example
feature-specific docs
```

A code change that makes current agent-facing documentation false is not fully verified until the inconsistency is resolved or explicitly reported.

---

## 24. Verification matrix

| Changed area | Minimum verification |
|---|---|
| Docs / comments / non-functional text | `git status`, `git diff`, `git diff --check` |
| Config/security docs | Diff checks + secret scan |
| Isolated Python module | Targeted relevant `unittest` |
| Shared backend/domain logic | Full relevant suite or full Python suite |
| Frontend code | `npm run build` + focused manual UI check |
| API behavior | Backend test + consumer check + `docs/API_CONTRACTS.md` review |
| Authentication | Auth regression test or manual login/session/logout smoke |
| Database model/schema | Model + new migration + migration review + safe DB verification |
| `app/database.py` | Backend tests + legacy-bootstrap/Alembic conflict review |
| AI chat | Relevant AI chat tests; broaden if shared workflow changed |
| AI write-action | Safety/state-machine checks + relevant/full Python suite |
| Gemini provider/config | Relevant tests + live `check-llm.ps1` only when justified |
| Google Drive code | `test_google_drive`; live integration only when required |
| Secrets/auth/provider/logging | Secret scan + targeted behavior checks |
| Docker Compose/runtime | Relevant services build/start + smoke |
| `Dockerfile.render` / production image | Render image build + safe runtime smoke where possible |
| Health/lifespan/DB readiness | `/health` with safe DB configuration |

---

## 25. When the full Python suite is required

Run the full Python suite when one or more of these are true:

- shared backend logic changed;
- several backend modules changed;
- database models changed;
- shared Pydantic schemas changed;
- API foundations changed;
- AI workflow foundations changed;
- the affected scope is unclear;
- the task is large/cross-cutting;
- targeted tests cannot credibly cover regression risk.

Command:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

For isolated low-risk changes, targeted verification is acceptable.

---

## 26. Completion evidence

A non-trivial completion report should include only checks that were actually performed.

Example:

```text
Verification:
- PASS: python -m unittest tests.test_ai_action_pending
- PASS: python -m unittest tests.test_ai_action_runtime
- PASS: git diff --check
- NOT RUN: live Gemini smoke; provider behavior unchanged
- NOT RUN: Render runtime smoke; deployment not affected
```

For frontend:

```text
Verification:
- PASS: npm run build
- PASS: manual transaction-edit UI flow
- PASS: git diff --check
```

For deployment:

```text
Verification:
- PASS: docker build -f Dockerfile.render ...
- PASS: /health using safe development DB
- PASS: secret scan
- PASS: git diff --check
```

Never use vague substitutes such as:

```text
looks good
should work
probably passes
```

---

## 27. Final verification rule

Verification is complete when there is enough evidence for the specific change.

The standard is:

```text
relevant checks passed
        +
no known task-introduced regression
        +
final diff reviewed
        +
security/contract impact reviewed where relevant
        +
unverified items explicitly reported
```

The goal is credible evidence, not ritual execution of every possible command.
