# Orest — Deployment Model and Rules

> This document defines the stable deployment model, deployment-sensitive boundaries, and verification expectations for Orest.
>
> It is an agent-facing deployment reference.
>
> Detailed human operational steps — Render UI actions, current URLs, DNS records, OAuth bootstrap steps, and troubleshooting — belong in `docs/deploy.md`.
>
> Architecture rationale is recorded in `docs/DECISIONS.md`.
> Verification details are defined in `docs/TESTING.md`.
>

---

## 1. Purpose

This document answers:

```text
How is Orest deployed?
Which files/settings affect deployment?
Which changes require deployment awareness?
What must be verified or reported after such changes?
```

It intentionally does not duplicate:

- the full Render setup runbook;
- exact DNS values;
- current branch names;
- current provider/model selections;
- secret values;
- temporary operational instructions.

Those details may change more frequently than the deployment architecture itself.

---

## 2. Current deployed environment

The current public deployment is a learning/demo environment hosted on Render Free tier.

Treat it as:

```text
public deployed environment
production-like runtime
free/demo infrastructure
```

Do not assume production-grade:

- uptime;
- storage durability;
- performance;
- SLA;
- backup guarantees.

The current deployment model uses one Render Web Service.

---

## 3. Deployment topology

Current deployed flow:

```text
Git repository
      │
      ▼
Render build
      │
      ▼
Dockerfile.render
      │
      ▼
single web-service image
      │
      ▼
FastAPI / Uvicorn
├── /health
├── /api/*
├── React SPA
└── frontend assets
      │
      ├── Neon PostgreSQL
      ├── Gemini
      └── Google Drive when configured
```

The deployed browser application and FastAPI backend use the same public origin.

Local development may use a different topology.

---

## 4. Runtime artifacts

Orest contains three different container/runtime artifacts.

They are not interchangeable.

### `Dockerfile`

Primary role:

```text
local/base Python runtime
```

It is not automatically equivalent to the deployed Render web image.

### `docker-compose.yml`

Primary role:

```text
local development topology
```

Current local Compose services include:

```text
bot
api
frontend
```

The frontend normally runs through Vite separately from FastAPI.

### `Dockerfile.render`

Primary role:

```text
deployed web image
```

It builds the React frontend and packages it into the FastAPI image.

Conceptually:

```text
Node build stage
    │
    ├── npm ci
    └── npm run build
    │
    ▼
frontend/dist
    │
    ▼
Python runtime stage
    │
    ├── Python dependencies
    ├── app/
    ├── promts/
    ├── Alembic files
    └── frontend/dist
    │
    ▼
uvicorn app.api:app
```

Render supplies the runtime port through `$PORT`.

---

## 5. Deployment-sensitive files

Changes to the following areas may affect the deployed environment:

```text
Dockerfile.render
requirements.txt
frontend/package.json
frontend/package-lock.json
app/api.py
promts/
alembic/
alembic.ini
.env.example
```

Other files can also be deployment-sensitive if they affect:

- startup/import paths;
- runtime configuration;
- static/SPA serving;
- database initialization;
- AI provider setup;
- storage integration.

Do not assume a change is deployment-neutral only because `Dockerfile.render` itself was not edited.

---

## 6. Configuration model

### `.env.example`

`.env.example` is the repository-level configuration-variable registry.

It contains:

- variable names;
- safe placeholders;
- local/example defaults.

It does not contain real secrets.

### Local environment

Local development may use:

```text
.env
```

with real local credentials/configuration.

### Render environment

The deployed service uses Render Environment Variables / secrets for real runtime values.

The repository is not the storage location for deployed secrets.

---

## 7. Important runtime configuration semantics

### Database

`DATABASE_URL` is required by the deployed backend and AI persistence flows.

Database configuration is server-side only.

### Secure admin cookie

Local HTTP development may use:

```text
ADMIN_SESSION_COOKIE_SECURE=false
```

The deployed HTTPS environment uses:

```text
ADMIN_SESSION_COOKIE_SECURE=true
```

Do not weaken secure-cookie behavior for the public HTTPS deployment as incidental cleanup.

### Render port

Render provides:

```text
PORT
```

at runtime.

Do not require users to manually create a permanent `PORT=...` application secret unless the hosting model changes.

### Frontend API origin

Local frontend development may use explicit frontend API configuration.

The deployed React SPA uses the same origin as FastAPI.

Do not introduce an unnecessary production cross-origin API dependency without an explicit deployment decision.

---

## 8. External service dependencies

The deployed web service depends on external systems.

