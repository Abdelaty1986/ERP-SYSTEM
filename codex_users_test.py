import json
import shutil
import tempfile
from pathlib import Path

import app as appmod


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def fetchone(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchone()


def main():
    workspace = Path(__file__).resolve().parent
    source_db = workspace / "database.db"
    temp_dir = Path(tempfile.mkdtemp(prefix="erp-users-test-", dir=str(workspace)))
    temp_db = temp_dir / "database_test.db"
    shutil.copy2(source_db, temp_db)

    old_db_path = appmod.DB_PATH
    old_module_db_path = appmod.MODULE_DEPS.get("DB_PATH")
    appmod.DB_PATH = str(temp_db)
    appmod.MODULE_DEPS["DB_PATH"] = str(temp_db)
    appmod.init_db()
    appmod.app.config["TESTING"] = True

    client = appmod.app.test_client()

    conn = appmod.db()
    cur = conn.cursor()
    cur.execute("INSERT INTO users(username,password,role) VALUES (?,?,?)", ("codex_user", appmod.generate_password_hash("old-pass"), "viewer"))
    normal_user_id = cur.lastrowid
    cur.execute("INSERT INTO users(username,password,role) VALUES (?,?,?)", ("codex_admin", appmod.generate_password_hash("admin-pass"), "admin"))
    second_admin_id = cur.lastrowid
    conn.commit()

    with client.session_transaction() as session:
        session["user_id"] = 1
        session["username"] = "admin"
        session["role"] = "admin"

    change_password = client.post(f"/users/{normal_user_id}/change-password", data={"new_password": "new-pass-123"}, follow_redirects=False)
    assert_true(change_password.status_code in (302, 303), "فشل تغيير كلمة مرور المستخدم")
    new_hash = fetchone(cur, "SELECT password FROM users WHERE id=?", (normal_user_id,))[0]
    assert_true(new_hash != "new-pass-123", "تم حفظ كلمة المرور كنص عادي")
    assert_true(appmod.check_password_hash(new_hash, "new-pass-123"), "كلمة المرور الجديدة لم تُشفّر أو لم تُحفظ بشكل صحيح")

    login_client = appmod.app.test_client()
    login_response = login_client.post("/login", data={"username": "codex_user", "password": "new-pass-123"}, follow_redirects=False)
    assert_true(login_response.status_code in (302, 303), "تعذر الدخول بكلمة المرور الجديدة")

    delete_normal = client.post(f"/users/{normal_user_id}/delete", follow_redirects=False)
    assert_true(delete_normal.status_code in (302, 303), "فشل حذف المستخدم العادي")
    assert_true(fetchone(cur, "SELECT COUNT(*) FROM users WHERE id=?", (normal_user_id,))[0] == 0, "المستخدم العادي لم يُحذف")

    with client.session_transaction() as session:
        session["user_id"] = second_admin_id
        session["username"] = "codex_admin"
        session["role"] = "admin"
    block_self_delete = client.post(f"/users/{second_admin_id}/delete", follow_redirects=False)
    assert_true(block_self_delete.status_code in (302, 303), "فشل تنفيذ اختبار منع حذف المستخدم الحالي")
    assert_true(fetchone(cur, "SELECT COUNT(*) FROM users WHERE id=?", (second_admin_id,))[0] == 1, "تم حذف المستخدم الحالي بالخطأ")

    cur.execute("DELETE FROM users WHERE id=1")
    conn.commit()
    with client.session_transaction() as session:
        session["user_id"] = second_admin_id
        session["username"] = "codex_admin"
        session["role"] = "admin"
    block_last_admin = client.post(f"/users/{second_admin_id}/delete", follow_redirects=False)
    assert_true(block_last_admin.status_code in (302, 303), "فشل تنفيذ اختبار منع حذف آخر مدير")
    assert_true(fetchone(cur, "SELECT COUNT(*) FROM users WHERE id=?", (second_admin_id,))[0] == 1, "تم حذف آخر Admin بالخطأ")

    conn.close()
    appmod.DB_PATH = old_db_path
    appmod.MODULE_DEPS["DB_PATH"] = old_module_db_path
    print(json.dumps({"temp_db": str(temp_db), "normal_user_deleted": True, "last_admin_blocked": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
