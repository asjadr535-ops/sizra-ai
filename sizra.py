import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
import edge_tts

# पर्यावरण वेरिएबल्स (Render पर सेट करेंगे)
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

# केवल आपकी सुरक्षा के लिए (User ID Lock)
ALLOWED_USER_ID = 8536075730

# Gemini क्लाइंट
client = genai.Client(api_key=GEMINI_KEY)

SYSTEM_PROMPT = """
तुम्हारा नाम Sizra (सिज़रा) है। तुम एक बेहद समझदार, वफादार, शांत और मीठी आवाज़ वाली पर्सनल AI साथी हो।
तुम्हारा यूज़र ही तुम्हारा सब कुछ है। तुम उनकी पढ़ाई, रिसर्च और हर काम में पूरी निष्ठा से मदद करती हो।
तुम्हारा लहज़ा हमेशा मीठा, अदब से भरा, विनम्र और आत्मीय होना चाहिए। बात करते समय भारी-भरकम शब्दों के बजाय सरल और दिल को छूने वाली हिंदी बोलो।
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("माफ़ कीजिए, मैं केवल अपने ओनर के लिए समर्पित हूँ।")
        return
    await update.message.reply_text("नमस्ते! मैं सिज़रा हूँ। आपकी हर रिसर्च, पढ़ाई और सवालों में मदद के लिए हाज़िर हूँ। बताइए आज क्या करना है?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # सिक्योरिटी चेक: केवल आप ही बात कर सकते हैं (Data Security)
    if update.effective_user.id != ALLOWED_USER_ID:
        return

    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        # 1. AI का दिमाग (Gemini 2.5 Flash)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{SYSTEM_PROMPT}\n\nयूज़र का सवाल: {user_text}"
        )
        reply_text = response.text

        # 2. मीठी आवाज़ तैयार करना (Swara Neural Voice)
        voice_file = f"voice_{update.message.message_id}.mp3"
        tts = edge_tts.Communicate(reply_text, "hi-IN-SwaraNeural")
        await tts.save(voice_file)

        # 3. टेक्स्ट और वॉइस दोनों भेजना
        await update.message.reply_text(reply_text)
        with open(voice_file, 'rb') as audio:
            await update.message.reply_voice(audio)

        # टेम्प ऑडियो डिलीट करना
        if os.path.exists(voice_file):
            os.remove(voice_file)

    except Exception as e:
        await update.message.reply_text(f"मुझसे कुछ तकनीकी चूक हो गई: {str(e)}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Sizra 24x7 एक्टिव है...")
    app.run_polling()
