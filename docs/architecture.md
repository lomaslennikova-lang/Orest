# Orest — Current Architecture

> This document describes the current structure, component boundaries, runtime modes, and major data flows of Orest.
> It is a factual architecture reference, not a behavioral contract for AI agents.
>
> AI-agent working rules are defined in `AGENTS.md`.
> API behavior is defined in `docs/API_CONTRACTS.md`.
> Architectural rationale is recorded in `docs/DECISIONS.md`.
> Deployment procedures are defined in `docs/DEPLOYMENT.md`.
>

---

## 1. System overview

Orest is a financial application with two main user-facing entry points:

1. a Telegram bot;
2. a web admin interface.

They are separate application runtimes inside the same Python project. They share the same data model/database infrastructure, but the Telegram bot does **not** call the FastAPI HTTP layer for its current financial commands.

```text
Telegram user                         Browser
     │                                  │
     ▼                                  ▼
Telegram Bot API                  React / Vite
     │                                  │ HTTP/API
     ▼                                  ▼
app/main.py                        app/api.py / FastAPI
Telegram runtime                   Web backend runtime
     │                                  │
     │ SQLAlchemy                        ├── Gemini-based AI services
     │                                  ├── private receipt storage / Drive
     └──────────────┬───────────────────┘
                    ▼
             PostgreSQL / Neon
```

Shared Python modules under `app/` provide database models/configuration and other reusable application logic.

The web runtime owns the HTTP API, web authentication/session flow, AI chat/write-action endpoints, and deployed React SPA serving. The Telegram runtime currently performs its Telegram financial commands directly through SQLAlchemy/database sessions.

---

## 2. Repository map

Key repository areas:

```text
Orest/
├─ app/
│  ├─ api.py
│  ├─ main.py
│  ├─ dev.py
│  ├─ database.py
│  ├─ models.py
│  ├─ llm.py
│  ├─ google_drive.py
│  ├─ ai_chat/
│  └─ ai_actions/
│
├─ frontend/
├─ alembic/
├─ tests/
├─ docs/
├─ promts/
├─ scripts/
│
├─ Dockerfile
├─ Dockerfile.render
├─ docker-compose.yml
├─ alembic.ini
├─ requirements.txt
└─ .env.example
```

The repository contains both application code and operational/deployment configuration.

---

## 3. User-facing entry points

### 3.1 Telegram

The Telegram bot runtime is centered on:

```text
app/main.py
```

Development auto-reload support is provided by:

```text
app/dev.py
```

The Telegram interface is a separate entry point from the browser application, but it operates within the same Python project and financial data domain.

---

### 3.2 Web admin interface

The browser interface lives in:

```text
frontend/
```

Current frontend technology:

- React;
- Vite.

The frontend provides the web/admin user interface for financial data and AI functionality.

It communicates with FastAPI over HTTP.

In local development, the frontend runs as a separate Vite development server.

In the Render deployment, the built React application is served by the FastAPI application from the same web service.

---

## 4. FastAPI and the API layer

The main web/backend entry point is:

```text
app/api.py
```

`app/api.py` creates the FastAPI application and contains the HTTP-facing API layer.

Its current responsibilities include:

- health/readiness endpoint;
- admin authentication/session endpoints;
- financial summary and transaction endpoints;
- AI analysis endpoint;
- AI chat endpoints;
- conversation persistence endpoints;
- prompt suggestion endpoints;
- receipt attachment upload/access;
- pending AI action endpoints;
- Google OAuth/Drive integration endpoints;
- serving the built frontend in the deployed web runtime.

Conceptually:

```text
React frontend
      │
      │ HTTP
      ▼
FastAPI routes
      │
      ▼
backend/domain logic
      │
      ├── database
      ├── AI services
      └── private storage
```

The API layer is part of the FastAPI backend; it is not a separate service.

---

## 5. Python application/domain logic

Python application logic is organized primarily under:

```text
app/
```

There are two main Python runtimes:

```text
app/main.py  -> Telegram runtime
app/api.py   -> FastAPI web runtime
```

They share database models/configuration but do not currently communicate with each other through HTTP.

Important areas include:

```text
app/database.py
app/models.py
app/llm.py
app/google_drive.py
app/ai_chat/
app/ai_actions/
```

Across the Python application layer, Orest performs server-side database access and financial writes. The FastAPI web runtime additionally owns:

- web authentication/session handling;
- web/API financial validation;
- ownership checks for web AI resources;
- AI orchestration;
- receipt processing;
- pending-action state handling;
- web transaction execution.

