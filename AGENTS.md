# AGENTS.md — AI Working Contract for Orest

> This file defines how AI agents must work with the Orest repository.
> It is an agent-facing behavioral contract, not a replacement for technical documentation.

## 1. Working authority and evidence

Do not treat all repository information as one linear priority list. Different sources answer different questions.

### Current task intent

The user's current explicit goal, constraints, acceptance criteria, and product decisions define the requested outcome.

If the requested outcome intentionally changes an existing contract or protected decision, identify that impact explicitly rather than silently preserving the old behavior.

### Current implementation evidence

Use current code, migrations, runtime configuration, and tests to establish what the repository actually does now.

Tests are evidence of intended behavior, but they can become stale. Do not treat a failing or conflicting test as automatically more authoritative than an explicit stable contract or current task decision.

### Repository policy and intended stable behavior

Use:

- `AGENTS.md` for agent working rules;
- `docs/ARCHITECTURE.md` for current system structure;
- `docs/API_CONTRACTS.md` for stable external behavior;
- `docs/DECISIONS.md` for durable project decisions;
- `docs/TESTING.md` for verification policy;
- `docs/DEPLOYMENT.md` for deployment boundaries;
- feature-specific documentation for detailed feature behavior.

For everyday task formatting, see `docs/TASK_TEMPLATE.md`.

### Conflicts

If code, tests, current documentation, or the user's requested outcome conflict:

1. do not silently choose one source;
2. determine whether the difference is an intentional requested change, a code regression, a stale test, or stale documentation;
3. preserve protected behavior unless the current task explicitly changes it;
4. report the inconsistency and resolve/update the stale side when it is in scope.

`docs/architecture.md` and `docs/database.md` are historical learning documents and are not current architecture sources.

---

## 2. Project model

Orest currently includes:

- Telegram bot;
- FastAPI backend;
- React + Vite frontend;
- PostgreSQL / Neon;
- SQLAlchemy + Alembic;
- Gemini-based AI features;
- persisted AI conversations;
- AI receipt attachments;
- AI pending/write actions;
- Docker Compose for local development;
- `Dockerfile.render` for Render deployment.

Do not treat the repository as only a Telegram bot.

---

## 3. Core working principles

### Inspect before inventing

Before implementation:

1. read this file;
2. inspect files related to the task;
3. understand the current implementation;
4. inspect relevant API contracts, models, migrations, tests, and consumers;
5. determine whether part of the requested behavior already exists;
6. only then design the change.

Do not require the user to provide technical details that can be discovered from the repository.

### Preserve working behavior

Preserve existing working behavior by default.

Do not redesign, replace, or broadly refactor working code merely because another implementation appears cleaner.

Broad refactoring is acceptable only when it is necessary for the requested task or the user explicitly asks for it.

### Smallest coherent change

Make the smallest **architecturally coherent** change that solves the requested problem.

Do not optimize for the fewest changed lines if that would violate existing boundaries or duplicate logic.

### Scope discipline

Do not fix unrelated issues merely because they were discovered while working.

If an unrelated meaningful bug, security issue, outdated contract, or documentation inconsistency is found:

- report it separately;
- do not silently fix it unless it blocks the requested work and the fix is local, safe, and non-breaking.

---

## 4. Task execution flow

For non-trivial work, use:

`Understand -> Plan -> Implement -> Verify -> Report`

### Understand

Identify:

- current behavior;
- requested behavior;
- likely affected files/components;
- contracts that must remain stable;
- meaningful assumptions;
- important risks.

Do not silently make material assumptions.

### Plan

For non-trivial, cross-component, architectural, database, API, security, deployment, or AI write-action changes, explicitly state:

- what exists now;
- what needs to change;
- which areas/files will change;
- what must remain unchanged;
- how the result will be verified.

For trivial, low-risk local changes, planning may remain implicit.

### Implement

Follow current architecture and reuse existing services, repositories, validators, and patterns where appropriate.

### Verify

Implementation is not completion.

Run verification proportional to the affected area and risk.

### Report

Provide a concise completion report proportional to the size of the task.

---

## 5. User task intent

Treat the user's explicit:

- goal;
- constraints;
- acceptance criteria;
- product decisions;

as higher priority than implementation preferences inferred by the agent.

If the user's suggested implementation conflicts with established architecture or a protected invariant:

- do not silently follow it;
- do not silently ignore it;
- explain the conflict and preserve the user's intended outcome using the safest compatible approach.

### Task modes

If the user says `ANALYZE ONLY`:

- inspect and reason;
- do not modify files;
- return current behavior, options, risks, recommendation, and proposed scope.

If the user says `IMPLEMENT`:

