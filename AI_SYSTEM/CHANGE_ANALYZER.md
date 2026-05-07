# LedgerX AI Change Analyzer

## Purpose
This document teaches AI systems how to analyze a requested change before modifying LedgerX ERP.

The AI must think like:
- ERP architect
- accounting reviewer
- inventory reviewer
- risk analyst
- QA engineer

Not just a code generator.

---

# Step 1: Understand the Request

Before changing anything, identify:

- What is the requested feature/fix?
- Which module is affected?
- Is the change:
  - UI only
  - business logic
  - database
  - accounting
  - inventory
  - permissions
  - reports
  - API/route related

---

# Step 2: Determine Criticality

## Very High Risk
Changes affecting:
- accounting
- journal entries
- posting logic
- inventory quantities
- permissions
- migrations
- invoice calculations

## Medium Risk
Changes affecting:
- templates
- css
- reports
- dashboards

## Low Risk
Changes affecting:
- colors
- spacing
- labels
- static content

---

# Step 3: Read Related Files

Before modifying:
- Read module_map.json
- Read impact_matrix.json
- Read PROJECT_RULES.md
- Read PROJECT_CONTEXT.json

Then identify:
- related files
- related routes
- related templates
- related JS
- related migrations

---

# Step 4: Analyze Side Effects

The AI must ask:

## Accounting Impact
- Will journal entries change?
- Can balances become incorrect?
- Can debit/credit become unbalanced?

## Inventory Impact
- Will stock quantities change?
- Will unit conversion break?
- Can negative stock occur?

## UI Impact
- Will forms become unusable?
- Will mobile break?
- Will JavaScript selectors break?

## Database Impact
- Is migration required?
- Is migration safe?
- Is existing data preserved?

## Permissions Impact
- Can unauthorized users gain access?
- Are protected routes still protected?

---

# Step 5: Decide Development Strategy

## UI-Only Strategy
Allowed:
- CSS
- spacing
- layout improvements
- responsive fixes

Avoid:
- changing input names
- changing JS hooks

---

## Safe Backend Strategy
Allowed:
- helper functions
- defensive checks
- validation improvements

Avoid:
- rewriting stable logic
- changing historical transaction behavior

---

## Migration Strategy
Rules:
- never drop tables
- never drop columns
- check existence before ALTER TABLE
- migration must be repeat-safe

---

# Step 6: Generate Risk Report

Before coding, AI should summarize:

- affected modules
- affected files
- risk level
- required tests
- possible side effects

---

# Step 7: Required Validation

Minimum validation:

## UI
- open page
- create transaction
- edit transaction
- responsive check

## Accounting
- verify journal entry
- verify debit = credit

## Inventory
- verify stock movement
- verify quantities

## Permissions
- verify viewer restrictions
- verify admin access

---

# Step 8: Merge Safety

Never merge to main automatically.

All AI-generated changes must:
- stay in dev-ai first
- pass review
- pass tests
- pass manual validation

