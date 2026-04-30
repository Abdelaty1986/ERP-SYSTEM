#!/usr/bin/env bash
set -euo pipefail

# Auto deploy script for PythonAnywhere / Linux server.
# Run it from your project folder:
#   bash deploy.sh
#
# What it does:
# 1) Saves current git commit.
# 2) Pulls latest code from GitHub.
# 3) Installs requirements if requirements.txt exists.
# 4) Runs database migrations.
# 5) Runs Ultimate Test if the file exists.
# 6) Records deployment in app_deployments table.
# 7) Touches reload file if you set PA_WSGI_FILE.

PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"
DB_PATH="${DB_PATH:-$PROJECT_DIR/database.db}"
BRANCH="${BRANCH:-main}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PA_WSGI_FILE="${PA_WSGI_FILE:-}"

cd "$PROJECT_DIR"

echo "============================================================"
echo "Ledger X / ERP Auto Deploy"
echo "Project: $PROJECT_DIR"
echo "Branch : $BRANCH"
echo "DB     : $DB_PATH"
echo "============================================================"

OLD_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
echo "Current commit: $OLD_COMMIT"

echo "Pulling latest code..."
git fetch origin "$BRANCH"
git pull --ff-only origin "$BRANCH"

NEW_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
echo "New commit: $NEW_COMMIT"

if [ -f "requirements.txt" ]; then
  echo "Installing requirements..."
  "$PYTHON_BIN" -m pip install --user -r requirements.txt
fi

echo "Running migrations..."
"$PYTHON_BIN" migrations.py "$DB_PATH"

if [ -f "ultimate_test.py" ]; then
  echo "Running Ultimate Test..."
  "$PYTHON_BIN" ultimate_test.py
elif [ -f "ULTIMATE_TEST.py" ]; then
  echo "Running Ultimate Test..."
  "$PYTHON_BIN" ULTIMATE_TEST.py
elif [ -f "test_ultimate.py" ]; then
  echo "Running Ultimate Test..."
  "$PYTHON_BIN" test_ultimate.py
else
  echo "Ultimate Test file not found. Skipping test step."
fi

echo "Recording deployment..."
"$PYTHON_BIN" - <<PY
import sqlite3
db_path = r"$DB_PATH"
commit = r"$NEW_COMMIT"
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS app_deployments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deployed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    git_commit TEXT,
    status TEXT NOT NULL DEFAULT 'success',
    notes TEXT
)
""")
cur.execute("INSERT INTO app_deployments(git_commit,status,notes) VALUES (?,?,?)", (commit, "success", "auto deploy completed"))
conn.commit()
conn.close()
print("Deployment recorded.")
PY

if [ -n "$PA_WSGI_FILE" ] && [ -f "$PA_WSGI_FILE" ]; then
  echo "Reloading PythonAnywhere app by touching WSGI file..."
  touch "$PA_WSGI_FILE"
else
  echo "PA_WSGI_FILE not set. Reload manually from PythonAnywhere Web tab if needed."
fi

echo "============================================================"
echo "Deploy completed successfully ✅"
echo "Old commit: $OLD_COMMIT"
echo "New commit: $NEW_COMMIT"
echo "============================================================"
