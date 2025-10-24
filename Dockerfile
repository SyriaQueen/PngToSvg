# 1. التحديث إلى Debian Bullseye (إصدار مدعوم)
FROM python:3.11-slim-bullseye

# 2. تحديث المستودعات وتثبيت potrace وتنظيف الكاش
RUN apt-get update && \
    apt-get install -y potrace --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# 3. إنشاء دليل العمل داخل الحاوية
WORKDIR /app

# 4. نسخ ملف المتطلبات
COPY requirements.txt .

# 5. تثبيت متطلبات Python
RUN pip install --no-cache-dir -r requirements.txt

# 6. نسخ باقي ملفات التطبيق (app.py والمجلد templates)
COPY . .

# 7. تحديد المنفذ
EXPOSE 5000

# 8. تشغيل التطبيق باستخدام Gunicorn
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 app:app
