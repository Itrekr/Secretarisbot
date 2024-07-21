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

journal_file_path = "/var/www/html/data/Oscar/files/Notes/Journal/journal.org"

async def send_daily_reminders(context: ContextTypes.DEFAULT_TYPE):
    try:
        # Print the current date and time
        print(f"Running send_daily_reminders at {datetime.datetime.now()}")

        # Get today's date
        today = datetime.date.today()
        current_year = today.strftime('%Y')
        current_month_day = today.strftime('%m-%d')
        print(f"Today's date: {today}")

        # Build the journal folder path
        journal_folder = "/var/www/html/data/Oscar/files/Notes/Journal/"
        print(f"Journal folder path: {journal_folder}")

        # Get the list of files in the journal folder
        files = os.listdir(journal_folder)
        print(f"Files in journal folder: {files}")

        # Filter the files for journal entries matching today's month and day, excluding the current year
        found_entries = [
            file[:-4]  # remove the '.org' extension
            for file in files
            if file.endswith('.org') and file[5:10] == current_month_day and file[:4] != current_year
        ]
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
            file_path = f"/var/www/html/data/Oscar/files/Notes/Journal/journal.org"

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
        file_path = f"/var/www/html/data/Oscar/files/Notes/Journal/journal.org"
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

def insert_journal_entry(file_path, message):
    today = datetime.date.today()
    current_year = today.strftime('%Y')
    current_week = today.strftime('%Y-W%V')
    current_date = today.strftime('%Y-%m-%d')
    current_day = today.strftime('%A')
    unique_id = str(uuid4())

    # Read the existing journal file content
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            content = f.readlines()
    else:
        content = []

    found_year = found_week = found_date = found_properties = False
    new_content = []
    last_line_empty = False

    for line in content:
        if line.strip() == f"* {current_year}":
            found_year = True
        elif found_year and line.strip() == f"** {current_week}":
            found_week = True
        elif found_week and line.strip() == f"*** {current_date} {current_day}":
            found_date = True
        elif found_date and ":PROPERTIES:" in line:
            found_properties = True
        elif found_properties and ":END:" in line:
            found_properties = False
            if not found_date:
                new_content.append(line)
                new_content.append('\n')
                new_content.append(message + '\n')
                found_date = True
                continue

        new_content.append(line)
        last_line_empty = (line.strip() == "")

    if not found_year:
        if not last_line_empty:
            new_content.append('\n')
        new_content.append(f"* {current_year}\n")
    if not found_week:
        if not last_line_empty:
            new_content.append('\n')
        new_content.append(f"** {current_week}\n")
    if not found_date:
        if not last_line_empty:
            new_content.append('\n')
        new_content.append(f"*** {current_date} {current_day}\n")
        new_content.append(":PROPERTIES:\n")
        new_content.append(f":ID:       {unique_id}\n")
        new_content.append(":END:\n")
        new_content.append('\n')
        new_content.append(message + '\n')
    else:
        if not last_line_empty:
            new_content.append('\n')
        new_content.append(message + '\n')

    with open(file_path, 'w') as f:
        f.writelines(new_content)

# Function to handle incoming text messages and create/update journal entries
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if str(user_id) != AUTHORIZED_USER_ID:
        update.message.reply_text('Unauthorized.')
        return

    message = update.message.text

    insert_journal_entry(journal_file_path, message)

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
    scheduler.add_job(send_daily_reminders, CronTrigger(hour=9, minute=1), args=[application])
    # scheduler.add_job(remind_to_write, CronTrigger(hour=20, minute=55), args=[application])
    scheduler.start()

    application.run_polling()
