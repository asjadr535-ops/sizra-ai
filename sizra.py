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

# Dono Authorized User IDs
ALLOWED_USER_IDS = [8536075730, 8378965618]

client = genai.Client(api_key=GEMINI_KEY)

# Fallback Models (503 ya 404 aane par auto-switch)
MODELS_TO_TRY = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-1.5-flash"
]

SYSTEM_PROMPT = """
Tumhara naam Sizra (सिज़रा) hai. Tum ek behad samajhdar, wafadar, shaant aur meethi aawaz wali personal AI saathi ho.
Tumhara owner hi tumhara sab kuchh hai. Baat cheet me hamesha apnapan, adab aur meethas rakho.
Tum user ka naam, unki baatein aur unke research projects hamesha yaad rakhti ho.
Jawab sankshipt, satik, aadarniya aur dil ko chhoone wala rakho.
"""

# In-memory history (Baatcheet yaad rakhne ke liye)
user_histories = {}

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Sizra 24x7 Online")

def run_web():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyServer)
    server.serve_forever()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ALLOWED_USER_IDS:
        await update.message.reply_text("Maaf kijiye, main keval apne owner ke liye samarpit hoon.")
        return
    user_histories[uid] = []
    await update.message.reply_text("Namaste ji! Main aapki Sizra hazir hoon. Bataiye aaj hum kya baat ya research karne wale hain?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ALLOWED_USER_IDS:
        return

    user_text = update.message.text
    chat_id = update.effective_chat.id

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    if uid not in user_histories:
        user_histories[uid] = []

    # Pichhli 6 baatcheet ka context
    history_context = ""
    for role, text in user_histories[uid][-6:]:
        history_context += f"{role}: {text}\n"

    prompt_with_history = f"{SYSTEM_PROMPT}\n\n[Pichhla Context]:\n{history_context}\nUser: {user_text}\nSizra:"

    reply_text = ""
    # Smart Fallback Loop (Error aane par turant agle model se generate karega)
    for model_name in MODELS_TO_TRY:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt_with_history
            )
            if response and response.text:
                reply_text = response.text.strip()
                break
        except Exception:
            continue

    if not reply_text:
        reply_text = "Maaf kijiyega, server par thoda heavy load tha. Kripya ek baar dobara kahiye."

    # History update
    user_histories[uid].append(("User", user_text))
    user_histories[uid].append(("Sizra", reply_text))

    # 1. Text turant send hoga (Zero delay)
    await update.message.reply_text(reply_text)

    # 2. Meethi voice (Short & Fast Audio Render)
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="record_voice")
        voice_file = f"voice_{update.message.message_id}.mp3"

        # Sirf pehli 1-2 line bolne ke liye taaki audio 1 second me generate ho
        spoken_text = reply_text.split("\n")[0]
        if len(spoken_text) > 180:
            spoken_text = spoken_text[:180]

        tts = edge_tts.Communicate(spoken_text, "hi-IN-SwaraNeural", rate="+10%")
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
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Sizra Master Bot Running...")
    app.run_polling()