```text
Render Web Service
    │
    ├── Neon PostgreSQL
    │     ├── financial data
    │     ├── application users/categories
    │     ├── AI conversations/messages
    │     ├── pending-action metadata
    │     └── LangGraph/checkpoint persistence
    │
    ├── Gemini
    │     ├── financial analysis
    │     ├── AI chat
    │     └── receipt interpretation
    │
    └── Google Drive (when configured)
          └── private receipt file storage
```

A failure in one dependency does not necessarily mean the whole deployment image is invalid.

Diagnose by subsystem.

---

## 9. Dependency-aware diagnostics

Use the dependency boundary to interpret failures.

### `/health` fails

Inspect:

- application startup;
- `DATABASE_URL`;
- database connectivity;
- Neon/TLS/runtime configuration.

### `/health` succeeds but AI fails

Inspect:

- Gemini configuration;
- provider availability/quota;
- AI runtime/checkpointer;
- provider-specific errors.

### Web/AI works but receipt storage fails

Inspect:

- Google Drive configuration;
- OAuth state;
- folder/storage permissions;
- receipt-storage backend configuration.

Do not expose credentials while diagnosing these paths.

Report configuration presence/status rather than printing secret values.

---

## 10. Storage durability

### Local deployed filesystem

The current Render Free environment does not provide durable local filesystem guarantees.

Runtime locations such as:

```text
/tmp/orest/receipts
/tmp/orest/audit
```

must be treated as temporary/runtime storage.

Do not design long-term durable storage around the deployed local filesystem.

This also applies to the current local JSONL AI audit files: they provide an application audit record, but the Free Render local filesystem does not guarantee long-term audit retention. In addition, the current JSONL append and PostgreSQL commit are separate resources rather than one atomic transaction. Do not describe the current demo deployment as having durable/compliance-grade or cross-resource-atomic audit storage unless an appropriate mechanism is added.

### Receipt files

When Google Drive integration is configured, the preferred durable receipt model is:

```text
receipt file bytes
    -> private Google Drive

application metadata
    -> PostgreSQL / Neon
```

Receipt files remain private application resources.

### Database metadata

PostgreSQL remains the authority for application metadata such as:

- ownership;
- lifecycle/status;
- attachment identifiers;
- Drive identifiers;
- pending-action state.

---

## 11. Database migrations

Application deployment/restart is intentionally separate from persistent schema migration.

Use this model:

```text
code deploy / restart
        ≠
automatic schema migration
```

Do not add automatic:

```text
alembic upgrade head
```

to normal application startup or Render container command as incidental cleanup.

New schema changes are implemented through Alembic migrations.

Execution against the deployed database is a separate controlled deployment action.

---

## 12. Migration-related deployment impact

When a task introduces a schema change, the completion report must explicitly state:

```text
Database migration required: yes
Migration file created: yes/no
Migration tested safely: yes/no
Deployed DB migration executed: yes/no
Manual action required: ...
```

Do not execute a deployed-database migration merely to make a coding task appear complete unless deployment execution is explicitly part of the task.

---

## 13. Health and readiness

Current deployed health contract:

```text
GET /health
```

A successful response means:

```text
FastAPI is responding
+
database connectivity check succeeds
```

This is application readiness, not pure process liveness.

A failed `/health` after deployment may therefore indicate either:

- application/runtime failure;
- database configuration/connectivity failure.

---

## 14. Deployment verification

Detailed commands are defined in `docs/TESTING.md`.

For deployment-sensitive changes, verification should normally include the relevant subset of:

```text
frontend production build
Python/backend tests
secret scan
Dockerfile.render image build
safe runtime smoke
/health check
post-deploy smoke
```

Do not connect to production data merely for test convenience.

---

## 15. Production-like image verification

For changes affecting the deployed image, build:

```powershell
docker build --file Dockerfile.render --tag orest-render-check .
```

This validates important deployment assumptions such as:

- Node dependency installation;
- frontend build;
- Python dependency installation;
- copied file paths;
- final image assembly.

A runtime `/health` smoke requires safe usable database configuration.

If unavailable, report:

```text
PASS — Render image build
NOT RUN — local /health smoke; safe DB unavailable
```

Do not misrepresent image-build success as full runtime verification.

---

## 16. Post-deploy smoke checks

After a deployed web change, the stable smoke semantics are:

```text
GET /health
    -> 200 {"status":"ok"}

GET /openapi.json
    -> 200

GET /api/me without valid session
    -> 401

GET /
    -> React SPA
```

Additional smoke checks should match the changed feature.

Examples:

```text
login flow
transaction read/write
AI chat
receipt upload
Google Drive integration
```

