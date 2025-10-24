# استخدام صورة Python خفيفة تعتمد على نظام Debian (للسماح بتثبيت potrace باستخدام apt)
FROM python:3.11-slim-buster

# تحديث قوائم الحزم وتثبيت أداة potrace لتحويل الصور إلى SVG
# --no-install-recommends يقلل من حجم الصورة
RUN apt-get update && \
    apt-get install -y potrace --no-install-recommends && \
    # تنظيف الكاش لتقليل حجم الصورة النهائية
    rm -rf /var/lib/apt/lists/*

# إنشاء دليل العمل داخل الحاوية
WORKDIR /app

# نسخ ملف المتطلبات أولاً للاستفادة من الـ caching في Docker
COPY requirements.txt .

# تثبيت متطلبات Python
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات التطبيق (app.py والمجلد templates)
COPY . .

# تحديد المنفذ الافتراضي (Render سيستخدم متغير البيئة PORT)
EXPOSE 5000

# تشغيل التطبيق باستخدام Gunicorn
# Gunicorn هو خادم ويب للإنتاج وسيعمل على المنفذ $PORT الذي تحدده Render تلقائياً
# app:app تعني: ابحث عن متغير Flask المسمى 'app' داخل الملف 'app.py'
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 app:app
