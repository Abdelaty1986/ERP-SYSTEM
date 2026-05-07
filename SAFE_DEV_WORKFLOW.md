# LedgerX Safe Development Workflow

## Daily Development Flow

### 1. Make sure you are on the AI development branch
```bash
git branch
```

If not on dev-ai:
```bash
git checkout dev-ai
```

### 2. Update branch from GitHub
```bash
git pull origin dev-ai
```

### 3. Create or apply changes
Only modify files needed for the current task.

### 4. Run migrations
```bash
python migrations.py
```

### 5. Run tests
Start with the available tests:
```bash
python tests/invoice_workflow_test.py
```

If there are more tests:
```bash
python -m pytest
```

### 6. Manual check
Open the affected screen and test:
- Page opens
- Add/edit works
- Save works
- Totals are correct
- Accounting impact is correct
- Inventory impact is correct
- Permissions are respected

### 7. Commit changes
```bash
git add .
git commit -m "describe the change clearly"
git push origin dev-ai
```

### 8. Merge later only after review
Do not merge to main until the change is tested.
