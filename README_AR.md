# ERP Developer Control + Test Dashboard Upgrade

انسخ الملفات في أماكنها داخل المشروع، خصوصًا:

- app.py إلى فولدر المشروع الرئيسي
- pro_test.py إلى فولدر المشروع الرئيسي
- templates/developer_control.html
- templates/system_health.html

ثم شغل:

```bash
python -m py_compile app.py pro_test.py
python app.py
```

افتح:

```text
/dev-control
/system-health
```

التعديل يعتبر Redirects أدوات المطور التالية PASS داخل صفحة المطور وداخل pro_test.py:

- /dev/run-migrations
- /dev/run-test
- /dev/deploy
- /dev/import-data
- /dev/backup-now
