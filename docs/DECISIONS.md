# Orest — Decision Log

> This document records durable architectural, product, security, and operational decisions for Orest.
>
> A decision belongs here only when multiple reasonable implementations were possible and Orest deliberately chose one.
>
> This is not a description of the current codebase (`docs/ARCHITECTURE.md`), not an API reference (`docs/API_CONTRACTS.md`), and not an AI-agent working policy (`AGENTS.md`).
>
> When a decision changes, do not rewrite history. Mark the old decision as `Superseded` and add a new decision.
>

---

## Decision status values

- **Active** — current decision.
- **Proposed** — under consideration but not yet adopted.
- **Superseded** — replaced by a newer decision.
- **Deprecated** — still exists technically, but should not be used as the pattern for new work.

Some decisions are additionally marked **Protected** when changing them materially alters security, financial side effects, or trust boundaries.

---

# DEC-001 — Persistent data access goes through the backend

**Status:** Active

## Context

The web frontend could theoretically connect directly to a cloud database or database-facing API.

Orest instead uses a Python/FastAPI backend as the server-side boundary for persistent financial data.

## Decision

Persistent financial data access is performed through backend-controlled application logic.

The React frontend does not act as the authority for direct PostgreSQL/Neon access.

## Rationale

Keeping persistent access on the server side keeps sensitive concerns out of the browser, including:

- authentication/authorization;
- ownership checks;
- financial validation;
- write semantics;
- audit/security controls.

The current Telegram and FastAPI runtimes are not yet fully unified behind one transaction service, so this decision defines the trust boundary rather than claiming that all server-side validation code is already centralized.

## Consequences

- frontend code remains a client of backend APIs;
- financial writes are validated server-side;
- database credentials remain server-side;
- future data-access features should normally extend backend services/API rather than bypass them.

## Change impact

Changing this decision would materially alter the system trust boundary and would require review of authentication, authorization, validation, security, and deployment.

## Related

- `AGENTS.md`
- `docs/ARCHITECTURE.md`
- `docs/API_CONTRACTS.md`

---

# DEC-002 — New persistent schema evolution uses Alembic

**Status:** Active

## Context

Orest began before all database evolution was managed through versioned migrations.

The original financial tables have legacy bootstrap behavior, while newer application/AI tables are already managed through Alembic migrations.

## Decision

All **new** persistent schema changes use Alembic migrations.

Legacy bootstrap code for original financial tables is not the pattern for future schema evolution.

## Rationale

Versioned migrations provide:

- explicit schema history;
- reviewable database changes;
- repeatable local/deployment behavior;
- safer coordination between code and persistent data.

## Consequences

When a new persistent field/table/index/constraint is introduced:

- the SQLAlchemy model may change;
- a new Alembic migration is created;
- the migration is reviewed and verified.

New schema changes should not be implemented by adding ad-hoc startup SQL.

## Change impact

Moving away from versioned migrations would reduce schema traceability and complicate deployment/recovery.

## Related

- `app/models.py`
- `alembic/`
- `docs/TESTING.md`
- `docs/DEPLOYMENT.md`

---

# DEC-002A — Legacy bootstrap for original financial tables is temporary

**Status:** Deprecated

## Context

The original `users`, `categories`, and `transactions` database path predates the project's full migration-based schema management.

Legacy startup/bootstrap logic remains for backward compatibility with that earlier stage.

## Decision

The legacy bootstrap path may remain temporarily, but it is not used as a design pattern for new schema work.

## Rationale

Removing or rewriting legacy bootstrap behavior can affect existing development/deployment databases and therefore should be handled as a dedicated migration/cleanup task rather than incidental refactoring.

## Consequences

- new tables/columns use Alembic;
- new startup-time `ALTER TABLE` patterns should not be added;
- eventual removal of the legacy path should be handled as an explicit project task.

## Change impact

Retiring this deprecated path requires validating existing databases and deployment assumptions.

## Related

- `app/database.py`
- DEC-002

---

# DEC-003 — LLM capabilities follow least privilege

**Status:** Active / Protected

## Context

An LLM can be integrated either through broad infrastructure access or through narrow application-controlled capabilities.

Broad access would make model output capable of directly affecting sensitive infrastructure or data.

## Decision

LLM capabilities are exposed through narrow backend-controlled interfaces.

The LLM does not receive generic infrastructure authority such as:

