import io
import os
import tempfile
import subprocess 
import zipfile # لاستيراد مكتبة الـ ZIP
from flask import Flask, request, send_file, render_template
from PIL import Image

app = Flask(__name__)

# --- دالة مساعدة لمعالجة صورة واحدة ---
# هذه الدالة تحتوي على كل المنطق الذي كان في دالة convert_image سابقاً
# ولكنها الآن تُرجع المخزن المؤقت (buffer) بدلاً من استجابة Flask
def process_image(image_file, output_format):
    image_file.seek(0)
    
    # --- معالجة SVG (Potrace) ---
    if output_format == 'svg':
        temp_input_path = None
        temp_output_path = None
        try:
            img = Image.open(image_file)
            
            # 1. المعالجة الذكية للشفافية والألوان (الحل الصحيح)
            if img.mode in ('RGBA', 'LA'):
                img_bw = Image.new('L', img.size, 255)
                black_fill = Image.new('L', img.size, 0)
                alpha_mask = img.split()[-1]
                img_bw.paste(black_fill, mask=alpha_mask)
            else:
                img_bw = img.convert('L')
                img_bw = img_bw.point(lambda p: 0 if p < 128 else 255, '1') 

            # 2. حفظ الصورة النقطية الثنائية مؤقتاً
            with tempfile.NamedTemporaryFile(suffix='.bmp', delete=False) as temp_input:
                img_bw.save(temp_input, format='BMP') 
                temp_input_path = temp_input.name
                
            temp_output_path = temp_input_path.replace('.bmp', '.svg')

            # 3. تنفيذ أمر Potrace
            command = ['potrace', '-s', temp_input_path, '-o', temp_output_path]
            subprocess.run(command, check=True, capture_output=True, text=True)
            
            # 4. قراءة ملف SVG وإرساله
            with open(temp_output_path, 'rb') as svg_file:
                buffer = io.BytesIO(svg_file.read())
            return buffer

        except subprocess.CalledProcessError as e:
            raise Exception(f'فشل Potrace في التحويل: {e.stderr}')
        except FileNotFoundError:
            raise Exception('خطأ: أداة Potrace غير مثبتة. (على Termux: pkg install potrace)')
        except Exception as e:
            raise Exception(f'فشل عام في معالجة SVG: {e}')
        finally:
            # 5. تنظيف الملفات المؤقتة
            if temp_input_path and os.path.exists(temp_input_path):
                os.remove(temp_input_path)
            if temp_output_path and os.path.exists(temp_output_path):
                os.remove(temp_output_path)
    
    # --- معالجة الصيغ النقطية الأخرى (PIL) ---
    else:
        try:
            img = Image.open(image_file)
            
            if output_format in ['jpeg', 'jpg'] and img.mode == 'RGBA':
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
            
            buffer = io.BytesIO()
            save_format = 'jpeg' if output_format == 'jpg' else output_format
            
            img.save(buffer, format=save_format)
            buffer.seek(0)
            return buffer
        except Exception as e:
            raise Exception(f'فشل في تحويل الصورة النقطية: {e}')


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert_image_route():
    # استخدام getlist للحصول على كل الملفات
    image_files = request.files.getlist('image')
    output_format = request.form.get('format', 'png').lower()

    if not image_files or not image_files[0].filename:
        return 'لم يتم تحميل أي ملفات.', 400

    # --- معالجة ملف واحد ---
    if len(image_files) == 1:
        try:
            image_file = image_files[0]
            # الترقيم يبدأ من 01
            download_name = f"01.{output_format}"
            
            buffer = process_image(image_file, output_format)
            
            return send_file(
                buffer,
                mimetype=f'image/{output_format}',
                as_attachment=True,
                download_name=download_name
            )
        except Exception as e:
            return str(e), 500

    # --- معالجة أكثر من ملف (إنشاء ZIP) ---
    else:
        # إنشاء ملف ZIP في الذاكرة
        zip_buffer = io.BytesIO()
        
        # 'w' = وضع الكتابة
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # التكرار على الملفات مع عداد مرقم
            for index, image_file in enumerate(image_files):
                # الترقيم: 01, 02, 03, ...
                filename = f"{str(index + 1).zfill(2)}.{output_format}"
                
                try:
                    # تحويل الصورة
                    converted_buffer = process_image(image_file, output_format)
                    
                    # كتابة بيانات الصورة المحولة إلى ملف ZIP
                    zip_file.writestr(filename, converted_buffer.getvalue())
                except Exception as e:
                    # إذا فشل ملف واحد، يمكننا تسجيل الخطأ والمتابعة
                    print(f"فشل تحويل الملف {image_file.filename}: {e}")
                    # يمكنك إضافة رسالة خطأ للمستخدم هنا إذا أردت
                    
        zip_buffer.seek(0)
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='converted_images.zip'
        )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
