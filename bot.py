import os
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler

# ✅ Get token from environment (Render → Environment tab → add BOT_TOKEN)
TOKEN = os.environ.get("BOT_TOKEN")

# ✅ Configure logs for Render
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# In-memory tasks
tasks = []

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi Egon! Use /add <task> at <HH:MM> to set a reminder.\nExample: /add Study AI at 20:00"
    )

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = " ".join(context.args)
        if " at " not in text:
            return await update.message.reply_text("❌ Format: /add <task> at <HH:MM>")

        task_text, time_text = text.split(" at ")
        time_obj = datetime.strptime(time_text, "%H:%M").time()

        now = datetime.now()
        remind_time = datetime.combine(now.date(), time_obj)
        if remind_time < now:
            remind_time += timedelta(days=1)  # next day if already passed

        chat_id = update.effective_chat.id

        # Schedule reminder
        scheduler.add_job(
            send_reminder,
            trigger='date',
            run_date=remind_time,
            args=[context, chat_id, task_text]
        )

        tasks.append((task_text, time_text))
        await update.message.reply_text(f"✅ Reminder set for '{task_text}' at {time_text}")

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

# --- Main bot setup ---
def main():
    logging.info("🚀 Starting Telegram bot...")
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_task))
    app.add_handler(CommandHandler("list", list_tasks))

    app.run_polling()

if __name__ == "__main__":
    main()