- implement within this contract and any explicitly agreed approach.

---

## 6. Architecture boundaries

### Frontend

`frontend/` is the React/Vite UI.

Frontend:

- communicates with backend through HTTP/API;
- must not access PostgreSQL/Neon directly;
- must not receive `DATABASE_URL` or server secrets;
- is not authoritative for authorization or financial validation.

Frontend validation may improve UX, but server-side validation remains authoritative.

### Backend

`app/` is the trusted server-side boundary for:

- authentication;
- authorization;
- security-sensitive logic;
- financial validation;
- ownership checks;
- persistent data access;
- AI tool boundaries;
- pending actions;
- write execution.

### Transaction-rule scope

Current transaction creation is not fully unified across runtimes:

- the FastAPI web/manual and AI-confirmed paths use shared transaction logic under `app/ai_actions/transactions.py`;
- the Telegram bot currently has its own transaction-command path in `app/main.py`.

When changing product-level transaction rules (amount limits, normalization, category behavior, dates, types), inspect all affected runtimes rather than assuming one shared validator covers the whole project. Do not silently introduce further divergence.

### Database

Persistent schema changes require Alembic migrations.

If `app/models.py` changes the persistent schema:

- create a new Alembic migration;
- review it;
- verify it.

Do not edit an already-applied migration to represent a new schema change unless the task is explicitly about repairing migration history.

---

## 7. AI and tool safety

LLMs are not trusted data layers.

Do not give an LLM:

- `DATABASE_URL`;
- database credentials;
- SQLAlchemy sessions;
- arbitrary SQL execution;
- unrestricted filesystem access;
- generic unrestricted write capabilities;
- session cookies;
- OAuth tokens;
- other secrets.

Use the principle of least privilege.

Prefer narrow server-side tools for specific actions instead of broad execution capabilities.

### AI write-actions

Current financial write-actions follow:

`input/attachment -> structured draft -> server validation -> pending action -> explicit confirm -> backend write -> result/audit`

Preserve:

- server-side validation;
- ownership checks;
- state/TTL checks;
- explicit confirmation;
- repeat-safe/idempotent confirmation;
- backend-controlled writes;
- audit/result persistence.

A change from `read/propose` to autonomous `write` is a high-impact behavioral change.

Do not introduce such autonomy without explicit user approval or an explicitly requested outcome that clearly requires it.

---

## 8. Change authority

### A. Agent may proceed

Within the requested task, the agent may perform without per-file approval:

- local bug fixes;
- small UI changes;
- internal helpers/functions;
- tests;
- local refactoring required for the task;
- non-breaking extensions of existing behavior;
- documentation updates;
- validation consistent with an existing contract;
- cleanup directly related to changed code.

### B. Agent may proceed but must disclose

If clearly required by the requested task, the agent may make the following changes but must identify them in the plan and completion report:

- new environment variable;
- new API route;
- new persistent field;
- new Alembic migration;
- new small dependency;
- Docker/runtime changes required by the feature;
- new external integration required by the feature.

### C. Protected changes

Do not introduce the following as incidental improvements:

- fundamental architecture-boundary changes;
- direct frontend database access;
- unrestricted LLM SQL/write access;
- removal of explicit confirmation from financial AI writes;
- weakened authentication or authorization;
- destructive database migrations;
- deletion of tables/columns containing data;
- privacy/retention model changes;
- making private files public;
- production domain/auth/OAuth model changes;
- significant removal of working code;
- Git history rewriting.

A protected change requires either an explicitly requested outcome that clearly requires it, or explicit user approval after impact has been explained.

---

## 9. Dependencies

Prefer:

1. the current project stack;
2. existing dependencies;
3. standard-library capabilities where reasonable.

Add a new dependency only when it provides a clear benefit over a reasonable solution using the current stack.

Explicitly disclose dependencies that:

- are security-sensitive;
- require native/system packages;
- significantly enlarge the image;
- introduce a new external service;
- replace an existing library.

---

## 10. Secrets and sensitive data

Real secrets may be used only where required at runtime.

Never copy, echo, log, document, commit, or reproduce real secret values.

### `.env`

- local/private runtime configuration;
- may contain real secrets;
- must not be committed;
- do not print its full contents in reports or logs.

### `.env.example`

- committed configuration template;
- contains placeholders only;
- must be updated when a new environment variable is introduced.

Do not dump full environment variables, request headers, cookies, auth tokens, database URLs, or OAuth credentials for debugging.

Do not add logs that can expose credentials, authentication headers, session cookies, private receipt contents, or sensitive financial payloads.

Run `scripts/scan-secrets.ps1` when relevant.

---

## 11. Git policy

