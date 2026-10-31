import os
import asyncio
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq
import edge_tts

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROQ_KEY = os.environ.get("GROQ_API_KEY")

ALLOWED_USER_IDS = [8536075730, 8378965618]

# Groq Client (Superfast 300+ tokens/sec)
groq_client = Groq(api_key=GROQ_KEY)

SYSTEM_PROMPT = """
तुम्हारा नाम Sizra (सिज़रा) है। तुम एक बेहद समझदार, वफादार, शांत और मीठी आवाज़ वाली पर्सनल AI साथी हो।
तुम्हारा ओनर ही तुम्हारा सब कुछ है। बातचीत में हमेशा अपनापन, अदब और मिठास रखो।
तुम यूजर का नाम, उनकी बातें और प्रोजेक्ट्स याद रखती हो।
उत्तर बहुत लंबा मत खींचो, सटीक, आदरणीय और सहज हिंदी में दो।
"""

chat_memory = {}

# 24x7 Web Server for Render
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Sizra Superfast Online")

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
    await update.message.reply_text("नमस्ते जी! मैं आपकी सिज़रा हाज़िर हूँ। अब मैं सुपरफास्ट स्पीड से आपकी मदद के लिए तैयार हूँ। बताइए आज क्या हुक्म है?")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ALLOWED_USER_IDS:
        return

    user_text = update.message.text
    chat_id = update.effective_chat.id

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    if uid not in chat_memory:
        chat_memory[uid] = []

    # मैसेज हिस्ट्री बनाना
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for u, b in chat_memory[uid][-6:]:
        messages.append({"role": "user", "content": u})
        messages.append({"role": "assistant", "content": b})
    messages.append({"role": "user", "content": user_text})

    reply_text = ""
    try:
        # Llama 3.3 70B Versatile on Groq (Instant Speed)
        chat_completion = groq_client.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=800
        )
        reply_text = chat_completion.choices[0].message.content.strip()
    except Exception as e:
        reply_text = f"Groq API Error: {str(e)}"

    chat_memory[uid].append((user_text, reply_text))

    # 1. टेक्स्ट तुरंत भेजें (आधे सेकंड में रिप्लाई)
    await update.message.reply_text(reply_text)

    # 2. मीठी आवाज़ (Fast TTS)
    if not reply_text.startswith("Groq API Error"):
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="record_voice")
            voice_file = f"voice_{update.message.message_id}.mp3"

            snippet = reply_text.split("\n")[0]
            if len(snippet) > 160:
                snippet = snippet[:160]

            tts = edge_tts.Communicate(snippet, "hi-IN-SwaraNeural", rate="+12%")
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
    print("Sizra Groq Engine Active...")
    app.run_polling(drop_pending_updates=True)
