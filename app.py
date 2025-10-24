import io
import os
import tempfile
import subprocess 
import zipfile
from flask import Flask, request, send_file, render_template
from PIL import Image

app = Flask(__name__)

# --- دالة مساعدة لمعالجة صورة واحدة ---
def process_image(image_file, output_format):
    image_file.seek(0)
    
    # --- معالجة SVG (التركيز على الشفافية) ---
    if output_format == 'svg':
        
        # 1. التحقق من صيغة الملف والشفافية
        try:
            img = Image.open(image_file)
        except Exception:
            raise Exception("الملف المدخل ليس صورة صالحة.")
            
        # التحقق من أن الملف PNG ولديه قناة ألفا (RGBA)
        if img.format != 'PNG' or img.mode != 'RGBA':
            raise Exception("الرجاء اختيار صورة PNG شفافة فقط للتحويل إلى SVG.")
        
        temp_input_path = None
        temp_output_path = None
        
        try:
            # 2. استخراج قناة ألفا (القناة المسؤولة عن الشفافية)
            # هذه هي القناة التي تحدد حدود الكائن (غير الشفاف)
            alpha_mask = img.split()[3]
            
            # 3. تحويل قناع ألفا إلى صورة ثنائية (أسود وأبيض) لـ Potrace
            # حيث يكون الكائن غير الشفاف أسود، والخلفية الشفافة أبيض
            img_bw = alpha_mask.point(lambda p: 0 if p > 0 else 255, '1')

            # 4. حفظ الصورة النقطية الثنائية مؤقتاً
            with tempfile.NamedTemporaryFile(suffix='.bmp', delete=False) as temp_input:
                img_bw.save(temp_input, format='BMP') 
                temp_input_path = temp_input.name
                
            temp_output_path = temp_input_path.replace('.bmp', '.svg')

            # 5. تنفيذ أمر Potrace
            command = ['potrace', '-s', temp_input_path, '-o', temp_output_path]
            subprocess.run(command, check=True, capture_output=True, text=True)
            
            # 6. قراءة ملف SVG وإرجاع المخزن المؤقت
            with open(temp_output_path, 'rb') as svg_file:
                buffer = io.BytesIO(svg_file.read())
            return buffer

        except subprocess.CalledProcessError as e:
            raise Exception(f'فشل Potrace في التحويل: {e.stderr}')
        except FileNotFoundError:
            raise Exception('خطأ: أداة Potrace غير مثبتة.')
        except Exception as e:
            raise Exception(f'فشل عام في معالجة SVG: {e}')
        finally:
            # 7. تنظيف الملفات المؤقتة
            if temp_input_path and os.path.exists(temp_input_path):
                os.remove(temp_input_path)
            if temp_output_path and os.path.exists(temp_output_path):
                os.remove(temp_output_path)
    
    # --- تعطيل الصيغ النقطية الأخرى ---
    else:
        # لن يتم الوصول إلى هنا إلا إذا تم تغيير قيمة 'format-select' في الواجهة
        raise Exception("هذا التطبيق يدعم فقط التحويل إلى SVG من PNG شفافة.")


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert_image_route():
    # استخدام getlist للحصول على كل الملفات
    image_files = request.files.getlist('image')
    # يجب تثبيت الإخراج على 'svg' بغض النظر عما يختاره المستخدم للتركيز على الوظيفة المطلوبة
    output_format = 'svg'

    if not image_files or not image_files[0].filename:
        return 'لم يتم تحميل أي ملفات.', 400

    # --- معالجة ملف واحد ---
    if len(image_files) == 1:
        try:
            image_file = image_files[0]
            download_name = f"converted-01.{output_format}"
            
            buffer = process_image(image_file, output_format)
            
            return send_file(
                buffer,
                mimetype='image/svg+xml', # MIME Type الصحيح لـ SVG
                as_attachment=True,
                download_name=download_name
            )
        except Exception as e:
            return str(e), 500

    # --- معالجة أكثر من ملف (إنشاء ZIP) ---
    else:
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for index, image_file in enumerate(image_files):
                filename = f"{str(index + 1).zfill(2)}.{output_format}"
                
                try:
                    converted_buffer = process_image(image_file, output_format)
                    zip_file.writestr(filename, converted_buffer.getvalue())
                except Exception as e:
                    print(f"فشل تحويل الملف {image_file.filename}: {e}")
                    # يمكن إضافة ملف نصي إلى ZIP يوضح الملفات التي فشلت
                    zip_file.writestr(f"error_{str(index + 1).zfill(2)}.txt", str(e))
                    
        zip_buffer.seek(0)
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='converted_svgs.zip'
        )
