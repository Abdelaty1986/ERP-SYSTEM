import os
import re
import traceback
from werkzeug.routing import BuildError

from app import app


TEMPLATES_DIR = "templates"

LOGIN_URL = "/login"
TEST_USERNAME = "hany"
TEST_PASSWORD = "1986"

# Routes that intentionally redirect and should not break the test
ALLOWED_REDIRECTS = {
    "/",
    "/purchases/multi",
}

# Do not test logout during the authenticated route scan, because it clears the session
SKIP_URLS = {
    "/logout",
}

SKIP_ENDPOINTS = {
    "static",
}


def collect_template_endpoints():
    endpoints = set()
    pattern = re.compile(r"url_for\(['\"]([^'\"]+)['\"]")

    if not os.path.isdir(TEMPLATES_DIR):
        return endpoints

    for root, dirs, files in os.walk(TEMPLATES_DIR):
        for file in files:
            if file.endswith((".html", ".jinja", ".jinja2")):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    endpoints.update(pattern.findall(content))

    return endpoints


def login(client):
    response = client.post(
        LOGIN_URL,
        data={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
        },
        follow_redirects=False,
    )

    with client.session_transaction() as sess:
        if "user_id" in sess:
            return True, "Login OK"

    return False, f"Login failed: status={response.status_code}"


def main():
    errors = []
    warnings = []

    print("=" * 60)
    print("AVAILABLE ENDPOINTS")
    print("=" * 60)

    real_endpoints = set(app.view_functions.keys())

    for endpoint in sorted(real_endpoints):
        print(endpoint)

    print("\n" + "=" * 60)
    print("CHECK TEMPLATE url_for ENDPOINTS")
    print("=" * 60)

    template_endpoints = collect_template_endpoints()

    for endpoint in sorted(template_endpoints):
        if endpoint not in real_endpoints:
            msg = f"Missing endpoint in templates: {endpoint}"
            print("❌", msg)
            errors.append(msg)
        else:
            print("✅", endpoint)

    print("\n" + "=" * 60)
    print("LOGIN TEST")
    print("=" * 60)

    client = app.test_client()
    ok, login_msg = login(client)

    if ok:
        print("✅", login_msg)
    else:
        print("❌", login_msg)
        errors.append(login_msg)

    print("\n" + "=" * 60)
    print("CHECK ROUTES RESPONSE AFTER LOGIN")
    print("=" * 60)

    if ok:
        for rule in app.url_map.iter_rules():
            endpoint = rule.endpoint
            url = rule.rule

            if endpoint in SKIP_ENDPOINTS:
                continue

            if url in SKIP_URLS:
                print(f"⚠️  SKIP {url} -> clears session")
                warnings.append(f"Skipped session-clearing route: {url}")
                continue

            if "GET" not in rule.methods:
                continue

            if rule.arguments:
                print(f"⚠️  SKIP {url} -> needs values {sorted(rule.arguments)}")
                warnings.append(f"Skipped dynamic route: {url}")
                continue

            try:
                response = client.get(url, follow_redirects=False)

                if response.status_code >= 500:
                    msg = f"Route {url} returned {response.status_code}"
                    print("❌", msg)
                    errors.append(msg)

                elif response.status_code in (301, 302, 303, 307, 308):
                    if url in ALLOWED_REDIRECTS:
                        location = response.headers.get("Location", "")
                        print(f"✅ {url} -> {response.status_code} allowed redirect to {location}")
                    else:
                        location = response.headers.get("Location", "")
                        msg = f"Route {url} redirected after login -> {response.status_code} Location: {location}"
                        print("❌", msg)
                        errors.append(msg)

                elif response.status_code >= 400:
                    msg = f"Route {url} returned {response.status_code}"
                    print("❌", msg)
                    errors.append(msg)

                else:
                    print(f"✅ {url} -> {response.status_code}")

            except BuildError as e:
                msg = f"BuildError in route {url}: {e}"
                print("❌", msg)
                errors.append(msg)

            except Exception as e:
                msg = f"Exception in route {url}: {e}"
                print("❌", msg)
                traceback.print_exc()
                errors.append(msg)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    print(f"Errors: {len(errors)}")
    print(f"Warnings: {len(warnings)}")

    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print("-", warning)

    print("\n" + "=" * 60)
    print("FINAL RESULT")
    print("=" * 60)

    if errors:
        print("FAILED ❌")
        for err in errors:
            print("-", err)
        raise SystemExit(1)
    else:
        print("PASSED ✅")


if __name__ == "__main__":
    main()
