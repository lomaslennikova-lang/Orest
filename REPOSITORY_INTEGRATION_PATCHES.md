# Repository documentation integration patches

These are small recommended edits to existing repository documents when the audited set is added.

## 1. `docs/architecture_hist.md` — add at top

```markdown
> **Historical learning document.**
> This file describes an early Telegram-only stage of Orest and is retained for learning history.
> It is not the current architecture source. See `docs/ARCHITECTURE.md`.
```

## 2. `docs/database.md` — add at top

```markdown
> **Historical learning document.**
> This file describes the initial database-design stage before the database was connected.
> Current structure is defined by the code/models/migrations and `docs/ARCHITECTURE.md`.
```

## 3. `docs/deploy.md` — add at top

```markdown
> **Operational deployment runbook.**
> This file contains current human-facing Render/DNS/OAuth steps.
> For stable deployment architecture and agent-facing deployment rules, see `docs/DEPLOYMENT.md`.
> Verify current branch, domain, DNS targets, provider/model values, and callback URLs before applying them.
```

### Replace the outdated receipt troubleshooting statement

Current wording says private external storage is only a future step. Replace it with wording equivalent to:

```markdown
| Receipt upload/AI action loses a locally stored file after restart/redeploy | Free Render local filesystem is ephemeral, or Google Drive storage is not fully configured for that attachment. | Treat local files as temporary. For durable receipt storage, verify the private Google Drive integration and its Environment Variables; existing legacy local attachments remain local. |
```

## 4. `README.md` — recommended opening

Replace the Telegram-only opening with a current short overview, for example:

```markdown
# Orest

Orest is a learning financial application developed through Vibe Coding.
It currently includes a Telegram bot, React/Vite web admin interface, FastAPI backend, PostgreSQL/Neon persistence, Gemini-based AI analysis/chat, and confirmable AI receipt write-actions.
```

Then preserve the Telegram quick-start section as a subsection rather than the identity of the whole repository.

### Add an agent/documentation section

```markdown
## Project documentation

For AI agents, start with [`AGENTS.md`](AGENTS.md).

Current system documentation:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — current structure and data flows;
- [`docs/API_CONTRACTS.md`](docs/API_CONTRACTS.md) — stable API behavior;
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — durable project decisions;
- [`docs/TESTING.md`](docs/TESTING.md) — verification policy;
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — stable deployment model;
- [`docs/TASK_TEMPLATE.md`](docs/TASK_TEMPLATE.md) — everyday Vibe-coding task templates.
```

### API endpoint inventory

The current README endpoint list omits:

```text
POST /api/ai/chat
```

Either add it, or preferably stop treating the README as the complete API registry and point readers to FastAPI OpenAPI plus `docs/API_CONTRACTS.md`.

### Render wording

Where README currently calls the Render deployment “Production-версія”, prefer “deployed web/demo version” or explicitly state that the current Render Free environment is a demo rather than production-grade infrastructure.

## 5. `docs/security.md`

The current statement that secrets live only in local `.env` is incomplete. Update the security note to distinguish:

```text
local runtime secrets   -> .env
deployed runtime secrets -> Render Environment Variables / secret settings
repository template      -> .env.example only, no real values
```

Alternatively, mark `docs/security.md` as an early learning document and point to `AGENTS.md`, `.env.example`, and `docs/DEPLOYMENT.md` for current policy.
