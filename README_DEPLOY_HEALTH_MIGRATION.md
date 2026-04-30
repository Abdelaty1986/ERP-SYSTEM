# ERP Deployment Package

## Files included

- `app.py`  
  نسخة app بعد ربط Migration و System Health Dashboard.

- `migrations.py`  
  نظام تحديث قاعدة البيانات بدون حذف الداتا.

- `system_health.py`  
  كود فحص صحة النظام.

- `templates/system_health.html`  
  صفحة لوحة صحة النظام.

- `deploy.sh`  
  سكريبت نشر تلقائي من GitHub للسيرفر.

## How to install

1. خذ نسخة احتياطية من المشروع و `database.db`.
2. انسخ الملفات داخل فولدر المشروع.
3. على السيرفر شغل:
   ```bash
   python3 migrations.py
   ```
4. شغل البرنامج.
5. افتح:
   `/system-health`

## Auto deploy

من فولدر المشروع على السيرفر:

```bash
bash deploy.sh
```

ولو على PythonAnywhere وتريد reload تلقائي:

```bash
PA_WSGI_FILE=/var/www/abdelaty1986_pythonanywhere_com_wsgi.py bash deploy.sh
```

## Benefit

السكريبت يقلل الأخطاء بعد كل تحديث:
- يسحب آخر نسخة من GitHub
- يشغل migrations
- يشغل Ultimate Test لو موجود
- يسجل عملية النشر
- يساعدك تعرف هل النسخة الجديدة سليمة قبل العميل
