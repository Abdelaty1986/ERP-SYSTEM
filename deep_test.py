import os
import re
import traceback
from werkzeug.routing import BuildError

from app import app


TEMPLATES_DIR = "templates"


def collect_template_endpoints():
    endpoints = set()
    pattern = re.compile(r"url_for\(['\"]([^'\"]+)['\"]")

    for root, dirs, files in os.walk(TEMPLATES_DIR):
        for file in files:
            if file.endswith((".html", ".jinja", ".jinja2")):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    matches = pattern.findall(content)
                    endpoints.update(matches)

    return endpoints


def main():
    errors = []

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
    print("CHECK ROUTES RESPONSE")
    print("=" * 60)

    client = app.test_client()

    for rule in app.url_map.iter_rules():
        if "GET" not in rule.methods:
            continue

        if rule.arguments:
            continue

        url = rule.rule

        try:
            response = client.get(url, follow_redirects=False)

            if response.status_code >= 500:
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
    print("FINAL RESULT")
    print("=" * 60)

    if errors:
        print("FAILED ❌")
        for err in errors:
            print("-", err)
    else:
        print("PASSED ✅")


if __name__ == "__main__":
    main()