The Telegram runtime has its own command handlers and currently performs Telegram transaction writes directly through shared SQLAlchemy models/database sessions.

Feature-specific logic is increasingly separated into dedicated modules rather than existing only inside `app/api.py`.

---

## 6. Database

Orest uses a persistent PostgreSQL database hosted on Neon.

Current database stack:

- PostgreSQL / Neon;
- SQLAlchemy;
- async database access;
- Alembic migrations.

Primary database-related files:

```text
app/database.py
app/models.py
alembic.ini
alembic/
```

The SQLAlchemy models and Alembic migrations define the detailed persistent schema.

`ARCHITECTURE.md` intentionally documents entity roles and relationships rather than duplicating every database column.

### 6.1 Core financial entities

The core financial model includes:

```text
User
  │
  ├── Category
  │      │
  │      └── Transaction
  │
  ├── AIConversation
  │      └── AIMessage
  │
  ├── AIReceiptAttachment
  │
  └── AIPendingAction
```

Current modeled tables include at least:

- `users`;
- `categories`;
- `transactions`;
- `ai_conversations`;
- `ai_messages`;
- `ai_prompt_suggestions`;
- `ai_receipt_attachments`;
- `ai_pending_actions`.

### 6.2 Financial relationship

A transaction belongs to:

- one user;
- one category.

Categories are user-owned.

This gives the core financial path:

```text
User
  ↓
Category
  ↓
Transaction
```

### 6.3 AI-related persistence

AI chat and write-action features also persist application state in PostgreSQL.

This includes:

- chat conversations;
- chat messages;
- prompt suggestions;
- receipt attachment metadata;
- pending-action state.

---

## 7. AI subsystem

Orest currently has more than one AI flow.

These flows should be understood separately.

### 7.1 Financial analysis

The one-shot analysis flow is conceptually:

```text
PostgreSQL
    │
    ▼
backend selects / aggregates allowed financial data
    │
    ▼
Gemini-based analysis
    │
    ▼
structured backend response
    │
    ▼
web frontend
```

The AI provider receives data prepared by the backend rather than direct database access.

---

### 7.2 AI chat

The AI chat subsystem lives primarily in:

```text
app/ai_chat/
```

Current modules include:

```text
gemini.py
graph.py
prompts.py
rate_limit.py
repository.py
schemas.py
tools.py
```

The chat flow combines:

- persisted conversations/messages;
- Gemini generation;
- backend-controlled financial tools;
- rate limiting;
- LangGraph workflow state;
- PostgreSQL-backed LangGraph checkpoints.

Conceptually:

```text
User message
    │
    ▼
POST /api/ai/chat
    │
    ▼
conversation/history
    │
    ▼
LangGraph
    │
    ├── Gemini
    │
    └── backend financial tools
    │
    ▼
assistant response
    │
    ▼
persisted chat state
```

The LangGraph workflow is bounded and can alternate between:

```text
Gemini
  ↓
tool call
  ↓
backend financial tool
  ↓
Gemini
```

before producing the final response.

LangGraph checkpoint state is persisted through PostgreSQL.

---

### 7.3 AI write-actions

AI write-action logic lives primarily in:

```text
app/ai_actions/
```

Current modules include:

```text
audit.py
pending.py
prompts.py
receipt_llm.py
receipts.py
runtime.py
schemas.py
transactions.py
```

The current financial write-action flow is based on a server-owned pending action.

```text
User input / receipt
        │
        ▼
receipt validation / extraction
        │
        ▼
LLM structured draft
        │
        ▼
backend validation
        │
        ▼
AIPendingAction
        │
        ▼
explicit confirm
        │
        ▼
backend transaction logic
        │
        ▼
PostgreSQL
        │
        ▼
saved execution result / audit
```

`AIPendingAction` stores the server-side state of a proposed action.

Current pending-action statuses include states such as:

```text
needs_clarification
pending_confirmation
confirmed
executed
cancelled
expired
failed
```

A repeated confirm returns the saved result rather than representing a separate new action execution.

---

## 8. Receipt and private-storage subsystem

Receipt attachments are represented by application metadata in PostgreSQL and stored outside the public web root.

Conceptually:

```text
Receipt upload
     │
     ▼
FastAPI upload endpoint
     │
     ▼
file validation
     │
     ▼
private storage
     │
     ├── local runtime storage
     └── Google Drive integration when configured
     │
     ▼
attachment metadata in PostgreSQL
```

The project contains:

```text
app/google_drive.py
```

and receipt-storage routing under the AI action subsystem.

The API uses opaque application identifiers and authenticated endpoints to access receipt-related resources.

---

## 9. Authentication and session flow

