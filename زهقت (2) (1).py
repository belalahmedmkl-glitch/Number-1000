import os
import csv
import re
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# إعداد التسجيل (Logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ضع التوكن الخاص بك هنا أو استخدم متغير بيئة
TOKEN = "8228431332:AAHOnUVvQDvJ81Gm34nn11Zn3D1j4eCLt9E"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك! أنا بوت معالجة ملفات الأرقام.\n"
        "أرسل لي ملف CSV وسأقوم بتصنيف الأرقام (8 خانات فأكثر) حسب العمود الثاني وإرسالها لك في ملفات نصية."
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    
    # التأكد من أن الملف هو CSV
    if not document.file_name.lower().endswith('.csv'):
        await update.message.reply_text("عذراً، يرجى إرسال ملف بصيغة CSV فقط.")
        return

    status_message = await update.message.reply_text("جاري تحميل ومعالجة الملف... يرجى الانتظار.")
    
    # إنشاء مجلد مؤقت للمعالجة
    user_id = update.message.from_user.id
    process_dir = f"process_{user_id}"
    output_dir = os.path.join(process_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    
    file_path = os.path.join(process_dir, document.file_name)
    
    try:
        # تحميل الملف
        new_file = await context.bot.get_file(document.file_id)
        await new_file.download_to_drive(file_path)
        
        classified_data = {}
        
        # معالجة الملف
        with open(file_path, mode='r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f)
            next(reader, None)  # تخطي العنوان
            
            for row in reader:
                if len(row) < 2:
                    continue
                
                category_name = row[1].strip()
                if not category_name:
                    category_name = "Unknown_Category"
                
                # استخراج الأرقام من الصف بالكامل
                row_content = " ".join(row)
                all_digit_sequences = re.findall(r'\d+', row_content)
                
                if category_name not in classified_data:
                    classified_data[category_name] = set()
                
                for num in all_digit_sequences:
                    if len(num) >= 8:
                        classified_data[category_name].add(num)

        # إعداد رينجات الأرقام
        def create_number_ranges(numbers_list):
            """تقسم الأرقام إلى رينجات (1,000 رقم لكل رينج)"""
            ranges = []
            for i in range(0, len(numbers_list), 1000):
                chunk = numbers_list[i:i + 1000]
                ranges.append(chunk)
            return ranges
        
        # إنشاء وإرسال الملفات النصية
        files_sent = 0
        for category, numbers in classified_data.items():
            if not numbers:
                continue
                
            # ترتيب الأرقام
            sorted_numbers = sorted(list(numbers))
            
            # تقسيم الأرقام إلى رينجات (مجموعات)
            number_ranges = create_number_ranges(sorted_numbers)
            
            # إنشاء ملف لكل رينج
            for idx, number_range in enumerate(number_ranges):
                # تسمية الملف: الفئة_الجزء
                safe_category = "".join([c for c in category if c.isalnum() or c in (' ', '-', '_')]).strip()
                
                if len(number_ranges) > 1:
                    txt_filename = f"{safe_category}_الجزء_{idx+1}.txt"
                else:
                    txt_filename = f"{safe_category}.txt"
                
                txt_path = os.path.join(output_dir, txt_filename)
                
                # كتابة الأرقام في الملف
                with open(txt_path, mode='w', encoding='utf-8') as f:
                    for number in number_range:
                        f.write(number + '\n')
                
                # إرسال الملف
                try:
                    await update.message.reply_document(
                        document=open(txt_path, 'rb'),
                        caption=f"الفئة: {category}\nعدد الأرقام: {len(number_range)}"
                    )
                    files_sent += 1
                    
                    # حذف الملف بعد الإرسال لتحرير المساحة
                    os.remove(txt_path)
                    
                except Exception as send_error:
                    logging.error(f"خطأ في إرسال الملف {txt_filename}: {send_error}")
        
        # إرسال ملخص
        if files_sent > 0:
            summary_message = f"✅ تم الانتهاء من المعالجة!\n"
            summary_message += f"📊 عدد الفئات: {len(classified_data)}\n"
            total_numbers = sum(len(numbers) for numbers in classified_data.values())
            summary_message += f"🔢 إجمالي الأرقام: {total_numbers}\n"
            summary_message += f"📁 عدد الملفات المرسلة: {files_sent}"
            
            await update.message.reply_text(summary_message)
        else:
            await update.message.reply_text("⚠️ لم يتم العثور على أرقام تطابق الشروط في الملف.")

    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text(f"حدث خطأ أثناء المعالجة: {str(e)}")
    
    finally:
        # تنظيف الملفات المؤقتة
        import shutil
        if os.path.exists(process_dir):
            shutil.rmtree(process_dir)
        await status_message.delete()

if __name__ == '__main__':
    if TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("خطأ: يرجى وضع Bot Token الخاص بك في الكود.")
    else:
        application = Application.builder().token(TOKEN).build()
        
        start_handler = CommandHandler('start', start)
        doc_handler = MessageHandler(filters.Document.ALL & ~filters.COMMAND, handle_document)
        
        application.add_handler(start_handler)
        application.add_handler(doc_handler)
        
        print("البوت يعمل الآن...")
        application.run_polling()