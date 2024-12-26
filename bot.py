import os
from dotenv import load_dotenv
import telebot
from pymongo import MongoClient
from flask import Flask, request

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DBNAME = os.getenv("MONGODB_DBNAME")
client = MongoClient(MONGODB_URI)
db = client[MONGODB_DBNAME]
files_collection = db['files']

app = Flask(__name__)

def get_file_info(file_id):
    file_info = bot.get_file(file_id)
    return file_info

def get_media_type(message):
    if message.reply_to_message:
        message = message.reply_to_message
        
    if message.document:
        return 'document', message.document.file_id
    elif message.photo:
        return 'photo', message.photo[-1].file_id
    elif message.video:
        return 'video', message.video.file_id
    elif message.audio:
        return 'audio', message.audio.file_id
    elif message.voice:
        return 'voice', message.voice.file_id
    elif message.sticker:
        return 'sticker', message.sticker.file_id
    else:
        return None, None

def forward_message_and_get_message_id(chat_id, from_chat_id, message_id):
    forwarded_message = bot.forward_message(chat_id, from_chat_id, message_id)
    return forwarded_message.message_id

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Hello! I am a bot for saving and sending media.\n\nUse:\n/save [name] - to save media with a name\n/send [name] - to send media based on the name")

@bot.message_handler(commands=['save'])
def save_media(message):
    try:
        command_parts = message.text.split(' ', 1)
        if len(command_parts) < 2:
            bot.reply_to(message, "Incorrect format, use: /save [name]")
            return

        name = command_parts[1].strip()
        media_type, file_id = get_media_type(message)

        if not file_id:
             bot.reply_to(message, "Sorry, this command can only save media files (documents, photos, videos, audio, etc.)")
             return

        existing_file = files_collection.find_one({"name": name})

        if existing_file:
            bot.reply_to(message, "Sorry, the file name already exists. Please use another name.")
        else:
            forward_message_id = forward_message_and_get_message_id(message.chat.id, message.chat.id, message.message_id)
            file_info = get_file_info(file_id)
            file_data = {
                "name": name,
                "file_id": file_id,
                "media_type": media_type,
                "user_id": message.from_user.id,
                "username": message.from_user.username,
                "message_id": forward_message_id,
                "file_info": file_info
            }
            files_collection.insert_one(file_data)
            bot.reply_to(message, f"Media with the name '{name}' has been successfully saved.")
    except Exception as e:
        bot.reply_to(message, f"An error occurred: {str(e)}")

@bot.message_handler(commands=['send'])
def send_media(message):
    try:
        command_parts = message.text.split(' ', 1)
        if len(command_parts) < 2:
            bot.reply_to(message, "Incorrect format, use: /send [name]")
            return

        name = command_parts[1].strip()
        file_data = files_collection.find_one({"name": name})

        if file_data:
            message_id = file_data["message_id"]
            bot.forward_message(message.chat.id, message.chat.id, message_id)
        else:
            bot.reply_to(message, f"No media found with the name '{name}'")
    except Exception as e:
           bot.reply_to(message, f"An error occurred: {str(e)}")

@app.route("/")
def home():
       return 'ok', 200


if __name__ == "__main__":
    bot.polling(none_stop=True)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))