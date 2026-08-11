# Orest — API Contracts

> This document defines compatibility promises and externally observable API behavior for Orest.
>
> OpenAPI describes the current mechanical schema.
> `docs/API_CONTRACTS.md` describes the behavioral semantics and compatibility expectations that must not change accidentally.
>
> Internal implementation details such as SQLAlchemy query structure, repository method names, Gemini prompts, LangGraph node layout, storage paths, and Docker behavior are not API contracts.
>

---

## 1. Scope and what counts as an API contract

This file covers the **HTTP/FastAPI interface** used by the web application and operational integrations. Telegram bot commands are a separate user-visible interface currently documented in `README.md` and implemented in `app/main.py`; they are not defined by this HTTP contract file.

For Orest HTTP APIs, a contract includes:

1. HTTP method and path;
2. authentication requirement;
3. ownership semantics;
4. request semantics;
5. response semantics;
6. meaningful error/status semantics;
7. side effects and state transitions.

A Python function name, ORM query, repository helper, prompt text, or internal service structure is not part of the public API contract unless it becomes externally observable.

---

## 2. Stability levels

### STABLE

Used by the current frontend or by a critical application flow.

Stable contracts must not change accidentally or as an unrelated refactor.

Examples:

- admin session API;
- transaction list/create/delete;
- AI chat;
- AI conversation endpoints;
- receipt attachment upload/access;
- pending AI action endpoints.

### SUPPORTED

Current supported API behavior that is part of the application but is not as tightly coupled to the primary frontend flow.

Example:

- `/api/summary`;
- one-shot AI financial analysis.

A supported contract may evolve, but consumers and tests must be reviewed before a breaking change.

### OPERATIONAL

Endpoints used for setup, administration, bootstrap, OAuth, or operational integration rather than ordinary application interaction.

Example:

- Google Drive OAuth connection endpoints.

Operational endpoints still have security and behavioral contracts, but are not treated as core finance/UI API.

### PROTECTED STABLE

A modifier for STABLE behavior whose accidental change could directly alter financial side effects, ownership, privacy, or the human-confirmation safety model.

Current examples include the AI pending-action execution endpoints.

Changing PROTECTED STABLE behavior requires explicit impact review and must not occur as incidental refactoring.

---

## 3. Common authentication semantics

Except where explicitly documented as public, Orest API endpoints use the authenticated admin session.

The web admin session is established by `/api/login` and carried in a signed session cookie.

Protected endpoints depend on server-side session validation.

General authentication behavior:

```text
valid admin session
    -> endpoint continues

missing / invalid / expired admin session
    -> 401
```

Some configuration failures can produce `503` before normal authentication can proceed.

Ownership-sensitive resources such as conversations, attachments, and pending actions are scoped to the authenticated application user.

---

# 4. Health

## `GET /health`

**Stability:** STABLE operational health contract  
**Authentication:** Public  
**Side effect:** none

### Success

```http
200 OK
```

```json
{
  "status": "ok"
}
```

### Behavioral semantics

A successful health response currently means:

- FastAPI is responding; and
- the database connectivity check completed successfully.

This endpoint is not an authenticated admin endpoint.

---

# 5. Admin authentication

## `POST /api/login`

**Stability:** STABLE  
**Authentication:** Public before login

### Request

```json
{
  "username": "string",
  "password": "string"
}
```

### Success

```http
200 OK
```

```json
{
  "username": "configured-admin-name",
  "role": "admin"
}
```

A successful response also sets the signed admin session cookie.

Current cookie semantics include:

- `HttpOnly`;
- `SameSite=Lax`;
- configurable `Secure`;
- session lifetime currently 8 hours.

### Errors

```text
401
```

Invalid username or password.

```text
503
```

Admin authentication is not configured.

---

## `POST /api/logout`

**Stability:** STABLE

### Success

```json
{
  "status": "ok"
}
```

The admin session cookie is deleted.

---

## `GET /api/me`

**Stability:** STABLE  
**Authentication:** Admin required

### Success

```json
{
  "username": "configured-admin-name",
  "role": "admin"
}
```

### Errors

```text
401
```

No valid admin session.

---

# 6. Finance API

## `GET /api/transactions`

**Stability:** STABLE  
**Authentication:** Admin required  
**Side effect:** none

Returns the transaction list used by the web interface.

### Response item

```json
{
  "id": 123,
  "amount": 100.0,
  "category": "Food",
  "type": "expense",
  "created_at": "2026-08-11T12:00:00+00:00",
  "user": "admin"
}
```

Stable field names:

```text
id
amount
category
type
created_at
user
```

Current ordering is newest transaction first by `created_at`.

`amount` is serialized as an absolute numeric value; direction is represented separately by `type`.

