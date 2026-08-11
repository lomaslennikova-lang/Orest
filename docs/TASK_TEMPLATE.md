# Orest — Task Template for Vibe Coding

> This document is the everyday task-format reference for working with an AI agent on Orest. Its canonical repository path is `docs/TASK_TEMPLATE.md`.
>
> The user defines the outcome, constraints, and acceptance criteria.
> The agent is responsible for inspecting the repository, finding the relevant implementation, planning when needed, making the smallest coherent change, verifying it, and reporting the result.
>
> Project-wide rules do not need to be repeated in every task. They are defined in `AGENTS.md`.

---

## 1. Default task format

For most everyday tasks, use only this:

```text
IMPLEMENT

Goal:
What should work after this task?

Current behavior:
What happens now?

Constraints:
What must not change, or what limits matter?

Done when:
How can we verify the result?
```

This is the preferred default format.

You do not need to specify:

- which files to edit;
- which functions to create;
- which tests to run;
- which architecture layers to use;

unless those details are themselves part of the requirement.

The agent should discover technical details from the repository.

---

## 2. Minimal task format

For a small, obvious change:

```text
IMPLEMENT

Goal:
...

Done when:
...
```

Example:

```text
IMPLEMENT

Goal:
Change the button label from "Delete" to "Remove" in the transaction table.

Done when:
The new label is visible in the web UI and the existing delete behavior is unchanged.
```

For trivial low-risk tasks, the agent may keep planning implicit.

---

## 3. Standard implementation task

Use when the change affects behavior but does not require a separate design discussion.

```text
IMPLEMENT

Goal:
...

Current behavior:
...

Constraints:
...

Done when:
- ...
- ...
- ...
```

Optional:

```text
Why:
Why does this matter to the user or product?
```

Add `Why` only when it helps the agent choose the correct implementation.

---

## 4. Analyze first

Use this when the task is architectural, risky, unclear, cross-component, or likely to have several valid solutions.

```text
ANALYZE ONLY

Goal:
...

Current behavior:
...

Constraints:
...

Questions to resolve:
- ...
- ...

Return:
- current implementation;
- relevant components/files;
- options;
- risks and tradeoffs;
- recommendation;
- proposed change scope.

Do not modify files.
```

Typical uses:

- new architecture;
- authentication changes;
- database redesign;
- new external integration;
- AI autonomy/write capabilities;
- deployment topology;
- significant refactoring;
- unclear legacy behavior.

After reviewing the analysis, continue with:

```text
IMPLEMENT

Use the agreed approach.

Done when:
...
```

---

## 5. Bug fix

For a reproducible problem:

```text
BUG

Observed:
What happens now?

Expected:
What should happen?

Steps to reproduce:
1. ...
2. ...
3. ...

Evidence:
Error message, screenshot, log, or other useful evidence.

Constraints:
What should not change?

Done when:
- the bug is reproducible before the fix;
- the reported behavior is corrected;
- relevant regression checks pass.
```

Use exact error text when available.

Do not prescribe the technical fix unless the implementation method itself is a requirement.

---

## 6. UI task

Describe desired behavior rather than low-level CSS when possible.

Preferred:

```text
IMPLEMENT

Goal:
Make the Amount field approximately half as wide while keeping values up to 100000 fully visible.

Current behavior:
The field occupies too much horizontal space.

Constraints:
Do not change validation or transaction behavior.

Done when:
The field is visibly narrower on the current layout and valid values remain readable.
```

Avoid unnecessary implementation instructions such as exact pixels unless exact dimensions are a true design requirement.

Screenshots are useful when the problem is visual.

---

## 7. API task

Use when the user-visible requirement depends on an API change.

```text
IMPLEMENT

Goal:
...

Current behavior:
...

Contract requirements:
- authentication/ownership behavior that must remain;
- request/response behavior that matters;
- compatibility requirements.

Constraints:
...

Done when:
- backend behavior works;
- affected consumer still works;
- relevant contract/tests are updated.
```

You normally do not need to specify the exact route or file if the agent can discover the existing API structure.

---

## 8. Database task

Use when persistent data or schema must change.

```text
IMPLEMENT

Goal:
...

Current data model:
Only include product-level facts the agent cannot reliably infer.

Data behavior required:
...

Constraints:
- preserve existing data;
- no destructive migration unless explicitly required;
- other important product constraints.

Done when:
- model behavior is correct;
- required migration exists;
- migration is reviewed/verified safely;
- relevant consumers/tests pass.
```

If a schema change is not obviously required, let the agent determine whether one is needed.

---

## 9. AI feature — read/analyze only

For an AI capability with no external write side effect:

```text
IMPLEMENT

Goal:
What should the AI be able to answer or analyze?

Allowed data:
What information may the AI use?

AI must not:
Any explicit product/security limits not already covered by AGENTS.md.

Expected behavior:
...

Ambiguous case:
What should happen when required information is unclear?

Done when:
- ...
```

Do not repeat project-wide least-privilege rules unless the task introduces a special exception or new boundary.

---

## 10. AI write-action task

Use a stricter contract whenever AI can propose or cause a persistent/external change.

```text
AI WRITE ACTION

Goal:
What real-world or persistent action should become possible?

AI may:
What may the model infer or propose?

AI must not:
What must never happen automatically?

Write effect:
What exact persistent/external change may occur?

Confirmation:
What explicit user confirmation is required before execution?

Validation:
What must the backend validate?

Ambiguous case:
When must the system ask for clarification instead of guessing?

Ownership/security:
Any task-specific ownership or access requirement.

Done when:
- no write occurs before confirmation;
- invalid/ambiguous input does not execute;
- cancel does not execute;
- valid confirm executes the expected action;
- repeated confirm is safe;
- ownership is enforced;
- relevant audit/result behavior is preserved;
- relevant tests pass.
```