- `DATABASE_URL`;
- database credentials;
- SQLAlchemy sessions;
- arbitrary SQL execution;
- unrestricted filesystem access;
- generic unrestricted write tools;
- session cookies;
- OAuth tokens.

## Rationale

LLM output is treated as untrusted input.

The backend defines:

- which data may be exposed;
- which actions are available;
- what validation is required;
- whether a side effect is allowed.

## Consequences

Prefer:

```text
specific financial read tool
specific structured draft tool
```

over:

```text
execute_sql(...)
write_database(...)
generic_shell(...)
```

AI capability expansion should normally add narrow tools rather than broad execution access.

## Change impact

Changing this decision would materially expand the AI trust boundary and require dedicated security review.

## Related

- `AGENTS.md`
- `docs/ARCHITECTURE.md`
- `docs/API_CONTRACTS.md`
- `docs/ai/`

---

# DEC-004 — AI-initiated financial writes require explicit confirmation

**Status:** Active / Protected

## Context

The AI assistant can analyze financial data and propose changes.

Automatic execution of model-generated financial actions would introduce a higher-risk autonomous side effect.

## Decision

An AI-initiated financial write is executed only after explicit user confirmation.

The intended flow is:

```text
input / receipt
    ↓
AI structured draft
    ↓
server-side validation
    ↓
pending action
    ↓
explicit user confirm
    ↓
backend financial write
```

## Rationale

This keeps the user in the loop before a real financial mutation occurs.

It separates:

- AI interpretation/proposal;
- server validation;
- user approval;
- execution.

## Consequences

- ordinary AI chat does not silently create transactions;
- clarification is preferred over guessing;
- pending actions are server-owned state;
- confirmation is a distinct operation.

## Change impact

Allowing autonomous AI financial writes would be a high-impact behavioral change and requires a new explicit decision.

## Related

- `docs/API_CONTRACTS.md`
- DEC-003
- DEC-005
- DEC-014

---

# DEC-005 — Financial action confirmation is repeat-safe

**Status:** Active / Protected

## Context

HTTP requests may be retried because of:

- double click;
- client retry;
- network uncertainty;
- repeated user action.

A repeated confirmation must not create duplicate financial records.

## Decision

Confirming an already successfully executed AI pending action returns the saved execution result instead of executing the financial write again.

## Rationale

Financial side effects require stronger guarantees than ordinary read requests.

Repeat-safe confirmation prevents accidental duplicate transactions.

## Consequences

- executed action state is persisted;
- created transaction IDs are retained;
- confirm behavior is idempotent/repeat-safe at the application level;
- tests must cover repeated confirmation.

## Change impact

Removing this guarantee could create duplicate financial transactions and is therefore a protected behavioral change.

## Related

- `docs/API_CONTRACTS.md`
- `docs/TESTING.md`
- DEC-004

---

# DEC-006 — Receipt-to-transaction v1 has deliberately narrow financial scope

**Status:** Active

## Context

Receipt interpretation can quickly expand into:

- multiple currencies;
- exchange-rate selection;
- income detection;
- discount allocation;
- ambiguous totals;
- aggregation decisions;
- item/category inference.

Attempting to automate all cases at once would increase uncertainty and hidden assumptions.

## Decision

The current receipt-to-transaction action intentionally uses a narrow scope:

- creates `expense` financial actions;
- uses UAH as the supported financial currency;
- does not automatically perform currency conversion;
- requests clarification when required financial data is ambiguous;
- keeps multiple receipt lines as separate rows/transactions rather than silently aggregating them.

## Rationale

A narrow v1 improves predictability and makes financial side effects easier to review and validate.

## Consequences

Unsupported or ambiguous cases are not silently guessed.

Future support for income, FX conversion, automatic aggregation, or other advanced receipt behavior should be introduced as explicit feature decisions.

## Change impact

Expanding this scope changes product behavior and must update the action model, validation, tests, and user-facing confirmation semantics.

## Related

- `app/ai_actions/`
- `docs/API_CONTRACTS.md`
- DEC-004

---

# DEC-007 — Authentication and authorization are enforced server-side

**Status:** Active

## Context

The frontend can hide controls or routes, but UI visibility is not a security boundary.

## Decision

Authentication, authorization, and ownership checks are enforced by the backend.

Frontend behavior may improve UX but is not authoritative for access control.

## Rationale

Client-side state can be modified or bypassed.

