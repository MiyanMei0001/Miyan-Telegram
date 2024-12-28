import logging
import csv
import json
from io import StringIO
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    CallbackQueryHandler,
    Dispatcher,
)
from pymongo import MongoClient
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# MongoDB connection
client = MongoClient(os.getenv('MONGODB_URI'))
db = client['your_database_name']

# Helper function to get user-specific collection
def get_user_collection(user_id):
    return db[f'user_{user_id}']

# Initialize Flask app
app = Flask(__name__)

# Initialize Telegram bot
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# Command handlers

def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("Add Data", callback_data='add')],
        [InlineKeyboardButton("List Data", callback_data='list')],
        [InlineKeyboardButton("Delete Data", callback_data='delete')],
        [InlineKeyboardButton("Search Data", callback_data='search')],
        [InlineKeyboardButton("Stats", callback_data='stats')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Welcome to the MongoDB Manager Bot! Choose an action:', reply_markup=reply_markup)

def help_command(update: Update, context: CallbackContext) -> None:
    help_text = """
Available commands:
/add <key:value> - Add data to the database.
/update <key:old_value> <key:new_value> - Update existing data.
/delete <key:value> - Delete data from the database.
/list - List all data in the database.
/search <keyword> - Search for data containing the keyword.
/clear - Delete all data in your collection.
/stats - Show statistics about your data.
/backup - Download your data as a JSON file.
/export_csv - Export your data as a CSV file.
/import_json - Import data from a JSON file.
"""
    update.message.reply_text(help_text)

def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    if query.data == 'add':
        query.edit_message_text('Use /add key:value to add data.')
    elif query.data == 'list':
        list_data(update, context, query)
    elif query.data == 'delete':
        query.edit_message_text('Use /delete key:value to delete data.')
    elif query.data == 'search':
        query.edit_message_text('Use /search keyword to search data.')
    elif query.data == 'stats':
        stats_command(update, context, query)

def list_data(update: Update, context: CallbackContext, query=None) -> None:
    user_id = update.callback_query.from_user.id if query else update.message.from_user.id
    collection = get_user_collection(user_id)

    documents = list(collection.find())
    if not documents:
        if query:
            query.edit_message_text('No data available.')
        else:
            update.message.reply_text('No data available.')
        return

    # Pagination
    page = int(context.args[0]) if context.args else 1
    per_page = 5
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_docs = documents[start_idx:end_idx]

    message = 'Your data:\n'
    for doc in paginated_docs:
        for key, value in doc.items():
            if key != '_id':
                message += f"- {key}: {value}\n"

    # Navigation buttons
    keyboard = []
    if page > 1:
        keyboard.append(InlineKeyboardButton("Previous", callback_data=f'list_{page - 1}'))
    if end_idx < len(documents):
        keyboard.append(InlineKeyboardButton("Next", callback_data=f'list_{page + 1}'))
    reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None

    if query:
        query.edit_message_text(message, reply_markup=reply_markup)
    else:
        update.message.reply_text(message, reply_markup=reply_markup)

def backup_data(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    collection = get_user_collection(user_id)

    documents = list(collection.find())
    if not documents:
        update.message.reply_text('No data available to backup.')
        return

    json_data = json.dumps(documents, default=str, indent=2)
    context.bot.send_document(chat_id=update.message.chat_id, document=StringIO(json_data), filename='backup.json')

def export_csv(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    collection = get_user_collection(user_id)

    documents = list(collection.find())
    if not documents:
        update.message.reply_text('No data available to export.')
        return

    csv_file = StringIO()
    writer = csv.DictWriter(csv_file, fieldnames=documents[0].keys())
    writer.writeheader()
    writer.writerows(documents)

    context.bot.send_document(chat_id=update.message.chat_id, document=StringIO(csv_file.getvalue()), filename='data.csv')

def import_json(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    collection = get_user_collection(user_id)

    if not update.message.document:
        update.message.reply_text('Please upload a JSON file.')
        return

    file = context.bot.get_file(update.message.document.file_id)
    json_data = file.download_as_bytearray().decode('utf-8')
    data = json.loads(json_data)

    collection.insert_many(data)
    update.message.reply_text('Data imported successfully.')

def error_handler(update: Update, context: CallbackContext) -> None:
    logger.warning('Update "%s" caused error "%s"', update, context.error)

# Add handlers to dispatcher
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('help', help_command))
dispatcher.add_handler(CommandHandler('backup', backup_data))
dispatcher.add_handler(CommandHandler('export_csv', export_csv))
dispatcher.add_handler(CommandHandler('import_json', import_json))
dispatcher.add_handler(CallbackQueryHandler(button_handler))
dispatcher.add_handler(CallbackQueryHandler(list_data, pattern='^list_'))
dispatcher.add_error_handler(error_handler)

# Flask route for webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), updater.bot)
    dispatcher.process_update(update)
    return 'ok'

# Start Flask server
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT')))