from app import app

# 🔴 روابط ممنوعة (علشان الأمان)
SKIP_KEYWORDS = [
    "/logout",
    "/delete",
    "/cancel",
    "/edit",
    "/toggle",
    "/restore",
    "/backup",
    "/import",
]

def should_skip(route):
    return any(word in route.lower() for word in SKIP_KEYWORDS)

def build_url(rule):
    url = str(rule)

    # تجاهل الروابط اللي فيها متغيرات
    if "<" in url or ">" in url:
        return None

    return url

def main():
    print("=" * 60)
    print("🚀 بدء اختبار شاشات وتقارير Ledger X")
    print("=" * 60)

    passed = []
    failed = []
    skipped = []

    client = app.test_client()

    # 🔐 تسجيل دخول تلقائي (عدّل الباسورد هنا)
    users = [
        ("hany", "1234"),     # 👈 غيّر الباسورد
        ("hazem", "1234"),    # 👈 غيّر الباسورد
    ]

    logged_in = False

    for u, p in users:
        resp = client.post("/login", data={
            "username": u,
            "password": p
        }, follow_redirects=True)

        if resp.status_code == 200:
            print(f"✅ تم تسجيل الدخول بـ {u}")
            logged_in = True
            break

    if not logged_in:
        print("❌ فشل تسجيل الدخول بكل اليوزرز")
        return

    # 🧪 اختبار كل الروابط
    for rule in app.url_map.iter_rules():
        methods = rule.methods or []

        if "GET" not in methods:
            skipped.append((str(rule), "ليست GET"))
            continue

        url = build_url(rule)

        if not url:
            skipped.append((str(rule), "تحتاج ID"))
            continue

        if should_skip(url):
            skipped.append((url, "رابط خطر"))
            continue

        try:
            response = client.get(url, follow_redirects=True)

            if response.status_code >= 500:
                failed.append((url, response.status_code))
                print(f"❌ FAIL {response.status_code} -> {url}")
            else:
                passed.append((url, response.status_code))
                print(f"✅ OK {response.status_code} -> {url}")

        except Exception as e:
            failed.append((url, str(e)))
            print(f"❌ ERROR -> {url}")
            print(e)

    # 📊 النتيجة
    print("\n" + "=" * 60)
    print("📊 النتيجة النهائية")
    print("=" * 60)

    print(f"✅ ناجح: {len(passed)}")
    print(f"❌ فشل: {len(failed)}")
    print(f"⏭️ متخطي: {len(skipped)}")

    if failed:
        print("\n🔥 الأخطاء:")
        for url, error in failed:
            print(f"- {url} => {error}")

    print("\n🎯 تم الاختبار بالكامل")

if __name__ == "__main__":
    main()