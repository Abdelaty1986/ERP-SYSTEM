# Demo Ready Report

- Backup: `before_seed_demo_20260501_033610.db`
- Accounts kept: `87`
- Customers: `2`
- Suppliers: `2`
- Products: `2`
- Journal entries: `18`
- Ledger lines: `36`

## Scenario

1. Opening balances for cash, bank, and inventory.
2. Purchase order + goods receipt + supplier invoice for a taxable supplier.
3. Direct supplier invoice for an exempt supplier.
4. Sales order + delivery note + customer invoice for a taxable customer.
5. Direct financial sales invoice for a normal customer.
6. Partial receipt from customer and partial payment to supplier.
7. One manual administrative expense journal.

## Accounting Check

- Trial debit: `450541.96`
- Trial credit: `450541.96`
- Balanced: `yes`