Do not run unrelated destructive or paid external flows merely for completeness.

---

## 17. Public origin and OAuth coupling

Changing the public domain/origin can affect:

- DNS;
- TLS;
- session-cookie assumptions;
- frontend/backend origin behavior;
- OAuth redirect URIs;
- Google OAuth configuration.

A domain change is not merely a text/config replacement.

It is a deployment-impacting change.

Specific current domain names, DNS targets, and provider UI instructions belong in `docs/deploy.md`, not in this stable deployment model.

---

## 18. Source branch

The currently deployed Git branch is an operational Render setting.

It is not a permanent architectural invariant.

Before deployment-sensitive work, verify the actual configured source branch rather than assuming an older runbook value is still current.

Specific branch instructions belong in `docs/deploy.md`.

---

## 19. Provider/model configuration

Specific Gemini model names and provider settings are runtime configuration, not deployment architecture.

The stable rule is:

```text
model/provider configuration
    -> environment/config
```

Do not hard-code current provider/model selections into the deployment architecture unless the project explicitly adopts them as a durable decision.

---

## 20. Free/demo environment implications

The current deployed environment is not assumed to provide:

- durable local disk;
- production SLA;
- guaranteed availability;
- guaranteed no-cold-start behavior.

Architecturally relevant consequences:

- critical persistent data belongs outside ephemeral local disk;
- deployment restarts must be tolerated;
- stateful application data belongs in persistent external services;
- public availability should not be treated as guaranteed production uptime.

Avoid embedding exact hosting-plan numeric limits into this file because provider policies can change.

---

## 21. Deployment-impact classification

### Low deployment impact

Examples:

- ordinary Python code already included in the image;
- ordinary React component changes;
- prompt content already copied into the image.

Typical effect:

```text
redeploy required
deployment model unchanged
```

### Consequential deployment impact

Examples:

- new environment variable;
- new Python/Node dependency;
- new copied directory/path;
- schema migration;
- OAuth configuration change;
- storage integration change.

The agent may implement these when required by the task, but must disclose them clearly.

### Protected deployment change

Examples:

- split frontend/backend into separate deployed origins;
- change auth/cookie topology;
- automatic deployed DB migrations;
- make private receipt storage public;
- destructive deployed DB operation;
- public-domain/origin redesign.

These require explicit project-level decision/approval.

---

## 22. Deployment completion report

For any deployment-sensitive task, report:

```text
Deployment impact:
- Deployed image changed: yes/no
- New env variables: yes/no
- Database migration required: yes/no
- Public origin/domain impact: yes/no
- OAuth/callback impact: yes/no
- Storage behavior impact: yes/no
- Manual Render action required: yes/no
- Redeploy required: yes/no
```

If manual action is required, state it explicitly.

Example:

```text
Manual action required:
- add NEW_VARIABLE to Render Environment;
- run Alembic migration;
- redeploy the service.
```

Do not leave required operational steps implicit.

---

## 23. Secrets and deployment logs

Deployment diagnostics must not print real:

- database URLs;
- admin passwords;
- session secrets;
- API keys;
- OAuth secrets;
- refresh tokens;
- cookies;
- private financial payloads.

Prefer:

```text
DATABASE_URL configured: yes
LLM_API_KEY configured: yes
GOOGLE_CLIENT_SECRET configured: no
```

rather than printing values.

Use the repository secret scanner when relevant.

---

## 24. Relationship to the human runbook

`docs/DEPLOYMENT.md` is the stable deployment model.

`docs/deploy.md` is the operational human runbook.

The human runbook may contain current details such as:

- Render UI fields;
- current source branch;
- current public URL;
- DNS records;
- current domain;
- OAuth bootstrap sequence;
- current provider/model values;
- troubleshooting commands.

Those details may change more frequently and should not automatically be treated as architectural invariants.

Recommended header for `docs/deploy.md`:

```markdown
> Operational deployment runbook.
> For the stable deployment architecture and agent-facing deployment rules,
> see `docs/DEPLOYMENT.md`.
```

---

## 25. Document boundary

This document answers:

```text
How is Orest deployed, and what deployment impact must be understood?
```

Related documents answer different questions:

- `AGENTS.md` — how AI agents work;
- `docs/ARCHITECTURE.md` — how the system is structured;
- `docs/API_CONTRACTS.md` — what API clients can rely on;
- `docs/DECISIONS.md` — why major deployment/architecture choices were made;
- `docs/TESTING.md` — how deployment-sensitive changes are verified;
- `docs/deploy.md` — current human operational steps.