Security-sensitive decisions must be evaluated by trusted server-side code.

## Consequences

- protected API routes validate the admin session;
- ownership-sensitive resources are checked server-side;
- future authentication mechanisms may change while preserving this trust boundary.

## Change impact

Moving authorization authority to the client would weaken the security model and require a new architectural decision.

## Related

- `AGENTS.md`
- `docs/API_CONTRACTS.md`
- `docs/ARCHITECTURE.md`

---

# DEC-008 — Render uses one same-origin web service built from Dockerfile.render

**Status:** Active

## Context

The web frontend and backend could be deployed as separate services/domains or as one web service.

## Decision

The current Render deployment uses one Web Service built with:

```text
Dockerfile.render
```

The built React SPA and FastAPI application are served from the same deployed service/origin.

## Rationale

The single-service model simplifies:

- deployment;
- same-origin API calls;
- session-cookie behavior;
- production CORS requirements;
- operational setup for the current project scale.

## Consequences

The deployed FastAPI service serves:

```text
/health
/api/*
React SPA
frontend assets
```

Local development may still run Vite and FastAPI separately.

## Change impact

Splitting frontend/backend across production domains would require review of:

- CORS;
- cookie/session settings;
- public URLs;
- OAuth redirects;
- deployment topology.

## Related

- `Dockerfile.render`
- `docs/ARCHITECTURE.md`
- `docs/DEPLOYMENT.md`

---

# DEC-009 — Production schema migrations are not coupled to application startup

**Status:** Active

## Context

Database migrations can either run automatically on every application startup/redeploy or be executed as a controlled deployment step.

## Decision

Application startup does not automatically run production `alembic upgrade head`.

Production schema migration is treated as a separate controlled operation.

## Rationale

Restarting or redeploying application code should not automatically imply a persistent schema mutation.

Database changes have a different risk profile from process startup.

## Consequences

- migration files are committed with code;
- migrations are reviewed/tested separately;
- production migration execution is an explicit deployment action;
- ordinary application restart remains non-migrating.

## Change impact

Automatic startup migration would alter deployment risk and must be introduced deliberately.

## Related

- `docs/DEPLOYMENT.md`
- `docs/TESTING.md`
- DEC-002

---

# DEC-010 — Runtime secrets are external to repository state

**Status:** Active

## Context

The application requires credentials for database, admin session, AI provider, Telegram, OAuth, and other integrations.

## Decision

Real runtime secrets are supplied through environment configuration such as:

- local `.env`;
- Render Environment Variables / secrets.

The repository contains templates/placeholders only.

## Rationale

Credentials should not become part of:

- Git history;
- application source code;
- documentation;
- build artifacts intended for distribution.

## Consequences

- `.env.example` documents configuration names without real values;
- secret changes do not require source-code changes;
- deployment configuration remains external to repository history.

## Change impact

Embedding secrets in source/repository state would violate the project's security model.

## Related

- `AGENTS.md`
- `.env.example`
- `docs/DEPLOYMENT.md`

---

# DEC-011 — Receipt attachments are private application resources

**Status:** Active / Protected

## Context

Receipt files contain user financial information and could be exposed either as public static assets or through authenticated application access.

## Decision

Receipt attachments are private resources.

They are not exposed as public web assets or public sharing URLs.

## Rationale

Receipts may contain sensitive financial and personal information.

Access must remain within the application's authenticated ownership model.

## Consequences

The application uses:

- opaque attachment/action identifiers;
- authenticated retrieval endpoints;
- private storage;
- server-side ownership checks.

Public Drive sharing or public static receipt URLs are outside the current privacy model.

## Change impact

Making receipts public would materially change privacy/security behavior and requires a new explicit decision.

## Related

- `docs/API_CONTRACTS.md`
- `docs/ARCHITECTURE.md`
- DEC-012

---

# DEC-012 — Receipt file storage may use private Google Drive while metadata remains in PostgreSQL

**Status:** Active

## Context

Receipt file bytes and receipt metadata have different storage needs.

The project also needs storage that is not tied exclusively to an ephemeral web-service filesystem.

## Decision

When Google Drive storage is configured:

- receipt file content may be stored in a private Google Drive folder;
- PostgreSQL retains application metadata, ownership, lifecycle data, and Drive identifiers.

## Rationale

This separates:

- binary/private file storage;
- relational application state.

It also avoids relying solely on ephemeral local storage in the deployed web service.

