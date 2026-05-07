# Task: Improve Invoice Workspace UX

## Status
Pending

## Priority
High

## Goal
Improve invoice entry workspace UI/UX for desktop usage.

## Requirements
- Give invoice lines table more space.
- Reduce summary panel width.
- Preserve all existing logic.
- Preserve JavaScript behavior.
- Preserve accounting calculations.
- Keep mobile usable.

## Files Likely Affected
- static/css/ledgerx_invoice_workspace.css
- static/css/ledgerx_ui.css
- templates/sales.html
- templates/purchases.html

## Forbidden
- No database changes
- No route changes
- No accounting logic changes
- No inventory logic changes

## Validation
- Open sales invoice
- Open purchase invoice
- Add multiple lines
- Test totals
- Test responsive layout

## Branch
dev-ai
