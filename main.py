import os
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import Update, InputFile
from telegram.ext import ContextTypes
import yt_dlp
import asyncio
import re
from flask import Flask, render_template_string
from threading import Thread

# إعدادات التطبيق
app = Flask(__name__)

# صفحة ويب أساسية لتجنب إيقاف Replit للتطبيق
@app.route('/')
def home():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Telegram Downloader Bot</title>
        <meta charset="utf-8">
    </head>
    <body>
        <div style="text-align: center; margin-top: 100px;">
            <h1>🤖 بوت التحميل يعمل بنجاح</h1>
            <p>البوت نشط وجاهز لاستقبال الطلبات</p>
            <p>💡 اذهب إلى تيليجرام وابدأ استخدام البوت</p>
        </div>
    </body>
    </html>
    ''')

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# تشغيل خادم الويب في خيط منفصل
Thread(target=run_flask).start()

# إعدادات البوت
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')

# إعدادات التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

class TelegramDownloaderBot:
    def __init__(self):
        self.supported_platforms = {
            'instagram': ['instagram.com'],
            'tiktok': ['tiktok.com', 'vm.tiktok.com'],
            'facebook': ['facebook.com', 'fb.watch']
        }
        
    def validate_url(self, url: str) -> str:
        """التحقق من صحة الرابط وتحديد المنصة"""
        patterns = {
            'instagram': r'(https?://(www\.)?instagram\.com/(p|reel|stories)/[^/]+/?)\S*',
            'tiktok': r'(https?://(www\.)?tiktok\.com/@[^/]+/video/\d+)|(https?://vm\.tiktok\.com/\S+)',
            'facebook': r'(https?://(www\.)?facebook\.com/[^/]+/(videos|reel)/\d+)|(https?://fb\.watch/\S+)'
        }
        
        for platform, pattern in patterns.items():
            if re.match(pattern, url):
                return platform
        return None
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """رسالة الترحيب"""
        welcome_text = """
        🌹 أهلاً وسهلاً بك في بوت التحميل!
        
        📱 **المنصات المدعومة:**
        • إنستقرام (فيديوهات، ريلز، ستوريات)
        • تيك توك (فيديوهات بدون علامة مائية)
        • فيسبوك (فيديوهات وريلز)
        
        💡 **طريقة الاستخدام:**
        فقط أرسل رابط الفيديو وسأقوم بتحميله لك!
        
        مثال:
        `https://www.instagram.com/reel/Cxample/`
        """
        await update.message.reply_text(welcome_text)
    
    async def download_video(self, url: str, platform: str):
        """تحميل الفيديو"""
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': 'downloads/%(title).100s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'extractaudio': False,
            'noplaylist': True,
        }
        
        # إعدادات خاصة للتيك توك
        if platform == 'tiktok':
            ydl_opts['format'] = 'best[ext=mp4]'
        
        try:
            loop = asyncio.get_event_loop()
            
            def sync_download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    filename = ydl.prepare_filename(info)
                    ydl.download([url])
                    return {'filename': filename, 'info': info}
            
            result = await loop.run_in_executor(None, sync_download)
            return result
            
        except Exception as e:
            raise Exception(f'خطأ في التحميل: {str(e)}')
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الرسائل الواردة"""
        message = update.message
        url = message.text.strip()
        
        # التحقق من أن الرسالة تحتوي على رابط
        platform = self.validate_url(url)
        if not platform:
            await message.reply_text("""
            ❌ الرابط غير صالح أو غير مدعوم.
            
            📋 المنصات المدعومة:
            • إنستقرام: فيديوهات، ريلز، ستوريات
            • تيك توك: فيديوهات
            • فيسبوك: فيديوهات، ريلز
            
            💡 مثال للرابط الصحيح:
            `https://www.tiktok.com/@user/video/123456789`
            """)
            return
        
        # إرسال رسالة الانتظار
        wait_msg = await message.reply_text("⏳ جاري التحضير...")
        
        try:
            await wait_msg.edit_text("📥 جاري التحميل من السيرفر...")
            
            # تحميل الفيديو
            result = await self.download_video(url, platform)
            
            await wait_msg.edit_text("🔄 جاري إرسال الفيديو...")
            
            # إرسال الفيديو
            caption = f"🎥 {result['info'].get('title', 'فيديو')}\n📱 المنصة: {platform.upper()}"
            
            with open(result['filename'], 'rb') as video_file:
                await message.reply_video(
                    video=InputFile(video_file),
                    caption=caption,
                    supports_streaming=True
                )
            
            # تنظيف الملف المؤقت
            try:
                os.remove(result['filename'])
            except:
                pass
            
            await wait_msg.delete()
            await message.reply_text("✅ تم التحميل بنجاح! 🎉")
            
        except Exception as e:
            error_msg = f"""
            ❌ حدث خطأ أثناء التحميل
            
            💡 الأسباب المحتملة:
            • الفيديو محمي أو خاص
            • مشكلة في الشبكة
            • حجم الفيديو كبير جداً
            
            🔄 حاول مرة أخرى أو جرب رابط آخر
            """
            await wait_msg.edit_text(error_msg)
            
            # تنظيف الملف في حالة الخطأ
            try:
                if 'result' in locals():
                    os.remove(result['filename'])
            except:
                pass
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الأخطاء"""
        error = context.error
        print(f"حدث خطأ: {error}")
        
        if update and update.message:
            await update.message.reply_text("❌ حدث خطأ غير متوقع. الرجاء المحاولة مرة أخرى.")

async def main():
    """الدالة الرئيسية لتشغيل البوت"""
    # التحقق من وجود التوكن
    if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        print("❌ لم يتم تعيين BOT_TOKEN")
        return
    
    # إنشاء مجلد التحميلات
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    
    # إنشاء تطبيق البوت
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إنشاء كائن البوت
    bot = TelegramDownloaderBot()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    # معالج الأخطاء
    application.add_error_handler(bot.error_handler)
    
    # بدء البوت
    print("🤖 البوت يعمل الآن على Replit...")
    await application.run_polling()

if __name__ == '__main__':
    # تشغيل البوت
    asyncio.run(main())
