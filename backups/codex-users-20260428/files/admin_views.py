import os
import sqlite3
from datetime import datetime

from flask import flash, redirect, render_template, request, send_file, url_for


def _safe_backup_database(source_path, target_path):
    source = sqlite3.connect(source_path, timeout=30)
    target = sqlite3.connect(target_path, timeout=30)
    try:
        source.execute("PRAGMA busy_timeout = 30000")
        source.execute("PRAGMA wal_checkpoint(PASSIVE)")
        source.backup(target)
        target.commit()
    finally:
        target.close()
        source.close()


def _safe_restore_database(source_path, target_path):
    source = sqlite3.connect(source_path, timeout=30)
    target = sqlite3.connect(target_path, timeout=30)
    try:
        source.execute("PRAGMA busy_timeout = 30000")
        target.execute("PRAGMA busy_timeout = 30000")
        target.execute("PRAGMA foreign_keys = OFF")
        source.backup(target)
        target.commit()
        target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        target.execute("PRAGMA foreign_keys = ON")
    finally:
        target.close()
        source.close()


def build_backup_restore_view(deps):
    base_dir = deps["BASE_DIR"]
    db_path = deps["DB_PATH"]

    def backup_restore():
        backup_dir = os.path.join(base_dir, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        if request.method == "POST":
            uploaded = request.files.get("backup_file")
            if not uploaded or not uploaded.filename.endswith(".db"):
                flash("اختر ملف قاعدة بيانات بصيغة db.", "danger")
                return redirect(url_for("backup_restore"))
            restore_path = os.path.join(backup_dir, "restore_upload.db")
            before_restore_path = os.path.join(
                backup_dir, f"before-restore-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
            )
            uploaded.save(restore_path)
            try:
                probe = sqlite3.connect(restore_path, timeout=10)
                probe.execute("PRAGMA schema_version")
                probe.close()
                _safe_backup_database(db_path, before_restore_path)
                _safe_restore_database(restore_path, db_path)
            except sqlite3.Error:
                flash(
                    "تعذر قراءة ملف النسخة الاحتياطية أو استعادته. تأكد من أن الملف قاعدة SQLite صالحة.",
                    "danger",
                )
                return redirect(url_for("backup_restore"))
            finally:
                if os.path.exists(restore_path):
                    os.remove(restore_path)
            flash("تمت استعادة قاعدة البيانات بنجاح من نسخة متسقة وآمنة.", "success")
            return redirect(url_for("backup_restore"))
        if request.args.get("download") == "1":
            filename = f"erp-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
            backup_path = os.path.join(backup_dir, filename)
            _safe_backup_database(db_path, backup_path)
            return send_file(backup_path, as_attachment=True, download_name=filename)
        backups = sorted([name for name in os.listdir(backup_dir) if name.endswith(".db")], reverse=True)
        return render_template("backup.html", backups=backups)

    return backup_restore


def build_audit_log_view(deps):
    db = deps["db"]

    def audit_log():
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT created_at,username,action,entity_type,entity_id,details,old_values,new_values,ip_address
            FROM audit_log
            ORDER BY id DESC
            LIMIT 200
            """
        )
        rows = cur.fetchall()
        conn.close()
        return render_template("audit_log.html", rows=rows)

    return audit_log


def build_permissions_view(deps):
    db = deps["db"]
    permission_modules = deps["PERMISSION_MODULES"]
    log_action = deps["log_action"]

    def permissions():
        roles = [
            ("accountant", "محاسب"),
            ("sales", "مبيعات"),
            ("viewer", "مشاهدة فقط"),
        ]
        access_levels = [
            ("none", "بدون صلاحية"),
            ("read", "مشاهدة"),
            ("write", "إضافة وتعديل"),
        ]
        conn = db()
        cur = conn.cursor()

        if request.method == "POST":
            before = {}
            cur.execute("SELECT role,permission_key,access_level FROM role_permissions")
            for role, permission_key, access_level in cur.fetchall():
                before[f"{role}:{permission_key}"] = access_level

            for role, _label in roles:
                for permission_key, _permission_label in permission_modules:
                    level = request.form.get(f"{role}__{permission_key}", "none")
                    if level not in ("none", "read", "write"):
                        level = "none"
                    cur.execute(
                        """
                        INSERT INTO role_permissions(role,permission_key,access_level)
                        VALUES (?,?,?)
                        ON CONFLICT(role,permission_key) DO UPDATE SET access_level=excluded.access_level
                        """,
                        (role, permission_key, level),
                    )

            after = {}
            cur.execute("SELECT role,permission_key,access_level FROM role_permissions")
            for role, permission_key, access_level in cur.fetchall():
                after[f"{role}:{permission_key}"] = access_level
            log_action(cur, "update", "role_permissions", None, "تحديث مصفوفة الصلاحيات", before, after)
            conn.commit()
            conn.close()
            flash("تم تحديث الصلاحيات التفصيلية.", "success")
            return redirect(url_for("permissions"))

        cur.execute("SELECT role,permission_key,access_level FROM role_permissions")
        matrix = {f"{role}__{permission_key}": access_level for role, permission_key, access_level in cur.fetchall()}
        conn.close()
        return render_template(
            "permissions.html",
            roles=roles,
            modules=permission_modules,
            access_levels=access_levels,
            matrix=matrix,
        )

    return permissions


def build_users_view(deps):
    db = deps["db"]
    generate_password_hash = deps["generate_password_hash"]
    log_action = deps["log_action"]

    def users():
        conn = db()
        cur = conn.cursor()

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            role = request.form.get("role", "user")

            if not username or not password:
                flash("اسم المستخدم وكلمة المرور مطلوبان.", "danger")
            elif role not in ["admin", "accountant", "sales", "viewer"]:
                flash("الدور غير صحيح.", "danger")
            else:
                try:
                    cur.execute(
                        "INSERT INTO users(username,password,role) VALUES (?,?,?)",
                        (username, generate_password_hash(password), role),
                    )
                    user_id = cur.lastrowid
                    log_action(cur, "create", "user", user_id, f"role={role}")
                    conn.commit()
                    conn.close()
                    flash("تمت إضافة المستخدم بنجاح.", "success")
                    return redirect(url_for("users"))
                except sqlite3.IntegrityError:
                    flash("اسم المستخدم موجود بالفعل.", "danger")

        cur.execute("SELECT id,username,role FROM users ORDER BY id")
        rows = cur.fetchall()
        conn.close()
        return render_template("users.html", rows=rows)

    return users
