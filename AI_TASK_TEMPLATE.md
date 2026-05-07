# AI Development Task Template

Use this template when asking any AI/Codex assistant to modify LedgerX.

## Task Title
[Write a clear title]

## Branch
Work only on:
dev-ai

Do not modify:
main

## Goal
[Describe what should be achieved]

## Files Likely Affected
- [file path]
- [file path]

## Must Preserve
- Existing routes
- Existing database data
- Existing accounting logic
- Existing inventory logic
- Existing permissions
- Existing input names/ids/classes used by JavaScript

## Allowed Changes
- CSS/UI changes
- Template organization
- Safe JS enhancements
- Non-destructive migration
- Tests

## Forbidden Changes
- Do not delete tables.
- Do not delete columns.
- Do not delete existing routes.
- Do not remove fields or buttons.
- Do not bypass permissions.
- Do not change posting logic unless explicitly requested.

## Required Validation
Run:
```bash
python migrations.py
```

Then run available tests, for example:
```bash
python tests/invoice_workflow_test.py
```

If tests are missing or fail because of missing test data, explain exactly what happened.

## Expected Output
- Summary of changes
- Files changed
- Tests run
- Any risks
- Manual testing checklist
