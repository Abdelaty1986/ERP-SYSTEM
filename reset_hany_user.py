from werkzeug.security import generate_password_hash

try:
    from app import db
except Exception as e:
    print("Error importing app/db:", e)
    print("Make sure this file is inside the main project folder next to app.py")
    raise SystemExit(1)


USERNAME = "hany"
PASSWORD = "1986"
ROLE = "admin"


def main():
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE username = ?", (USERNAME,))
    user = cur.fetchone()

    hashed_password = generate_password_hash(PASSWORD)

    if user:
        cur.execute(
            """
            UPDATE users
            SET password = ?, role = ?
            WHERE username = ?
            """,
            (hashed_password, ROLE, USERNAME),
        )
        print(f"User updated successfully: {USERNAME} / {PASSWORD}")
    else:
        cur.execute(
            """
            INSERT INTO users (username, password, role)
            VALUES (?, ?, ?)
            """,
            (USERNAME, hashed_password, ROLE),
        )
        print(f"User created successfully: {USERNAME} / {PASSWORD}")

    conn.commit()
    conn.close()

    print("Done.")


if __name__ == "__main__":
    main()
