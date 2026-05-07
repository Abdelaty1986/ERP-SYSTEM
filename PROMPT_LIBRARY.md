# LedgerX Prompt Library

## Safe UI Improvement Prompt

```text
You are working on LedgerX ERP.

Work only on branch dev-ai.

Improve the UI/UX of the following screen:
[screen name]

Rules:
- Do not remove any field, button, route, or feature.
- Do not change Flask route logic.
- Do not change database schema unless explicitly required.
- Do not rename input name/id/class used by JavaScript.
- Preserve all existing calculations and save behavior.
- Desktop experience is the priority.
- Mobile should remain usable.

Files to review:
[list files]

Required output:
- List changed files.
- Explain what changed.
- Confirm no business logic was changed.
- Provide manual test steps.
```

## Safe Migration Prompt

```text
You are working on LedgerX ERP.

Create a non-destructive migration.

Rules:
- Never drop tables.
- Never drop columns.
- Check if each column exists before adding it.
- Migration must be safe to run multiple times.
- Preserve all existing data.
- Do not alter old transactions incorrectly.

Required output:
- Migration summary.
- Tables/columns affected.
- Rollback note.
- Tests or manual SQL checks.
```

## Accounting Logic Prompt

```text
You are working on LedgerX ERP accounting logic.

Before changing code:
- Identify the accounting entry.
- Show debit and credit sides.
- Confirm total debit equals total credit.
- Explain inventory impact if any.

Rules:
- Do not post unbalanced entries.
- Do not change historical transactions.
- Preserve existing routes and permissions.

Required output:
- Files changed.
- Accounting explanation.
- Test scenario.
```

## Permissions Prompt

```text
You are working on LedgerX ERP permissions.

Goal:
[describe permission improvement]

Rules:
- Viewer users must not create/edit/delete/post.
- Keep admin/developer access protected.
- Reuse existing permission helpers when possible.
- Do not hardcode user names.

Required output:
- Files changed.
- Permission matrix.
- Manual test steps for viewer/admin.
```

## Bug Fix Prompt

```text
You are fixing a LedgerX bug.

Bug:
[paste error]

Rules:
- Find root cause first.
- Make the smallest safe fix.
- Do not rewrite unrelated code.
- Preserve data and routes.
- Add defensive checks if needed.

Required output:
- Root cause.
- Fix summary.
- Files changed.
- Tests run.
```
