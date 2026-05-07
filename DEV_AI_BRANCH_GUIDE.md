# dev-ai Branch Guide

## Purpose
dev-ai is the safe cloud development branch for AI-assisted improvements.

## Stable branch
main

## AI development branch
dev-ai

## Create branch
```bash
git checkout main
git pull origin main
git checkout -b dev-ai
git push -u origin dev-ai
```

## Switch to dev-ai
```bash
git checkout dev-ai
```

## Push development changes
```bash
git add .
git commit -m "update dev-ai"
git push origin dev-ai
```

## Return to stable main
```bash
git checkout main
```

## Merge rule
Only merge after:
- migrations pass
- tests pass
- manual screen check passes
- user approves
