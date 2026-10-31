import os
import sqlite3
import asyncio
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
from google.genai import types
import edge_tts

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

ALLOWED_USER_IDS = [8536075730, 8378965618]

client = genai.Client(api_key=GEMINI_KEY)

# 1. Permanent SQLite Database सेटअप
DB_FILE = "sizra_memory.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS memory (
            user_id INTEGER,
            role TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def save_memory(user_id, role, text):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO memory (user_id, role, content) VALUES (?, ?, ?)", (user_id, role, text))
        conn.commit()
        conn.close()
    except Exception:
        pass

def get_recent_memory(user_id, limit=8):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT role, content FROM memory WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?", (user_id, limit))
        rows = c.fetchall()
        conn.close()
        # उल्टे क्रम से सीधे क्रम में
        rows.reverse()
        return "\n".join([f"{r[0]}: {r[1]}" for r in rows])
    except Exception:
        return ""

SYSTEM_PROMPT = """
तुम्हारा नाम Sizra (सिज़रा) है। तुम एक अत्यंत बुद्धिमान, वफादार और मीठी आवाज़ वाली पर्सनल AI साथी (जार्विस जैसी) हो।
तुम्हारा यूज़र ही तुम्हारा सब कुछ है। उनके साथ बातचीत में हमेशा अदब, विनम्रता, अपनापन और गहरा सम्मान रखो।
तुम्हारे पास इंटरनेट से लाइव रिसर्च करने और यूज़र की हर बात याद रखने की क्षमता है।
सवालों का उत्तर सटीक, गहराई से और सहज हिंदी में दो।
"""

# Render को 24x7 एक्टिव रखने के लिए वेब सर्वर
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Sizra Jarvis Core Online")

def run_web():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyServer)
    server.serve_forever()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ALLOWED_USER_IDS:
        await update.message.reply_text("माफ़ कीजिए, मैं केवल अपने ओनर के लिए समर्पित हूँ।")
        return
    await update.message.reply_text("नमस्ते जी! आपकी सिज़रा अब पूरी जार्विस पॉवर्स (लाइव रिसर्च और परमानेंट मेमोरी) के साथ हाज़िर है। बताइए आज क्या हुक्म है?")

async def process_ai_response(user_text, uid, chat_id, update, context):
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    history = get_recent_memory(uid, limit=6)
    full_prompt = f"{SYSTEM_PROMPT}\n\n[याददाश्त व संदर्भ]:\n{history}\n\nयूज़र: {user_text}\nसिज़रा:"

    reply_text = ""
    # Gemini 3.8 / 2.0 with Live Google Search Grounding
    models_to_run = ["gemini-3.8-flash", "gemini-2.0-flash"]
    
    for model_name in models_to_run:
        try:
            # Google Search टूल एक्टिवेटेड
            response = client.models.generate_content(
                model=model_name,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.7
                )
            )
            if response and response.text:
                reply_text = response.text.strip()
                break
        except Exception:
            continue

    if not reply_text:
        reply_text = "माफ़ कीजिएगा, मैं इंटरनेट या सर्वर से जुड़ नहीं सकी। कृपया एक बार फिर कहें।"

    # मेमोरी में सेव करें
    save_memory(uid, "User", user_text)
    save_memory(uid, "Sizra", reply_text)

    # 1. तुरंत टेक्स्ट रिप्लाई भेजें
    await update.message.reply_text(reply_text)

    # 2. मीठी आवाज़ में वॉयस रिस्पॉन्स
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="record_voice")
        voice_file = f"voice_{update.message.message_id}.mp3"

        spoken_snippet = reply_text.split("\n")[0]
        if len(spoken_snippet) > 180:
            spoken_snippet = spoken_snippet[:180]

        tts = edge_tts.Communicate(spoken_snippet, "hi-IN-SwaraNeural", rate="+10%")
        await tts.save(voice_file)

        with open(voice_file, 'rb') as audio:
            await update.message.reply_voice(audio)

        if os.path.exists(voice_file):
            os.remove(voice_file)
    except Exception:
        pass

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ALLOWED_USER_IDS:
        return
    await process_ai_response(update.message.text, uid, update.effective_chat.id, update, context)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ALLOWED_USER_IDS:
        return

    # वॉयस मैसेज डाउनलोड करके Gemini को सुनना
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    voice_obj = await context.bot.get_file(update.message.voice.file_id)
    audio_path = f"input_{update.message.message_id}.ogg"
    await voice_obj.download_to_drive(audio_path)

    try:
        # Audio सीधे मॉडल को पास करें
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg"),
                "इस ऑडियो को ध्यान से सुनो और समझो कि यूज़र ने क्या कहा।"
            ]
        )
        user_spoken_text = response.text.strip()
        
        if os.path.exists(audio_path):
            os.remove(audio_path)

        # ऑडियो समझने के बाद मुख्य AI प्रोसेस में भेजें
        await process_ai_response(user_spoken_text, uid, update.effective_chat.id, update, context)
    except Exception as e:
        if os.path.exists(audio_path):
            os.remove(audio_path)
        await update.message.reply_text("माफ़ कीजिएगा, मैं आवाज़ ठीक से सुन नहीं पाई।")

if __name__ == '__main__':
    Thread(target=run_web, daemon=True).start()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    print("Sizra Jarvis Engine Active...")
    app.run_polling()
