import os
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, Webhook
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
import uvicorn

# --- Config ---
TOKEN = os.environ.get("BOT_TOKEN")  # Set in Render Environment Variables
MY_TZ = ZoneInfo("Asia/Yangon")
PORT = int(os.environ.get("PORT", 8000))  # Render provides PORT

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

    except Exception as e:
        logging.error(f"Error adding task: {e}")
        await update.message.reply_text(f"⚠️ Error: {e}")

async def send_reminder(context: ContextTypes.DEFAULT_TYPE, chat_id, task_text):
    await context.bot.send_message(chat_id=chat_id, text=f"⏰ Reminder: {task_text}")

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not tasks:
        await update.message.reply_text("No tasks yet 💤")
    else:
        msg = "\n".join([f"- {t[0]} at {t[1]}" for t in tasks])
        await update.message.reply_text("📋 Your tasks:\n" + msg)

# --- FastAPI App for Webhook ---
app = FastAPI()

@app.post(f"/webhook/{TOKEN}")
async def telegram_webhook(update: dict):
    """Receives Telegram updates via webhook"""
    from telegram import Update
    from telegram.ext import Application
    update_obj = Update.de_json(update, application.bot)
    await application.update_queue.put(update_obj)
    return {"ok": True}

# --- Telegram Application ---
application = ApplicationBuilder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("add", add_task))
application.add_handler(CommandHandler("list", list_tasks))

# --- Start Webhook ---
async def main():
    url = os.environ.get("RENDER_EXTERNAL_URL")  # Render service URL
    if not url:
        raise Exception("Set RENDER_EXTERNAL_URL environment variable!")

    webhook_url = f"{url}/webhook/{TOKEN}"
    logging.info(f"Setting webhook to: {webhook_url}")
    await application.bot.set_webhook(webhook_url)

    logging.info("Bot started with Webhook ✅")
    await application.start()
    await application.updater.start_polling()  # optional fallback
    await application.idle()

if __name__ == "__main__":
    import asyncio
    # Start FastAPI + Bot
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    uvicorn.run(app, host="0.0.0.0", port=PORT)