## Consequences

The application database remains the authority for attachment metadata and ownership.

The storage provider is replaceable without changing the fundamental private-resource decision in DEC-011.

## Change impact

Changing the storage provider is an implementation/operational decision unless privacy or ownership semantics also change.

## Related

- `app/google_drive.py`
- `docs/DEPLOYMENT.md`
- DEC-011

---

# DEC-013 — Health means application readiness including database connectivity

**Status:** Active

## Context

A health endpoint can represent:

- process liveness only; or
- broader application readiness.

## Decision

Orest `/health` currently includes a database connectivity check.

A successful health response represents FastAPI readiness with working database connectivity.

## Rationale

The application depends on persistent database access for core behavior.

A process that cannot access the database is not considered fully ready.

## Consequences

Monitoring/deployment checks may treat a database outage as an unhealthy application.

## Change impact

Separating liveness from readiness may be a valid future improvement, but changing current `/health` semantics requires API/deployment updates.

## Related

- `docs/API_CONTRACTS.md`
- `docs/DEPLOYMENT.md`

---

# DEC-014 — Executed AI financial actions have a separate audit trail

**Status:** Active / Protected

## Context

AI chat history records conversation, but conversation history alone is not sufficient evidence of the exact financial action that was executed.

## Decision

Executed AI-initiated financial actions maintain an application-controlled audit record separate from conversational text.

## Rationale

An execution audit must capture the actual action/state used for the financial write rather than relying on natural-language chat interpretation.

## Consequences

Audit information can include:

- action identifier;
- execution timestamp;
- validated payload;
- created transaction identifiers;
- attachment/hash linkage where relevant.

The audit layer is part of the financial-write safety model.

Current implementation limitations:

- the JSONL audit record is appended during the confirm flow before the surrounding database transaction commits, so filesystem audit output and PostgreSQL commit are not one atomic transaction; a rare later database-commit failure could leave an audit record without a committed financial write;
- the current Free Render local filesystem is ephemeral, so the existence of an application audit record must not be confused with guaranteed long-term or compliance-grade audit retention.

Atomic cross-resource audit consistency and durable external audit backup/storage require separate implementation/operational decisions.

## Change impact

Removing execution auditability would weaken traceability of AI financial side effects and requires a new explicit decision.

## Related

- `app/ai_actions/audit.py`
- `docs/ai/`
- DEC-004
- DEC-005

---

# DEC-015 — AI conversation/workflow state is persistent application data

**Status:** Active

## Context

The AI assistant could be implemented as a stateless request wrapper or as an application feature with persistent conversation/workflow state.

## Decision

AI conversation and workflow state is persisted as part of the application.

This includes:

- AI conversations;
- AI messages;
- relevant pending-action state;
- LangGraph checkpoint persistence.

## Rationale

The assistant is intended to support continued dialogue and stateful application workflows rather than isolated one-shot prompts only.

## Consequences

- conversation continuity survives ordinary page/request boundaries;
- state ownership must be enforced;
- database availability is part of AI chat runtime behavior;
- deleting persistence would materially change the assistant experience.

## Change impact

Moving to fully stateless chat would be a product/architecture change and should be introduced as a new decision.

## Related

- `app/ai_chat/`
- `app/models.py`
- `docs/ARCHITECTURE.md`
- `docs/API_CONTRACTS.md`

---

# Decision creation template

Use this structure for future decisions:

```markdown
# DEC-XXX — Title

**Status:** Proposed | Active | Superseded | Deprecated

## Context

What problem, constraint, or meaningful choice existed?

## Decision

What did Orest deliberately choose?

## Rationale

Why was this option chosen over reasonable alternatives?

## Consequences

What follows from the decision?

## Change impact

What would need review if this decision changed?

## Related

- files
- APIs
- other decisions
```

If replacing an older decision:

```markdown
**Status:** Superseded by DEC-XXX
```

and create the new decision instead of rewriting the historical one.

---

# What does not belong in this file

Do not add an entry only because something exists in code.

Examples that normally do **not** require a decision entry:

- a helper function name;
- a route's Python function name;
- an internal repository method;
- an implementation-specific prompt;
- an exact configurable timeout;
- a dependency version;
- a temporary file path.

Promote something to a decision only when:

- multiple reasonable approaches existed; and
- choosing one affects architecture, product behavior, security, persistence, deployment, or future implementation direction.
