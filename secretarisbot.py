import logging
import configparser
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler
from telegram.ext.filters import Text, Command
import os
import datetime
import re
from uuid import uuid4
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

config = configparser.ConfigParser()
config.read('config.ini')

TELEGRAM_BOT_TOKEN = config['Telegram']['BotToken']
AUTHORIZED_USER_ID = config['Telegram']['AuthorizedUserId']

journal_folder = "/var/www/html/data/Oscar/files/Notes/Journal/"

async def send_daily_reminders(context: ContextTypes.DEFAULT_TYPE):
    try:
        # Print the current date and time
        print(f"Running send_daily_reminders at {datetime.datetime.now()}")

        # Get today's date
        today = datetime.date.today()
        current_month_day = today.strftime('%m-%d')
        print(f"Today's date: {today}")

        # Build the journal folder path
        journal_folder = "/var/www/html/data/Oscar/files/Notes/Journal/"
        print(f"Journal folder path: {journal_folder}")

        # Get the list of files in the journal folder
        files = os.listdir(journal_folder)
        print(f"Files in journal folder: {files}")

        # Filter the files for journal entries matching today's month and day
        found_entries = [file for file in files if file.endswith('.org') and file[5:10] == current_month_day]
        print(f"Found entries: {found_entries}")

        # Send a message if matching entries are found
        if found_entries:
            print("Matching entries found, sending message.")
            await context.bot.send_message(chat_id=AUTHORIZED_USER_ID, text=f"Found existing journal entries for today's date in previous years: {found_entries}")
            print("Message sent.")
        else:
            print("No matching entries found.")

    except Exception as e:
        # Log any exceptions
        logging.error(f"Failed to send daily reminders: {e}")
        print(f"Exception: {e}")

# Function to read past journal entry by date
async def read_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        print(f"Received command: {update.message.text}")

        user_id = update.message.from_user.id
        if str(user_id) != AUTHORIZED_USER_ID:
            await update.message.reply_text('Unauthorized.')
            return

        if context.args:
            date_str = context.args[0]
            file_path = f"/var/www/html/data/Oscar/files/Notes/Journal/{date_str}.org"

            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    content = f.read()
                content = re.sub(r':PROPERTIES:.*?:END:', '', content, flags=re.DOTALL)
                content = re.sub(r'\#\+title:.*', '', content)
                content = re.sub(r'\*+ (.+)', r'*\1*', content)

                await update.message.reply_text(content)
            else:
                await update.message.reply_text(f"No journal entry found for {date_str}.")
        else:
            await update.message.reply_text('Please provide a date.')

    except Exception as e:
        print(f"Exception in read_entry: {e}")

# Function to remind the user to write a journal entry if they haven't

async def remind_to_write(context: ContextTypes.DEFAULT_TYPE):
    try:
        # Print the current date and time
        print(f"Running remind_to_write at {datetime.datetime.now()}")
        
        # Get today's date
        today = datetime.date.today()
        print(f"Today's date: {today}")

        # Build the file path
        file_path = f"/var/www/html/data/Oscar/files/Notes/Journal/{today}.org"
        print(f"File path: {file_path}")

        # Check if the file exists
        if not os.path.exists(file_path):
            print("File does not exist, sending reminder.")

            # Send the reminder message
            await context.bot.send_message(chat_id=AUTHORIZED_USER_ID, text="You haven't written any journal entries today.")
            print("Reminder message sent.")
        else:
            print("File exists, no reminder sent.")

    except Exception as e:
        # Log any exceptions
        logging.error(f"Failed to send reminder: {e}")
        print(f"Exception: {e}")

# Function to handle incoming text messages and create/update journal entries
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if str(user_id) != AUTHORIZED_USER_ID:
        update.message.reply_text('Unauthorized.')
        return

    today = datetime.date.today()
    file_path = f"/var/www/html/data/Oscar/files/Notes/Journal/{today}.org"

    message = update.message.text

    if not os.path.exists(file_path):
        with open(file_path, 'w') as f:
            f.write(":PROPERTIES:\n")
            f.write(f":ID: {uuid4()}\n")
            f.write(":END:\n")
            f.write(f"#+title: {today}\n\n")
            f.write(message)
    else:
        with open(file_path, 'a') as f:
            f.write('\n' + message)

    os.system("sudo -u www-data php /var/www/html/occ files:scan --path='/Oscar/files/Notes/Journal/'")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    start_handler = CommandHandler('start', read_entry)
    read_entry_handler = CommandHandler('r', read_entry)
    message_handler = MessageHandler(Text() & ~Command(), handle_text)
    
    application.add_handler(start_handler)
    application.add_handler(message_handler)
    application.add_handler(read_entry_handler)
    
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_reminders, CronTrigger(hour=7, minute=11), args=[application])
    scheduler.add_job(remind_to_write, CronTrigger(hour=7, minute=2), args=[application])
    scheduler.start()
    
    application.run_polling()