Changing these field names or semantics requires consumer review.

---

## `POST /api/transactions`

**Stability:** STABLE  
**Authentication:** Admin required  
**Side effect:** creates one transaction

### Request

```json
{
  "created_at": "2026-08-11T12:00:00+00:00",
  "amount": 100.0,
  "category": "Food",
  "type": "expense"
}
```

Request fields:

```text
created_at
amount
category
type
```

The backend applies the shared transaction validation rules before writing.

### Success

```http
201 Created
```

```json
{
  "status": "created",
  "id": 123
}
```

### Validation

Invalid financial input is rejected server-side.

Typical invalid data is returned as:

```text
422
```

Manual web creation and AI-confirmed creation are expected to remain consistent with the same server-side financial validation rules.

---

## `DELETE /api/transactions/{transaction_id}`

**Stability:** STABLE  
**Authentication:** Admin required  
**Side effect:** deletes the selected transaction

### Success

```json
{
  "status": "deleted"
}
```

### Errors

```text
404
```

Transaction does not exist.

---

## `GET /api/summary`

**Stability:** SUPPORTED  
**Authentication:** Admin required  
**Side effect:** none

### Success

```json
{
  "total_income": 0.0,
  "total_expense": 0.0,
  "balance": 0.0
}
```

Current fields:

```text
total_income
total_expense
balance
```

This endpoint is supported, but it is not treated as tightly frontend-coupled as `/api/transactions`.

---

# 7. One-shot AI financial analysis

## `POST /api/ai/analyze-transactions`

**Stability:** SUPPORTED  
**Authentication:** Admin required  
**Side effect:** external AI call; no financial write

### Optional request filters

```json
{
  "date_from": "2026-08-01",
  "date_to": "2026-08-31",
  "transaction_type": "expense",
  "user": "admin"
}
```

Fields:

```text
date_from?
date_to?
transaction_type? = income | expense
user?
```

### Response

```json
{
  "summary": "string",
  "top_expense_categories": [],
  "risks": [],
  "advice": [
    "item 1",
    "item 2",
    "item 3"
  ]
}
```

Current response semantics include exactly three `advice` items.

### Errors

```text
422
```

No matching transactions, or no expense transaction exists for the selected analysis.

```text
503
```

AI provider request failed or is unavailable.

```text
502
```

AI provider returned an unexpected response format.

---

# 8. AI chat

## `POST /api/ai/chat`

**Stability:** STABLE  
**Authentication:** Admin required

### Request

```json
{
  "message": "string",
  "conversation_id": null,
  "attachment_id": null,
  "clarification_action_id": null
}
```

Fields:

```text
message
conversation_id?
attachment_id?
clarification_action_id?
```

Current validation:

- `message`: 1..2000 characters after trimming;
- extra fields are rejected;
- `attachment_id` and `clarification_action_id` cannot be used together.

### Response

```json
{
  "conversation_id": "uuid",
  "message": {
    "id": 1,
    "conversation_id": "uuid",
    "role": "assistant",
    "content": "string",
    "tool_name": null,
    "tool_call_id": null,
    "status": "completed",
    "created_at": "2026-08-11T12:00:00+00:00"
  },
  "pending_action_id": null,
  "pending_action_status": null
}
```

When a receipt/action workflow produces a pending action:

```text
pending_action_status =
    pending_confirmation
    or
    needs_clarification
```

### Conversation behavior

If `conversation_id` is provided:

- it must be owned by the current admin user;
- otherwise the request does not operate on that conversation.

If no `conversation_id` is supplied:

- the current last owned conversation may be reused;
- if none exists, a new conversation is created.

### Receipt/action behavior

A direct `attachment_id` may start a receipt-analysis flow.

A `clarification_action_id` resumes an owned action in `needs_clarification` state.

These two inputs are mutually exclusive.

### Errors

```text
404
```

Conversation or receipt resource does not exist for the current owner.

```text
409
```

Clarification action is no longer available for clarification.

```text
410
```

Receipt retention period has expired.

```text
422
```

Request or generated receipt draft is invalid.

```text
429
```

AI chat rate limit exceeded.

A `Retry-After` response header is included.

```text
503
```

AI provider, chat checkpoint/runtime, or receipt AI analysis is temporarily unavailable.

---

# 9. AI conversations

## `POST /api/ai/conversations`

**Stability:** STABLE  
**Authentication:** Admin required  
**Side effect:** creates a new empty conversation

### Success

```http
201 Created
```

Response:

```json
{
  "id": "uuid",
  "owner_user_id": 1,
  "title": null,
  "updated_at": "2026-08-11T12:00:00+00:00"
}
```

Creating a new conversation does not delete the owner's previous conversation history.

---

## `GET /api/ai/conversations/last`