### Read-only Git commands

The agent may use read-only commands as needed, including:

- `git status`;
- `git diff`;
- `git diff --check`;
- `git log`;
- `git show`;
- `git branch`.

### Working-tree edits

The agent may edit relevant files within the requested task without per-file approval.

### Staging

Do not stage files unless the user asks to prepare a commit or staging is explicitly part of the task.

### Commit

Do not create a Git commit unless the user explicitly asks.

### Push

Never push unless the user explicitly asks to publish/push changes.

### Merge / rebase

Use merge, rebase, branch deletion, or remote changes only when explicitly part of the Git task.

Do not rewrite history merely to make it cleaner.

### Destructive Git operations

Do not discard, overwrite, or delete uncommitted user changes unless the user explicitly requests that exact outcome.

Treat destructive restore/reset/clean operations as protected.

Never force-push unless explicitly requested and the impact has been explained.

Do not revert unrelated user changes.

---

## 12. Destructive and external operations

Do not recursively delete project directories, persistent data, Docker volumes, databases, uploads, or storage as ordinary cleanup.

Do not perform destructive DB or Docker operations unless explicitly required and approved.

Do not use production data as disposable test data.

Do not trigger real-world side effects for testing unless necessary and explicitly understood.

---

## 13. Verification

Run checks proportional to the affected area and risk.

Detailed commands and test matrix: `docs/TESTING.md`.

### General rules

When behavior changes:

- add or update relevant tests;
- include relevant failure cases.

Do not weaken a valid test merely to make an incorrect implementation pass.

If a relevant test fails:

- determine whether the failure is new or pre-existing;
- report that distinction explicitly.

### Frontend

Frontend code changes normally require a successful production build.

### API

When changing an API:

- verify the backend provider;
- verify frontend/other consumers;
- preserve stable request/response/auth/status semantics unless the change is intentional.

### Database

Schema-change completion requires:

- model change;
- new migration;
- migration review;
- relevant tests;
- no unintended destructive behavior.

Do not apply a migration to production merely as a test.

### AI write-actions

Changes to AI write-actions must verify, where applicable:

- draft does not write to DB;
- clarification does not write;
- cancel does not write;
- valid confirm writes correctly;
- repeated confirm does not duplicate writes;
- expired action cannot execute;
- ownership is enforced;
- invalid payload is rejected;
- result/audit behavior is preserved.

### Final diff

Before declaring completion:

- review `git status`;
- review `git diff`;
- run `git diff --check`.

Check for unrelated files, debug code, temporary prints, generated files, secret leakage, accidental contract changes, and unrelated refactoring.

### Security-sensitive changes

For auth, uploads, AI, secrets, DB writes, or external integrations, explicitly review:

1. Did access expand?
2. Is auth/ownership still enforced?
3. Can secrets/private data leak?
4. Was a new destructive/write side effect introduced?

---

## 14. Documentation consistency

If a code change invalidates current agent-facing documentation, updating that documentation is part of the task.

Review, when relevant:

- `AGENTS.md`;
- `docs/ARCHITECTURE.md`;
- `docs/API_CONTRACTS.md`;
- `docs/DECISIONS.md`;
- `docs/TESTING.md`;
- `docs/DEPLOYMENT.md`;
- feature-specific docs;
- `.env.example`.

Do not leave code and current agent-facing documentation knowingly inconsistent.

---

## 15. Definition of Done

A task is **Done** only when:

- the requested behavior is implemented;
- the change is consistent with project architecture;
- relevant verification has passed;
- the final diff has been reviewed;
- contracts and current documentation remain consistent;
- secret/security boundaries remain intact;
- required migrations/config/deployment actions are identified;
- anything not verified or unresolved is explicitly reported.

Partial verification must be reported precisely.

Do not claim a check passed if it was not actually run.

Do not perform production side effects merely to make the task appear fully complete.

---

## 16. Completion report

Use a report proportional to the task.

For non-trivial work, include:

```text
Completed

Changed:
- ...

Files:
- ...

Verification:
- PASS: ...
- NOT RUN: ...
- PRE-EXISTING FAILURE: ...

Impact:
- API: none / ...
- Database: none / ...
- Deployment: none / ...
- Security: none / ...

Manual action required:
- none / ...

Out-of-scope findings:
- none / ...
```

For small local changes, keep the report brief.

---

## 17. Final principle

The user defines:

- the goal;
- product behavior;
- constraints;
- acceptance criteria.

The agent is responsible for:

- understanding the existing system;
- choosing the safest compatible implementation;
- making the smallest coherent change;
- preserving protected invariants;
- verifying the result;
- reporting truthfully what was and was not completed.
