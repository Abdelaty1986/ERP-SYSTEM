# LedgerX AI Review Checklist

Before accepting AI-generated changes, check the following:

## General
- [ ] Did the AI modify only the requested files?
- [ ] Did it avoid deleting existing functionality?
- [ ] Did it keep existing routes working?
- [ ] Did it explain what changed?

## Database
- [ ] No table was dropped.
- [ ] No column was dropped.
- [ ] Migration is safe to run multiple times.
- [ ] Existing data is preserved.

## Accounting
- [ ] Journal entries remain balanced.
- [ ] Debit equals credit.
- [ ] Sales/purchases/returns affect the correct accounts.
- [ ] Old transactions are not incorrectly changed.

## Inventory
- [ ] Quantities are updated correctly.
- [ ] Unit conversion is respected.
- [ ] Stock movement has a document reference.

## UI
- [ ] No required field disappeared.
- [ ] Names/IDs/classes used by JS were preserved.
- [ ] Desktop layout is comfortable.
- [ ] Mobile layout is usable.

## Permissions
- [ ] Viewer users cannot write.
- [ ] Admin/developer tools are protected.
- [ ] Existing role checks still work.

## Final
- [ ] migrations.py ran successfully.
- [ ] Tests ran successfully or failures are explained.
- [ ] Manual screen test completed.
- [ ] Safe to merge later.
