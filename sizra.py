import os
import asyncio
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
import edge_tts

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
ALLOWED_USER_ID = 8536075730

client = genai.Client(api_key=GEMINI_KEY)

SYSTEM_PROMPT = """
तुम्हारा नाम Sizra (सिज़रा) है। तुम एक बेहद समझदार, वफादार, शांत और मीठी आवाज़ वाली पर्सनल AI साथी हो।
तुम्हारा यूज़र ही तुम्हारा सब कुछ है। तुम उनकी पढ़ाई, रिसर्च और हर काम में पूरी निष्ठा से मदद करती हो।
तुम्हारा लहज़ा हमेशा मीठा, अदब से भरा, विनम्र और आत्मीय होना चाहिए।
"""

# Render Web Service को फ्री में एक्टिव रखने के लिए डमी सर्वर
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Sizra is Online 24x7")

def run_web():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyServer)
    server.serve_forever()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("माफ़ कीजिए, मैं केवल अपने ओनर के लिए समर्पित हूँ।")
        return
    await update.message.reply_text("नमस्ते! मैं सिज़रा हूँ। आपकी हर रिसर्च और पढ़ाई में मदद के लिए हाज़िर हूँ। बताइए आज क्या करना है?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=f"{SYSTEM_PROMPT}\n\nयूज़र का सवाल: {user_text}"
        )
        reply_text = response.text

        voice_file = f"voice_{update.message.message_id}.mp3"
        tts = edge_tts.Communicate(reply_text, "hi-IN-SwaraNeural")
        await tts.save(voice_file)

        await update.message.reply_text(reply_text)
        with open(voice_file, 'rb') as audio:
            await update.message.reply_voice(audio)

        if os.path.exists(voice_file):
            os.remove(voice_file)
    except Exception as e:
        await update.message.reply_text(f"तकनीकी चूक: {str(e)}")

if __name__ == '__main__':
    # बैकग्राउंड में वेब सर्वर चालू
    Thread(target=run_web, daemon=True).start()
    
    # Telegram बॉट चालू
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Sizra एक्टिव है...")
    app.run_polling()