This format is recommended for:

- transaction creation/edit/delete through AI;
- file/storage actions;
- email/message sending;
- account/config changes;
- any future AI-triggered persistent side effect.

---

## 11. Refactoring task

Use when the goal really is structural improvement rather than product behavior.

```text
IMPLEMENT

Goal:
What structural problem should be improved?

Current problem:
Why is the current structure causing maintenance, duplication, testing, or reliability issues?

Behavior to preserve:
- ...
- ...

Scope:
Which part may be refactored?

Out of scope:
What should remain untouched?

Done when:
- external behavior remains unchanged;
- duplication/structural problem is reduced;
- relevant tests/builds pass;
- no unrelated cleanup is included.
```

Do not use a refactoring task as a hidden way to redesign unrelated working code.

---

## 12. Deployment-sensitive task

Use when code changes require Render/config/migration/storage/OAuth awareness.

```text
IMPLEMENT

Goal:
...

Deployment effect expected:
If known, describe the expected effect.

Constraints:
...

Done when:
- code behavior is correct;
- deployment-sensitive files/config are updated if required;
- image/build checks pass where relevant;
- required manual deployment actions are clearly reported.
```

The agent should report:

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

---

## 13. Product decisions vs implementation details

A useful rule:

```text
If two technically valid solutions produce different user behavior,
the choice is a product decision.
```

Product decisions should be stated by the user or explicitly resolved before implementation.

Examples:

- Should deleting a category delete its transactions or move them elsewhere?
- Should AI create a missing category automatically?
- Should an ambiguous receipt total be guessed or clarified?
- Should a write happen automatically or require confirmation?

Implementation details usually belong to the agent.

Examples:

- which helper function to create;
- which existing service to reuse;
- exact internal module organization;
- test file location;
- variable names.

---

## 14. When to name files or technical implementation

Usually, do not tell the agent which files to edit.

Name a file or technical approach when:

1. the location/approach is itself a requirement;
2. a previous attempt changed the wrong layer;
3. a compatibility constraint requires a specific existing component;
4. you are intentionally studying a particular architecture choice.

Example:

```text
Constraint:
Keep transaction validation in the existing shared backend validation layer.
Do not move it into the React form.
```

---

## 15. Good acceptance criteria

Acceptance criteria should describe observable results.

Weak:

```text
- write correct code;
- make it work;
- no errors.
```

Strong:

```text
- after Confirm, exactly one transaction is created;
- Cancel creates no transaction;
- reloading the page preserves the result;
- an invalid category is rejected by the backend;
- repeated Confirm does not create a duplicate.
```

Prefer criteria that can be tested or directly observed.

---

## 16. Do not over-specify edge cases

The user does not need to enumerate every technical edge case.

For non-trivial tasks, the agent is responsible for identifying relevant:

- invalid input;
- empty/missing data;
- authorization/ownership;
- retry/duplicate behavior;
- provider failure;
- persistence;
- state transitions;
- compatibility risks.

Specify an edge case yourself when it represents a **product decision**, not merely a technical test case.

---

## 17. Evidence to include with a task

Useful evidence may include:

- exact error text;
- screenshot;
- relevant log excerpt;
- URL/route;
- steps to reproduce;
- expected example input/output.

Do not paste large amounts of repository code when the agent can inspect the files directly.

Do not include secrets.

---

## 18. What the user should not need to repeat

Do not repeat these project-wide rules in ordinary tasks:

- inspect before inventing;
- preserve architecture;
- smallest coherent change;
- no unrelated refactoring;
- backend owns persistent/security-sensitive decisions;
- Alembic for new schema evolution;
- least privilege for LLM;
- explicit confirmation for protected AI financial writes;
- secret handling;
- Git/destructive-operation policy;
- verification and final diff review;
- completion report.

They already live in `AGENTS.md`.

---

## 19. Expected agent response for a non-trivial IMPLEMENT task

The agent should normally:

```text
1. Inspect the existing implementation.
2. State meaningful assumptions/risks.
3. Provide a concise plan.
4. Implement the requested behavior.
5. Run relevant verification.
6. Review the final diff.
7. Report the result and any manual action.
```

The user does not need to restate this sequence in each task.

---

## 20. Completion report expectation

For a non-trivial task, expect a concise report similar to:

```text
Completed

Changed:
- ...

Files:
- ...

Verification:
- PASS: ...
- NOT RUN: ...

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

For a trivial task, a much shorter completion note is sufficient.

---

# Everyday quick reference

## Normal task

```text
IMPLEMENT

Goal:
...

Current behavior:
...

Constraints:
...

Done when:
...
```

## Small task

```text
IMPLEMENT

Goal:
...

Done when:
...
```

## Analyze before coding

```text
ANALYZE ONLY

Goal:
...

Constraints:
...

Return:
- current implementation;
- options;
- risks;
- recommendation.

Do not modify files.
```

## Bug

```text
BUG

Observed:
...

Expected:
...

Steps to reproduce:
1. ...
2. ...

Done when:
...
```

## AI write-action

```text
AI WRITE ACTION

Goal:
...

AI may:
...

AI must not:
...

Write effect:
...

Confirmation:
...

Ambiguous case:
...

Done when:
...
```

---

# Final principle

The best everyday task prompt does not explain how to program the solution.

It defines:

```text
what should change
+
what must remain stable
+
how success is observed
```

The repository and `AGENTS.md` provide the rest of the working context.