The web admin uses server-side credential validation and a signed session cookie.

Conceptually:

```text
Browser
   │
   ▼
POST /api/login
   │
   ▼
FastAPI validates admin credentials
   │
   ▼
signed admin session cookie
   │
   ▼
protected /api/* endpoints
```

Protected AI and financial routes depend on the authenticated admin session.

Ownership-sensitive AI resources are associated with an application user and checked server-side.

---

## 10. Health and application lifespan

FastAPI defines:

```text
GET /health
```

The health flow includes a database connectivity check.

Conceptually:

```text
GET /health
    │
    ▼
FastAPI
    │
    ▼
database connection check
    │
    ▼
{"status":"ok"}
```

During FastAPI application lifespan startup, the current application also initializes database/AI runtime resources, including the AI chat graph and its PostgreSQL checkpoint infrastructure.

---

## 11. Runtime modes

Orest currently supports three practical runtime arrangements.

### 11.1 Local individual processes

Components may be started separately.

Telegram bot:

```text
python app/main.py
```

or development reload:

```text
python -m app.dev
```

FastAPI:

```text
uvicorn app.api:app --reload
```

Frontend:

```text
cd frontend
npm run dev
```

Conceptually:

```text
Telegram runtime   Python process

Browser
  │
  ▼
Vite :5173
  │
  ▼
FastAPI :8000
  │
  ▼
Neon PostgreSQL
```

---

### 11.2 Docker Compose

`docker-compose.yml` defines the local multi-service development setup.

The current development arrangement includes separate services for:

```text
bot
api
frontend
```

This preserves the separate-process development model inside containers.

Conceptually:

```text
docker compose
├── bot
├── api
└── frontend
```

---

### 11.3 Render web deployment

Production-style web deployment uses:

```text
Dockerfile.render
```

The image is multi-stage:

```text
Node 22 build stage
        │
        ├── npm ci
        └── npm run build
        │
        ▼
frontend/dist
        │
        ▼
Python 3.12 application stage
        │
        ├── backend dependencies
        ├── app/
        ├── promts/
        ├── alembic/
        └── frontend/dist
        │
        ▼
uvicorn app.api:app
```

The deployed web architecture is therefore:

```text
Browser
   │
 HTTPS
   ▼
one Render Web Service
   │
   ▼
FastAPI
├── /health
├── /api/*
├── React SPA
└── frontend assets
```

This differs from local development, where Vite and FastAPI normally run as separate processes.

---

## 12. Major data flows

### 12.1 Dashboard read

```text
PostgreSQL
    │
    ▼
backend query
    │
    ▼
FastAPI finance endpoint
    │
    ▼
React dashboard
```

---

### 12.2 Manual transaction creation

```text
React form
    │
    ▼
FastAPI transaction endpoint
    │
    ▼
server-side validation
    │
    ▼
transaction logic
    │
    ▼
PostgreSQL
```

---

### 12.3 AI financial analysis

```text
PostgreSQL
    │
    ▼
backend-selected financial data
    │
    ▼
Gemini
    │
    ▼
structured analysis
    │
    ▼
FastAPI
    │
    ▼
React
```

---

### 12.4 AI chat

```text
React
  │
  ▼
/api/ai/chat
  │
  ▼
conversation + LangGraph
  │
  ├── Gemini
  └── backend financial tools
  │
  ▼
persisted message
  │
  ▼
React
```

---

### 12.5 Receipt-driven AI write

```text
Receipt
   │
   ▼
upload API
   │
   ▼
private storage + attachment metadata
   │
   ▼
AI extraction
   │
   ▼
server-side draft validation
   │
   ▼
pending action
   │
   ▼
explicit confirm
   │
   ▼
transaction logic
   │
   ▼
PostgreSQL
```

---

## 13. Document boundaries

This document describes **what exists and how the pieces connect**.

Related documents have different responsibilities:

### `AGENTS.md`

How an AI agent is expected to work with the repository.

### `docs/API_CONTRACTS.md`

Stable HTTP/API behavior and endpoint contracts.

### `docs/DECISIONS.md`

Why important architectural/product decisions were made.

### `docs/TESTING.md`

How changes are verified.

### `docs/DEPLOYMENT.md`

How the application is built, configured, and deployed.

### SQLAlchemy models + Alembic migrations

Detailed persistent database schema.

---

## 14. Historical documentation

Some earlier documents in `docs/` were created during earlier learning stages of the project.

In particular:

```text
docs/architecture.md
docs/database.md
```

may describe older states of the application.

The current architecture reference is this file together with the current code, models, migrations, and tests.
