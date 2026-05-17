"""
System health helper for the Flask ERP app.
Extended with JARVIS runtime health checks, health score, and service list.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


REQUIRED_TABLES = [
    "accounts", "company_settings", "users", "role_permissions",
    "customers", "suppliers", "products", "journal", "ledger",
    "sales_invoices", "purchase_invoices", "receipt_vouchers", "payment_vouchers",
    "posting_control", "document_sequences", "schema_migrations",
]

HR_OPTIONAL_TABLES = [
    "departments", "employees", "payroll_runs", "payroll_lines",
    "hr_departments", "hr_employees", "hr_payroll_runs", "hr_payroll_lines",
]

# JARVIS runtime paths
JARVIS_CORE_DIR = Path(__file__).resolve().parent / "JARVIS_CORE"
RUNTIME_LOGS_DIR = JARVIS_CORE_DIR / "runtime_logs"
RUNTIME_MEMORY_DIR = JARVIS_CORE_DIR / "runtime_memory"
RUNTIME_CONFIG = JARVIS_CORE_DIR / "runtime_config.json"
RUNTIME_HUD_FILE = RUNTIME_MEMORY_DIR / "runtime_supervision_hud.json"


def _connect(db_path):
    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def _safe_count(cur, table):
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return int(cur.fetchone()[0])
    except sqlite3.Error:
        return None


def _table_exists(cur, table):
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def _check_runtime_dir(dir_path, label):
    """Check if a runtime directory exists and count its files."""
    p = Path(dir_path)
    if not p.exists() or not p.is_dir():
        return {"ok": False, "details": f"{label}: directory not found"}
    try:
        files = [f for f in p.iterdir() if f.is_file()]
        return {"ok": True, "details": f"{label}: {len(files)} files", "count": len(files)}
    except Exception as e:
        return {"ok": False, "details": f"{label}: {e}"}


def _check_runtime_file(file_path, label):
    """Check if a runtime file exists and is readable."""
    p = Path(file_path)
    if not p.exists():
        return {"ok": False, "details": f"{label}: not found"}
    try:
        size_kb = p.stat().st_size / 1024
        return {"ok": True, "details": f"{label}: {size_kb:.1f} KB", "size_kb": round(size_kb, 1)}
    except Exception as e:
        return {"ok": False, "details": f"{label}: {e}"}


def _check_api_endpoint(app, url):
    """Check if a Flask route exists (does not call it)."""
    try:
        rules = [str(r) for r in app.url_map.iter_rules()]
        matched = any(url in r for r in rules)
        return {"ok": matched, "details": url if matched else f"{url}: route not registered"}
    except Exception as e:
        return {"ok": False, "details": str(e)}


def build_system_health(db_path, app, get_migration_status_func):
    """
    Build a comprehensive system health report including ERP database checks,
    Flask routes, JARVIS runtime health, and system resources.

    Returns a dict with:
      - generated_at, overall_ok, overall_label, checks (legacy)
      - status, health_score, warnings, services (new)
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    checks = []
    stats = {}
    services = []
    warnings = []

    # Scoring weights
    SCORE_DB = 25
    SCORE_ROUTES = 10
    SCORE_RUNTIME_DIRS = 15
    SCORE_RUNTIME_FILES = 10
    SCORE_SYSTEM = 20
    SCORE_API = 10
    SCORE_WORKER = 10
    total_possible = SCORE_DB + SCORE_ROUTES + SCORE_RUNTIME_DIRS + SCORE_RUNTIME_FILES + SCORE_SYSTEM + SCORE_API + SCORE_WORKER
    earned = 0

    def add_check(name, ok, details="", level=None):
        if level is None:
            level = "success" if ok else "danger"
        checks.append({"name": name, "ok": ok, "details": details, "level": level})

    def add_service(name, ok, details=""):
        services.append({
            "name": name,
            "status": "online" if ok else "offline",
            "last_check": now,
            "details": details,
        })

    # ---- 1. Database checks (25 pts) ----
    db_ok = os.path.exists(db_path)
    add_check("Database file", db_ok, db_path if db_ok else "database.db not found")
    add_service("Database File", db_ok, db_path if db_ok else "not found")
    if db_ok:
        earned += SCORE_DB * 0.3
        try:
            size_mb = os.path.getsize(db_path) / (1024 * 1024)
            stats["db_size_mb"] = round(size_mb, 2)
            conn = _connect(db_path)
            cur = conn.cursor()

            cur.execute("PRAGMA integrity_check")
            integrity = cur.fetchone()[0]
            integrity_ok = integrity == "ok"
            add_check("SQLite integrity", integrity_ok, integrity)
            if integrity_ok:
                earned += SCORE_DB * 0.3

            missing = [t for t in REQUIRED_TABLES if not _table_exists(cur, t)]
            tables_ok = not missing
            add_check("Required tables", tables_ok,
                      "All tables present" if tables_ok else "Missing: " + ", ".join(missing))
            if tables_ok:
                earned += SCORE_DB * 0.2

            stats["users"] = _safe_count(cur, "users") or 0
            stats["accounts"] = _safe_count(cur, "accounts") or 0
            stats["customers"] = _safe_count(cur, "customers") or 0
            stats["suppliers"] = _safe_count(cur, "suppliers") or 0
            stats["products"] = _safe_count(cur, "products") or 0
            stats["journal_rows"] = _safe_count(cur, "journal") or 0
            stats["employees"] = _safe_count(cur, "employees") or 0

            # Migration check
            try:
                mig = get_migration_status_func(db_path)
                mig_ok = mig.get("pending", 1) == 0
                add_check("Migration status", mig_ok,
                          f"Current {mig.get('current_version','?')} / Latest {mig.get('latest_version','?')}",
                          "success" if mig_ok else "warning")
                if mig_ok:
                    earned += SCORE_DB * 0.2
            except Exception as exc:
                mig = {"rows": [], "pending": "?", "current_version": "?", "latest_version": "?"}
                add_check("Migration status", False, str(exc))

            conn.close()
            db_connect_ok = True
        except Exception as exc:
            mig = {"rows": [], "pending": "?", "current_version": "?", "latest_version": "?"}
            add_check("Database connection", False, str(exc))
            db_connect_ok = False
    else:
        mig = {"rows": [], "pending": "?", "current_version": "?", "latest_version": "?"}
        db_connect_ok = False

    if db_ok and db_connect_ok:
        add_service("Database Engine", True, "SQLite connected")
    else:
        add_service("Database Engine", False, "disconnected or missing")

    # ---- 2. Flask routes (10 pts) ----
    try:
        routes = sorted(str(rule) for rule in app.url_map.iter_rules())
        stats["routes"] = len(routes)
        important_routes = ["/dashboard", "/login", "/jarvis/mobile", "/system-health"]
        missing_routes = [r for r in important_routes if r not in routes]
        routes_ok = not missing_routes
        add_check("Important routes", routes_ok,
                  "All routes present" if routes_ok else "Missing: " + ", ".join(missing_routes))
        if routes_ok:
            earned += SCORE_ROUTES
        add_service("Flask Routes", routes_ok, f"{len(routes)} registered")
    except Exception as e:
        add_check("Important routes", False, str(e))
        routes = []

    # ---- 3. JARVIS Runtime directories (15 pts) ----
    rt_logs = _check_runtime_dir(RUNTIME_LOGS_DIR, "Runtime logs")
    add_check("Runtime logs dir", rt_logs["ok"], rt_logs["details"])
    if rt_logs["ok"]:
        earned += SCORE_RUNTIME_DIRS * 0.5
    add_service("Runtime Logs", rt_logs["ok"], rt_logs.get("details", "unavailable"))

    rt_mem = _check_runtime_dir(RUNTIME_MEMORY_DIR, "Runtime memory")
    add_check("Runtime memory dir", rt_mem["ok"], rt_mem["details"])
    if rt_mem["ok"]:
        earned += SCORE_RUNTIME_DIRS * 0.5
    add_service("Runtime Memory", rt_mem["ok"], rt_mem.get("details", "unavailable"))

    # ---- 4. Key runtime files (10 pts) ----
    rt_config = _check_runtime_file(RUNTIME_CONFIG, "Runtime config")
    add_check("Runtime config", rt_config["ok"], rt_config["details"])
    if rt_config["ok"]:
        earned += SCORE_RUNTIME_FILES * 0.3
    add_service("Runtime Config", rt_config["ok"], rt_config.get("details", "unavailable"))

    rt_hud = _check_runtime_file(RUNTIME_HUD_FILE, "Runtime HUD")
    add_check("Runtime HUD file", rt_hud["ok"], rt_hud["details"])
    if rt_hud["ok"]:
        earned += SCORE_RUNTIME_FILES * 0.3

    # Check for runtime JSON files
    try:
        mem_files = list(RUNTIME_MEMORY_DIR.glob("*.json")) if RUNTIME_MEMORY_DIR.exists() else []
        stats["runtime_memory_files"] = len(mem_files)
        if mem_files:
            earned += SCORE_RUNTIME_FILES * 0.4
    except Exception:
        stats["runtime_memory_files"] = 0

    # ---- 5. System resources (20 pts) ----
    try:
        du = shutil.disk_usage(JARVIS_CORE_DIR.parent if JARVIS_CORE_DIR.exists() else "/")
        free_gb = du.free / (1024**3)
        disk_ok = free_gb > 1.0  # at least 1GB free
        add_check("Disk space", disk_ok, f"{free_gb:.1f} GB free")
        if disk_ok:
            earned += SCORE_SYSTEM * 0.4
        stats["disk_free_gb"] = round(free_gb, 1)
        stats["disk_total_gb"] = round(du.total / (1024**3), 1)
        add_service("Disk", disk_ok, f"{free_gb:.1f} GB free / {du.total//(1024**3)} GB total")
    except Exception as e:
        add_check("Disk space", False, str(e))
        stats["disk_free_gb"] = 0

    try:
        with open("/proc/meminfo") as f:
            meminfo = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().replace(" kB", "")
                    try:
                        meminfo[key] = int(val)
                    except ValueError:
                        meminfo[key] = 0
        mem_total_mb = meminfo.get("MemTotal", 0) / 1024
        mem_avail_mb = meminfo.get("MemAvailable", 0) / 1024
        mem_pct = round((1 - mem_avail_mb / mem_total_mb) * 100, 1) if mem_total_mb > 0 else 0
        ram_ok = mem_pct < 90  # warning if >90% used
        add_check("RAM", ram_ok, f"{mem_pct}% used ({mem_avail_mb:.0f} MB available / {mem_total_mb:.0f} MB total)")
        if ram_ok:
            earned += SCORE_SYSTEM * 0.3
        stats["ram_pct"] = mem_pct
        stats["ram_avail_mb"] = round(mem_avail_mb, 0)
        add_service("RAM", ram_ok, f"{mem_pct}% used")
    except Exception as e:
        add_check("RAM", False, str(e))
        stats["ram_pct"] = 0
        stats["ram_avail_mb"] = 0

    # Check Python process
    try:
        import resource
        proc_mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        stats["process_max_rss_kb"] = proc_mem
        earned += SCORE_SYSTEM * 0.3
    except Exception:
        pass

    # ---- 6. API availability (10 pts) ----
    api_endpoints = [
        "/jarvis/mobile/api/status",
        "/jarvis/mobile/api/runtime/execution-summary",
        "/jarvis/mobile/api/runtime/activity-feed",
        "/jarvis/mobile/api/runtime/insight-snapshot",
        "/jarvis/api/system-health",
        "/jarvis/api/execution/current",
    ]
    api_results = [_check_api_endpoint(app, ep) for ep in api_endpoints]
    api_ok_count = sum(1 for r in api_results if r["ok"])
    api_all_ok = api_ok_count == len(api_endpoints)
    add_check("API endpoints", api_all_ok, f"{api_ok_count}/{len(api_endpoints)} available")
    if api_all_ok:
        earned += SCORE_API
    else:
        earned += SCORE_API * (api_ok_count / len(api_endpoints))
    add_service("API Layer", api_all_ok, f"{api_ok_count}/{len(api_endpoints)} endpoints reachable")
    stats["api_endpoints_ok"] = api_ok_count
    stats["api_endpoints_total"] = len(api_endpoints)

    # ---- 7. Worker & Scheduler state (10 pts) ----
    try:
        worker_states_path = RUNTIME_MEMORY_DIR / "runtime_worker_state.json"
        if worker_states_path.exists():
            ws = json.loads(worker_states_path.read_text(encoding="utf-8"))
            worker_ok = ws.get("status") in ("idle", "running", "completed")
            add_check("Worker state", worker_ok, ws.get("status", "unknown"))
            if worker_ok:
                earned += SCORE_WORKER * 0.5
        else:
            add_check("Worker state", True, "No worker state file (new system)")
            earned += SCORE_WORKER * 0.5
    except Exception as e:
        add_check("Worker state", False, str(e))

    try:
        sched_path = RUNTIME_MEMORY_DIR / "auto_scheduler_state.json"
        if sched_path.exists():
            ss = json.loads(sched_path.read_text(encoding="utf-8"))
            sched_ok = ss.get("status") in ("idle", "starting", "completed")
            add_check("Scheduler state", sched_ok, ss.get("status", "unknown"))
            if sched_ok:
                earned += SCORE_WORKER * 0.3
        else:
            add_check("Scheduler state", True, "No scheduler file (new system)")
            earned += SCORE_WORKER * 0.3
    except Exception as e:
        add_check("Scheduler state", False, str(e))

    try:
        voice_path = RUNTIME_MEMORY_DIR / "voice_runtime_hud.json"
        if voice_path.exists():
            vs = json.loads(voice_path.read_text(encoding="utf-8"))
            voice_ok = vs.get("voice_enabled") is True or vs.get("status") in ("online", "listening")
            add_check("Voice runtime", voice_ok, "enabled" if voice_ok else "disabled")
            if voice_ok:
                earned += SCORE_WORKER * 0.2
        else:
            add_check("Voice runtime", True, "No voice state file (runtime default)")
            earned += SCORE_WORKER * 0.2
    except Exception as e:
        add_check("Voice runtime", False, str(e))

    add_service("Runtime Worker", True, "Managed via runtime API")
    add_service("Scheduler", True, "Managed via runtime API")
    add_service("Voice Runtime", True, "Managed via runtime API")

    # ---- Compute final status ----
    health_score = min(100, round(earned / total_possible * 100)) if total_possible > 0 else 0

    failed_checks = [c for c in checks if not c["ok"]]
    if failed_checks:
        for c in failed_checks[:5]:
            warnings.append(f"{c['name']}: {c['details']}")

    if health_score >= 80 and len(failed_checks) == 0:
        status = "online"
        label = "Healthy"
    elif health_score >= 50:
        status = "warning"
        label = "Needs attention"
    elif health_score >= 20:
        status = "degraded"
        label = "Degraded"
    else:
        status = "offline"
        label = "Critical"

    return {
        # Legacy keys (for system_health.html template)
        "generated_at": now,
        "overall_ok": health_score >= 80,
        "overall_label": label,
        "checks": checks,
        "stats": stats,
        "migration_status": mig,
        "routes": routes[:250],
        # New enriched keys
        "status": status,
        "health_score": health_score,
        "warnings": warnings,
        "services": services,
    }
