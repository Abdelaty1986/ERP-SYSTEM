from __future__ import annotations

from pathlib import Path

import app as app_module


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "static" / "readme" / "html"
APP = app_module.app

SNAPSHOTS = {
    "dashboard.html": "/dashboard",
    "journal.html": "/journal",
    "sales.html": "/sales",
    "purchases.html": "/purchases",
    "trial-balance.html": "/trial-balance",
}


def file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def localize_assets(html: str) -> str:
    static_dir = BASE_DIR / "static"
    html = html.replace('href="/static/style.css"', f'href="{file_uri(static_dir / "style.css")}"')
    html = html.replace('src="/static/uploads/company-logo.jpeg"', f'src="{file_uri(static_dir / "uploads" / "company-logo.jpeg")}"')
    html = html.replace('src="/static/uploads/company-logo.png"', f'src="{file_uri(static_dir / "uploads" / "company-logo.png")}"')
    html = html.replace('href="/static/', f'href="{file_uri(static_dir)}/')
    html = html.replace('src="/static/', f'src="{file_uri(static_dir)}/')
    return html


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with APP.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "admin"
            session["role"] = "admin"
        for file_name, route in SNAPSHOTS.items():
            response = client.get(route)
            if response.status_code >= 400:
                raise RuntimeError(f"Snapshot route failed: {route} -> {response.status_code}")
            html = localize_assets(response.get_data(as_text=True))
            (OUTPUT_DIR / file_name).write_text(html, encoding="utf-8")
            print(f"Wrote {file_name} from {route}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
