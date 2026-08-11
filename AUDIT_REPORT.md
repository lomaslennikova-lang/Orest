# Orest documentation audit

Audit date: 2026-08-11

## Result

The seven-document model is sound and should be kept. The audit found no reason to merge the documents back into a single large file. Each document has a distinct responsibility:

- `AGENTS.md` — agent behavior and authority boundaries;
- `docs/ARCHITECTURE.md` — factual current structure/data flows;
- `docs/API_CONTRACTS.md` — externally observable compatibility promises;
- `docs/DECISIONS.md` — durable rationale and deliberate choices;
- `docs/TESTING.md` — verification policy;
- `docs/DEPLOYMENT.md` — stable deployment model/impact;
- `docs/TASK_TEMPLATE.md` — user-facing daily task format.

## Material corrections applied

### 1. Telegram/FastAPI topology

The earlier architecture diagram incorrectly suggested that the Telegram runtime flows through FastAPI. Current `app/main.py` performs its financial commands directly through SQLAlchemy/database sessions. The audited architecture now shows Telegram and FastAPI as separate runtimes sharing database/model infrastructure.

### 2. AGENTS authority model

The earlier strict linear “source of truth” ranking was too simplistic because code, tests, task intent, API contracts, and decisions answer different questions. It was replaced with separate categories for current task intent, implementation evidence, repository policy/stable behavior, and conflict handling.

### 3. API stability vocabulary

`PROTECTED STABLE` was used for pending-action APIs but was not defined in the stability-level section. It is now explicitly defined.

### 4. Audit durability

The application has a separate JSONL audit trail for executed AI actions, but the current Free Render local filesystem is ephemeral. `DECISIONS.md` and `DEPLOYMENT.md` now state clearly that this is not guaranteed long-term/compliance-grade audit retention.

### 5. Cross-document reference

One `TESTING.md` matrix entry referenced `API_CONTRACTS.md` without the canonical `docs/` path. It is corrected.

### 6. Staleness markers

Static “Verified against main on 2026-08-11” lines were removed from the committed canonical docs. Git history already records document age, while static verification dates quickly become misleading. This audit report retains the audit date instead.

## Code-level findings surfaced by the documentation audit

These are not documentation blockers, but they are worth tracking as separate engineering tasks.

### Transaction-rule duplication across runtimes

FastAPI manual transaction creation and AI-confirmed writes use the shared transaction helper in `app/ai_actions/transactions.py`. Telegram commands in `app/main.py` still implement their own amount/category transaction path. This means a future product-level rule change can diverge between Telegram and web/AI unless both paths are reviewed. The audited `AGENTS.md` and `TESTING.md` now call this out explicitly.

### Audit/DB atomicity gap

The AI action flow appends the JSONL audit record before the surrounding SQLAlchemy transaction commits. This makes audit failure able to block the DB write, but the reverse edge is not atomic: if the later DB commit fails, a filesystem audit record may already exist. Treat stronger audit/DB atomicity as a future engineering decision rather than an already guaranteed property.

## Existing repository documentation requiring cleanup

### `docs/architecture.md`

Keep as a learning-history document, but add a prominent Historical header. It currently says the project has no database and describes Telegram as the only frontend.

### `docs/database.md`

Keep as a learning-history document, but add a Historical header. It explicitly describes the stage before the database was connected.

### `docs/deploy.md`

Keep as the human operational runbook. Add a header pointing to `docs/DEPLOYMENT.md`. Update the old troubleshooting line that says private external receipt storage is merely “the next stage,” because the same document now contains the implemented Google Drive flow. Also treat branch/domain/model/DNS values as current operational values to verify, not permanent architecture.

### `README.md`

README needs a small modernization pass. Its title/intro still present Orest as only a Telegram-bot skeleton, while later sections describe the React/FastAPI/Neon/AI system. Add a current project overview and links to the new documentation set. Also avoid calling the Free Render demo “Production” without qualification. The current endpoint inventory also omits `POST /api/ai/chat`, so it should either be corrected or replaced by a link to `docs/API_CONTRACTS.md` / OpenAPI instead of hand-maintaining a second full route list.

### `docs/security.md`

This file is conceptually still useful, but its statement that secrets are stored “only locally in `.env`” is incomplete for the current deployed system, which also uses Render Environment Variables. Update it or mark it as an early learning note and point current security/configuration guidance to `AGENTS.md`, `.env.example`, and `docs/DEPLOYMENT.md`.

## Recommended final repository structure

```text
Orest/
├─ AGENTS.md
├─ README.md
├─ .env.example
├─ docs/
│  ├─ ARCHITECTURE.md
│  ├─ API_CONTRACTS.md
│  ├─ DECISIONS.md
│  ├─ TESTING.md
│  ├─ DEPLOYMENT.md
│  ├─ TASK_TEMPLATE.md
│  │
│  ├─ architecture.md      # historical learning document
│  ├─ database.md          # historical learning document
│  ├─ deploy.md            # current human operational runbook
│  ├─ ai/                  # feature-specific notes
│  └─ ...
```

## Final assessment

The set is ready for repository integration after applying the accompanying legacy-doc/README cleanup. The most important remaining risk is not the new seven documents; it is older mixed-age documentation that could still mislead an agent if it is left unlabelled.
