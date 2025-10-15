import os
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from uvicorn import Config, Server

# --- Config ---
TOKEN = os.environ.get("BOT_TOKEN")  # Telegram bot token
MY_TZ = ZoneInfo("Asia/Yangon")
PORT = int(os.environ.get("PORT", 8000))
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")  # e.g., https://bot-testing-4ekg.onrender.com

# --- Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# --- Scheduler ---
scheduler = BackgroundScheduler(timezone=MY_TZ)
scheduler.start()

# --- In-memory tasks ---
tasks = []

# --- Telegram Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi Egon! Use /add <task> at <HH:MM AM/PM> to set a reminder.\n"
        "Example: /add Study AI at 08:30 PM"
    )
    logging.info(f"/start received from chat_id={update.effective_chat.id}")

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = " ".join(context.args)
        if " at " not in text:
            return await update.message.reply_text("❌ Format: /add <task> at <HH:MM AM/PM>")

        task_text, time_text = text.split(" at ")
        time_obj = datetime.strptime(time_text.strip(), "%I:%M %p").time()

        now = datetime.now(tz=MY_TZ)
        remind_time = datetime.combine(now.date(), time_obj, tzinfo=MY_TZ)
        if remind_time < now:
            remind_time += timedelta(days=1)

        chat_id = update.effective_chat.id

        scheduler.add_job(
            send_reminder,
            trigger="date",
            run_date=remind_time,
            args=[context, chat_id, task_text]
        )

        tasks.append((task_text, remind_time.strftime("%I:%M %p")))
        await update.message.reply_text(
            f"✅ Reminder set for '{task_text}' at {remind_time.strftime('%I:%M %p')}"
        )
        logging.info(f"Task added: '{task_text}' at {remind_time.strftime('%I:%M %p')} for chat_id={chat_id}")

    except Exception as e:
        logging.error(f"Error adding task: {e}")
        await update.message.reply_text(f"⚠️ Error: {e}")

async def send_reminder(context: ContextTypes.DEFAULT_TYPE, chat_id, task_text):
    await context.bot.send_message(chat_id=chat_id, text=f"⏰ Reminder: {task_text}")
    logging.info(f"✅ Reminder sent: '{task_text}' to chat_id={chat_id}")

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not tasks:
        await update.message.reply_text("No tasks yet 💤")
    else:
        msg = "\n".join([f"- {t[0]} at {t[1]}" for t in tasks])
        await update.message.reply_text("📋 Your tasks:\n" + msg)
    logging.info(f"/list called by chat_id={update.effective_chat.id}")

# --- FastAPI App ---
app = FastAPI()

@app.get("/")
async def home():
    return {"message": "🤖 Telegram Reminder Bot is running!"}

@app.post(f"/webhook/{TOKEN}")
async def telegram_webhook(update: dict):
    logging.info(f"Received update: {update}")
    from telegram import Update as TGUpdate
    update_obj = TGUpdate.de_json(update, application.bot)
    await application.update_queue.put(update_obj)
    return {"ok": True}

# --- Telegram Application ---
application = ApplicationBuilder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("add", add_task))
application.add_handler(CommandHandler("list", list_tasks))

# --- Main function ---
async def main():
    if not RENDER_URL:
        raise Exception("Set RENDER_EXTERNAL_URL environment variable!")

    webhook_url = f"{RENDER_URL}/webhook/{TOKEN}"
    logging.info(f"Setting webhook to: {webhook_url}")
    await application.bot.set_webhook(webhook_url)

    logging.info("Bot started with Webhook ✅")
    await application.start()
    await application.updater.start_polling()  # optional fallback
    await application.idle()

# --- Run bot + FastAPI server ---
if __name__ == "__main__":
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(main())

    config = Config(app=app, host="0.0.0.0", port=PORT, log_level="info")
    server = Server(config)
    loop.run_until_complete(server.serve())
