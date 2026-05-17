"""
Startup-safe authentication recovery layer for ERP/JARVIS.
Creates or updates the default user on every startup using Werkzeug
password hashing. Never logs plaintext passwords.

Environment variables (optional):
    ERP_DEFAULT_USER     — defaults to "hany"
    ERP_DEFAULT_PASSWORD — defaults to "1986"
"""

import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

DEFAULT_USER = "hany"
DEFAULT_PASSWORD = "1986"


def _get_db_path():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.environ.get("ERP_DB_PATH", os.path.join(base_dir, "database.db"))


def ensure_user_exists():
    username = os.environ.get("ERP_DEFAULT_USER", DEFAULT_USER)
    password = os.environ.get("ERP_DEFAULT_PASSWORD", DEFAULT_PASSWORD)

    db_path = _get_db_path()
    if not os.path.isfile(db_path):
        print("[auth] Database not found, skipping user recovery.")
        return {"created": False, "reason": "no_database"}

    conn = sqlite3.connect(db_path, timeout=30)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, password FROM users WHERE username=?", (username,))
        row = cursor.fetchone()

        if row is None:
            hashed = generate_password_hash(password)
            cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, hashed, "admin"),
            )
            conn.commit()
            print(f"[auth] User '{username}' created successfully.")
            return {"created": True, "action": "created"}
        else:
            stored_hash = row[1]
            is_werkzeug_hash = stored_hash.startswith("scrypt:") or stored_hash.startswith("pbkdf2:")
            if not is_werkzeug_hash:
                hashed = generate_password_hash(password)
                cursor.execute("UPDATE users SET password=? WHERE id=?", (hashed, row[0]))
                conn.commit()
                print(f"[auth] User '{username}' password upgraded to Werkzeug hash.")
                return {"created": False, "action": "upgraded"}
            elif not check_password_hash(stored_hash, password):
                hashed = generate_password_hash(password)
                cursor.execute("UPDATE users SET password=? WHERE id=?", (hashed, row[0]))
                conn.commit()
                print(f"[auth] User '{username}' password updated.")
                return {"created": False, "action": "updated"}
            else:
                print(f"[auth] User '{username}' exists with valid password.")
                return {"created": False, "action": "unchanged"}
    except Exception as exc:
        print(f"[auth] Error ensuring user '{username}': {exc}")
        return {"created": False, "reason": str(exc)}
    finally:
        conn.close()


if __name__ == "__main__":
    result = ensure_user_exists()
    print(f"[auth] Result: {result}")