**Stability:** STABLE  
**Authentication:** Admin required

Returns the most recent conversation owned by the current admin application user.

### Errors

```text
404
```

No owned conversation exists.

---

## `GET /api/ai/conversations/{conversation_id}/messages`

**Stability:** STABLE  
**Authentication:** Admin required

Optional query:

```text
limit
```

Current accepted range:

```text
1..50
```

Default:

```text
50
```

Only messages from an owned conversation are returned.

The HTTP response currently exposes user/assistant conversation messages.

### Errors

```text
404
```

Conversation does not exist for the owner.

```text
422
```

`limit` is outside `1..50`.

---

# 10. AI prompt suggestions

## `GET /api/ai/prompt-suggestions`

**Stability:** STABLE  
**Authentication:** Admin required

Returns prompt suggestions ordered newest first.

### Item

```json
{
  "id": 1,
  "content": "string",
  "created_at": "2026-08-11T12:00:00+00:00"
}
```

---

## `POST /api/ai/prompt-suggestions`

**Stability:** STABLE  
**Authentication:** Admin required  
**Side effect:** creates one prompt suggestion

### Request

```json
{
  "content": "string"
}
```

Current validation:

- non-blank after trim;
- max 2000 characters;
- extra request fields rejected.

### Success

```http
201 Created
```

Returns the created prompt suggestion.

### Errors

```text
409
```

Duplicate suggestion conflicts with current stored data.

---

## `DELETE /api/ai/prompt-suggestions/{suggestion_id}`

**Stability:** STABLE  
**Authentication:** Admin required  
**Side effect:** deletes one suggestion

### Success

```json
{
  "status": "ok"
}
```

### Errors

```text
404
```

Suggestion does not exist.

---

# 11. Receipt attachments

## `POST /api/ai/attachments`

**Stability:** STABLE  
**Authentication:** Admin required  
**Side effect:** stores one private receipt attachment and metadata

Accepted application media types:

```text
application/pdf
image/png
image/jpeg
```

Current maximum file size:

```text
5 MiB
```

The backend validates the uploaded content before committing attachment metadata.

### Success

```http
201 Created
```

```json
{
  "id": "uuid",
  "filename": "receipt.pdf",
  "media_type": "application/pdf",
  "byte_size": 12345,
  "created_at": "2026-08-11T12:00:00+00:00",
  "expires_at": "2026-08-18T12:00:00+00:00"
}
```

The public contract exposes an opaque attachment identifier, not a public storage path.

### Errors

```text
413
```

Receipt exceeds 5 MiB.

```text
422
```

Receipt validation fails, including unsupported/invalid receipt content.

Do not assume `415` for receipt validation; the current contract uses `422`.

---

# 12. AI pending actions

Pending AI actions are a protected stable contract because they control real financial writes.

## Pending action view

Current HTTP-safe representation:

```json
{
  "id": "uuid",
  "conversation_id": "uuid",
  "status": "pending_confirmation",
  "draft_payload": {},
  "expires_at": "2026-08-11T12:15:00+00:00",
  "completed_at": null,
  "created_transaction_ids": null
}
```

Current possible action statuses:

```text
needs_clarification
pending_confirmation
confirmed
executed
cancelled
expired
failed
```

---

## Common pending-action error semantics

For action operations:

```text
404
```

Action does not exist for the current owner.

```text
410
```

Action has expired.

```text
409
```

Action is already processed or not in a state that allows the requested operation.

These meanings are part of the pending-action state-machine contract.

---

## `GET /api/ai/actions/{action_id}`

**Stability:** PROTECTED STABLE  
**Authentication:** Admin required  
**Ownership:** current owner only  
**Side effect:** none

Returns only an action owned by the current authenticated application user.

An action belonging to another owner is not exposed through this endpoint.

---

## `PUT /api/ai/actions/{action_id}/draft`

**Stability:** PROTECTED STABLE  
**Authentication:** Admin required  
**Ownership:** current owner only  
**Side effect:** modifies pending draft state; does not execute financial write

### Request

```json
{
  "operation_at": "2026-08-11T12:00:00+00:00",
  "rows": [
    {
      "line_number": 1,
      "category": "Food",
      "amount": 100.0
    }
  ]
}
```

Current row validation:

```text
rows: 1..20
line_number?: 1..20
category: non-empty, max 255
amount: > 0 and <= 100000
```

Extra fields are rejected.

Updating the draft is not equivalent to confirming/executing it.

---

## `GET /api/ai/actions/{action_id}/receipt`

**Stability:** PROTECTED STABLE  
**Authentication:** Admin required  
**Ownership:** current owner only  
**Side effect:** none

Returns the private receipt content associated with an owned action.

The response media type matches the stored attachment.

