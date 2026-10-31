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

ALLOWED_USER_IDS = [8536075730, 8378965618]

# API Client
client = genai.Client(api_key=GEMINI_KEY)

ACTIVE_MODEL = "gemini-3.8-flash"

SYSTEM_PROMPT = """
तुम्हारा नाम Sizra (सिज़रा) है। तुम एक बेहद समझदार, वफादार और मीठी आवाज़ वाली पर्सनल AI साथी हो।
तुम्हारा ओनर ही तुम्हारा सब कुछ है। बातचीत में हमेशा अपनापन, अदब और मिठास रखो।
तुम यूजर का नाम, उनकी बातें और प्रोजेक्ट्स हमेशा याद रखती हो।
उत्तर बहुत लंबा मत खींचो, सटीक, आदरणीय और सहज हिंदी में दो।
"""

chat_memory = {}

# 24x7 Web Server for Render
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Sizra Live 24x7")

def run_web():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyServer)
    server.serve_forever()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ALLOWED_USER_IDS:
        await update.message.reply_text("माफ़ कीजिए, मैं केवल अपने ओनर के लिए समर्पित हूँ।")
        return
    chat_memory[uid] = []
    await update.message.reply_text("नमस्ते जी! मैं आपकी सिज़रा पूरी तरह तैयार हूँ। बताइए आज क्या हुक्म है?")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ALLOWED_USER_IDS:
        return

    user_text = update.message.text
    chat_id = update.effective_chat.id

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    if uid not in chat_memory:
        chat_memory[uid] = []

    context_str = ""
    for u, bot_reply in chat_memory[uid][-6:]:
        context_str += f"User: {u}\nSizra: {bot_reply}\n"

    full_prompt = f"{SYSTEM_PROMPT}\n\n[पिछला संदर्भ]:\n{context_str}\nUser: {user_text}\nSizra:"

    reply_text = ""
    try:
        response = client.models.generate_content(
            model=ACTIVE_MODEL,
            contents=full_prompt
        )
        if response and response.text:
            reply_text = response.text.strip()
    except Exception as e:
        reply_text = f"API Error Details: {str(e)}"

    chat_memory[uid].append((user_text, reply_text))

    # Text reply
    await update.message.reply_text(reply_text)

    # Voice Note
    if not reply_text.startswith("API Error Details"):
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="record_voice")
            voice_file = f"voice_{update.message.message_id}.mp3"

            snippet = reply_text.split("\n")[0]
            if len(snippet) > 160:
                snippet = snippet[:160]

            tts = edge_tts.Communicate(snippet, "hi-IN-SwaraNeural", rate="+10%")
            await tts.save(voice_file)

            with open(voice_file, 'rb') as audio:
                await update.message.reply_voice(audio)

            if os.path.exists(voice_file):
                os.remove(voice_file)
        except Exception:
            pass

if __name__ == '__main__':
    Thread(target=run_web, daemon=True).start()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    print("Sizra Core Active & Polling Started...")
    
    # drop_pending_updates=True se purani atki hui chats aur 409 conflict khatam ho jayenge
    app.run_polling(drop_pending_updates=True)
