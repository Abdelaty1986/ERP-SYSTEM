# LedgerX Project Rules

## Project Goal
LedgerX is an accounting/ERP system focused on stable desktop usage first, with acceptable mobile support for monitoring and quick actions.

## Golden Rule
Never break existing accounting, inventory, permissions, routes, database data, or working screens.

## Protected Areas
The following areas require extra caution:
- Accounting journal entries
- Ledger and trial balance logic
- Inventory quantities and stock movement
- Sales invoices and returns
- Purchase invoices, purchase orders, and receipts
- User permissions and roles
- Database migrations
- Existing customer/supplier/product data

## Database Rules
- Never delete database.db.
- Never drop a table.
- Never drop a column.
- Never rename a column without a compatibility migration.
- Always use non-destructive migrations.
- Before adding a column, check if it already exists.
- Every migration must be safe to run more than once.
- Existing data must be preserved.

## Flask / Routes Rules
- Do not remove existing routes.
- Do not change route URLs unless explicitly requested.
- If a route is replaced, keep a redirect or backward compatibility.
- Do not change endpoint names used by templates unless all references are updated.

## Template / UI Rules
- Do not remove existing form fields.
- Do not rename name, id, or JavaScript class hooks unless required and documented.
- UI improvements should preserve all current functionality.
- Desktop experience is the priority.
- Mobile experience should remain usable for monitoring and quick entry.

## Invoice Rules
- A multi-line invoice must remain one invoice with multiple lines.
- Each invoice line must keep product, unit, quantity, price, VAT, withholding, subtotal, and net values.
- Existing invoices must not be recalculated incorrectly because of future product price changes.
- Live totals before saving must match saved totals after saving.
- Do not change invoice posting logic without tests.

## Accounting Rules
- Every financial transaction must create balanced journal entries.
- Total debit must equal total credit.
- Cash sales affect cash/bank, sales, VAT, and inventory/COGS where applicable.
- Credit sales affect customer, sales, VAT, and inventory/COGS where applicable.
- Returns must reverse accounting and inventory impact clearly.
- Never post an unbalanced entry.

## Inventory Rules
- Stock quantities must never go negative unless explicitly allowed by business rule.
- Stock movements must have source document references.
- Units of measure must respect conversion factors.
- Historical transactions must keep their original unit/price data.

## Permissions Rules
- Do not bypass can_write, can_view, or role checks.
- Viewer users must not be able to create, edit, cancel, delete, or post transactions.
- Developer/admin tools must remain protected.

## Testing Rules
Before accepting any development:
1. Run migrations.
2. Run available tests.
3. Open the affected screen.
4. Test create/edit/delete where applicable.
5. Test accounting impact.
6. Test inventory impact.
7. Test permissions if the screen is protected.
8. Confirm no existing route is broken.

## Git Rules
- main branch is stable.
- AI development must happen on dev-ai.
- Do not push experimental changes directly to main.
- Merge to main only after review and tests.