### Errors

```text
404
```

Action/receipt relationship is absent for the owner.

```text
410
```

Receipt retention has expired.

---

## `POST /api/ai/actions/{action_id}/confirm`

**Stability:** PROTECTED STABLE  
**Authentication:** Admin required  
**Ownership:** current owner only  
**Side effect:** may create one or more real financial transactions

This endpoint is the financial execution boundary for the pending-action workflow.

### Success

```json
{
  "id": "uuid",
  "status": "executed",
  "created_transaction_ids": [123],
  "finance_url": "/api/transactions"
}
```

### Required behavioral semantics

Before execution, the backend controls:

- ownership;
- action state;
- expiration;
- server-side draft validation;
- financial transaction creation.

A successful confirmation transitions the action to an executed result.

### Repeat-safe confirm

Repeating confirmation for an already successfully executed action must not create duplicate financial transactions.

The saved execution result is returned instead.

This is a protected compatibility guarantee.

---

## `POST /api/ai/actions/{action_id}/cancel`

**Stability:** PROTECTED STABLE  
**Authentication:** Admin required  
**Ownership:** current owner only  
**Side effect:** cancels pending action; does not create financial transaction

### Success

```json
{
  "id": "uuid",
  "status": "cancelled"
}
```

A cancel operation must not execute the proposed financial write.

---

# 13. Google Drive operational API

These endpoints are OPERATIONAL rather than core application API.

## `GET /api/admin/google-drive/connect`

**Stability:** OPERATIONAL  
**Authentication:** Admin required

Starts the Google Drive OAuth flow.

Current behavior includes:

- generation of a one-time state value;
- state stored in an HttpOnly cookie;
- redirect to the Google authorization flow.

### Errors

```text
503
```

Google Drive integration is not configured.

---

## `GET /api/admin/google-drive/callback`

**Stability:** OPERATIONAL  
**Authentication:** Admin required

Completes OAuth bootstrap.

Current behavior validates:

- authorization result;
- callback `code`;
- callback `state`;
- expected state cookie.

### Errors

```text
400
```

OAuth callback was not completed safely.

```text
502
```

Google OAuth token exchange failed.

The current bootstrap response may display the one-time refresh token to the authenticated admin for manual secure configuration.

It is not a normal application-data API.

---

# 14. Error semantics

Orest does not define one universal meaning for every HTTP status across every endpoint.

Document status codes at the endpoint/family level.

Important established families include:

### Authentication

```text
401
```

Authentication required / invalid session.

### Validation

```text
422
```

Request or domain validation failed.

### Owned resources

```text
404
```

Resource does not exist or is not available to the current owner.

### Pending-action state machine

```text
409
```

Current action state does not allow the requested transition.

```text
410
```

Action/receipt expired.

### Upload

```text
413
```

Receipt exceeds size limit.

### AI runtime

```text
429
```

Chat rate limit.

```text
502 / 503
```

External provider or runtime/integration failure depending on endpoint semantics.

Do not introduce a new status-code convention across unrelated endpoints without reviewing current consumers and tests.

---

# 15. Contract-change process

Before changing a STABLE or PROTECTED STABLE API contract:

1. identify whether the change is breaking or non-breaking;
2. identify all frontend, Telegram, internal, and test consumers;
3. inspect the current Pydantic/HTTP schema;
4. update backend behavior;
5. update all affected consumers;
6. update relevant tests;
7. update this document;
8. report the API impact in the completion report.

Examples of breaking changes include:

- renaming a response field;
- removing a response field;
- changing field meaning/type;
- changing auth requirement;
- changing ownership semantics;
- changing confirm from repeat-safe to duplicate-producing behavior;
- changing a no-write endpoint into a write endpoint;
- changing a stable status/state transition relied on by the frontend.

Adding an optional response/request field may be non-breaking, but consumer behavior must still be reviewed.

---

# 16. Relationship to OpenAPI

FastAPI's generated OpenAPI schema is the primary mechanical description of:

- current routes;
- HTTP methods;
- Pydantic request models;
- Pydantic response models;
- basic validation constraints.

This file is the human/agent-facing behavioral companion to OpenAPI.

If OpenAPI/code and this file disagree:

- inspect the implementation and tests;
- determine whether the code changed intentionally;
- update the stale side;
- do not leave the contradiction unresolved.

---

# 17. Document boundary

This document answers:

```text
What can an API client rely on?
```

Other questions belong elsewhere:

- `AGENTS.md` — how AI agents work;
- `docs/ARCHITECTURE.md` — how the system is structured;
- `docs/DECISIONS.md` — why important choices were made;
- `docs/TESTING.md` — how changes are verified;
- `docs/DEPLOYMENT.md` — how the system is built/deployed.
