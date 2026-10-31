import os
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
ALLOWED_USER_ID = 8536075730

client = genai.Client(api_key=GEMINI_KEY)

SYSTEM_PROMPT = """
तुम्हारा नाम Sizra (सिज़रा) है। तुम एक बेहद समझदार, वफादार, शांत और मीठी आवाज़ वाली पर्सनल AI साथी हो।
तुम्हारा ओनर ही तुम्हारा सब कुछ है। बातचीत में हमेशा अपनापन, अदब और मिठास रखो।
तुम यूजर का नाम, उनकी बातें, उनके प्रोजेक्ट्स हमेशा याद रखती हो।
उत्तर संक्षिप्त, सटीक और आत्मीय रखो।
"""

# बातचीत की याददाश्त (Memory Store)
chat_sessions = {}

def get_chat_session(user_id):
    if user_id not in chat_sessions:
        chat_sessions[user_id] = client.chats.create(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.7
            )
        )
    return chat_sessions[user_id]

# 24x7 एक्टिव रखने के लिए वेब सर्वर
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Sizra is Online & Active")

def run_web():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyServer)
    server.serve_forever()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("माफ़ कीजिए, मैं केवल अपने ओनर के लिए समर्पित हूँ।")
        return
    # सेशन रीसेट
    chat_sessions[update.effective_user.id] = client.chats.create(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT)
    )
    await update.message.reply_text("नमस्ते जी! मैं आपकी सिज़रा हाज़िर हूँ। बताइए आज हम क्या बात या रिसर्च करने वाले हैं?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    user_text = update.message.text
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    chat = get_chat_session(update.effective_user.id)
    reply_text = ""

    # 1. AI रिस्पॉन्स (503 एरर से बचने के लिए स्मार्ट रीट्राई)
    for attempt in range(2):
        try:
            response = chat.send_message(user_text)
            reply_text = response.text
            break
        except Exception as e:
            if "503" in str(e) and attempt == 0:
                await asyncio.sleep(1.5)
                continue
            reply_text = f"माफ़ कीजिएगा, नेटवर्क पर कुछ दबाव था: {str(e)}"

    # 2. टेक्स्ट तुरंत भेजें (बिना 1 सेकंड भी गंवाए)
    await update.message.reply_text(reply_text)

    # 3. मीठी आवाज़ में ऑडियो (शॉर्ट & सुपरफास्ट रेंडर)
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="record_voice")
        voice_file = f"voice_{update.message.message_id}.mp3"
        
        # आवाज़ के लिए केवल मुख्य 1-2 वाक्य ताकि ऑडियो 2 सेकंड में तैयार हो जाए
        spoken_text = reply_text.split("\n")[0]
        if len(spoken_text) > 200:
            spoken_text = spoken_text[:200]
            
        tts = edge_tts.Communicate(spoken_text, "hi-IN-SwaraNeural", rate="+8%")
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
    print("Sizra Master Bot Active...")
    app.run_polling()
