import os
from dotenv import load_dotenv
import telebot
from pymongo import MongoClient
from flask import Flask, request
from bson.objectid import ObjectId
import requests

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DBNAME = os.getenv("MONGODB_DBNAME")
client = MongoClient(MONGODB_URI)
db = client[MONGODB_DBNAME]
files_collection = db['files']

app = Flask(__name__)

MAX_FILE_SIZE_MB = 20 # Set your maximum size here

def get_file_info(file_id):
    file_info = bot.get_file(file_id)
    return file_info

def file_info_to_dict(file_info):
    if file_info:
        return {
            "file_id": file_info.file_id,
            "file_unique_id": file_info.file_unique_id,
            "file_size": file_info.file_size,
            "file_path": file_info.file_path,
        }
    return None

def get_file_url(file_id):
    file_info = get_file_info(file_id)
    file_path = file_info.file_path
    return f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

def is_valid_file_id(file_id):
    try:
        file_info = bot.get_file(file_id)
        if file_info:
            return True
    except telebot.apihelper.ApiException:
        return False

def get_media_type(message):
    if message.reply_to_message:
        message = message.reply_to_message
        
    if message.document:
        return 'document', message.document.file_id, message.document.file_size
    elif message.photo:
        return 'photo', message.photo[-1].file_id, message.photo[-1].file_size
    elif message.video:
        return 'video', message.video.file_id, message.video.file_size
    elif message.audio:
        return 'audio', message.audio.file_id, message.audio.file_size
    elif message.voice:
        return 'voice', message.voice.file_id, message.voice.file_size
    elif message.sticker:
        return 'sticker', message.sticker.file_id, None
    else:
        return None, None, None

def download_file(file_path, file_name):
    try:
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        response = requests.get(file_url, stream=True)
        response.raise_for_status()
        
        with open(file_name, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        return True
    except Exception as e:
        print(f"Error downloading file: {e}")
        return False

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Hello! I am a bot to save and send media.\n\nUsage:\n/save [name] - to save media with a name\n/send [name] - to send media based on the name")

@bot.message_handler(commands=['save'])
def save_media(message):
    try:
        command_parts = message.text.split(' ', 1)
        if len(command_parts) < 2:
            bot.reply_to(message, "Invalid format, use: /save [name]")
            return

        name = command_parts[1].strip()
        media_type, file_id, file_size = get_media_type(message)
        
        if not file_id:
            bot.reply_to(message, "Sorry, this command can only save media files (documents, photos, videos, audio, etc).")
            return
        
        existing_file = files_collection.find_one({"name": name})
        
        if existing_file:
            bot.reply_to(message, "Sorry, a file with this name already exists. Please use a different name.")
            return
        
        file_info = get_file_info(file_id)
        
        is_large_file = False
        if file_size and file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
            is_large_file = True
        
        file_data = {
                "name": name,
                "file_id": file_id,
                "media_type": media_type,
                "user_id": message.from_user.id,
                "username": message.from_user.username,
                "file_info": file_info_to_dict(file_info),
                "save_type": "online" if not is_large_file else "local"
            }

        if is_large_file:
             file_path = file_info.file_path
             if download_file(file_path,name):
                  file_data["file_path"] = name
             else:
                 bot.reply_to(message, f"Failed to download the file {name}")
                 return
        elif not is_valid_file_id(file_id):
            bot.reply_to(message, "File Id is invalid")
            return
             
        files_collection.insert_one(file_data)
        bot.reply_to(message, f"Media with name '{name}' successfully saved.")

    except Exception as e:
        bot.reply_to(message, f"An error occurred: {str(e)}")

@bot.message_handler(commands=['send'])
def send_media(message):
    try:
        command_parts = message.text.split(' ', 1)
        if len(command_parts) < 2:
            bot.reply_to(message, "Invalid format, use: /send [name]")
            return

        name = command_parts[1].strip()
        file_data = files_collection.find_one({"name": name})

        if file_data:
            file_id = file_data["file_id"]
            media_type = file_data["media_type"]
            save_type = file_data.get("save_type", "online")
            
            if save_type == "online":
                if media_type == 'document':
                    bot.send_document(message.chat.id, file_id, caption=f"File: {name} ({file_data.get('username')})")
                elif media_type == 'photo':
                    bot.send_photo(message.chat.id, file_id, caption=f"Photo: {name} ({file_data.get('username')})")
                elif media_type == 'video':
                    bot.send_video(message.chat.id, file_id, caption=f"Video: {name} ({file_data.get('username')})")
                elif media_type == 'audio':
                    bot.send_audio(message.chat.id, file_id, caption=f"Audio: {name} ({file_data.get('username')})")
                elif media_type == 'voice':
                    bot.send_voice(message.chat.id, file_id, caption=f"Voice Note: {name} ({file_data.get('username')})")
                elif media_type == 'sticker':
                    bot.send_sticker(message.chat.id, file_id)
                else:
                    bot.reply_to(message, "Unknown media type.")
            elif save_type == "local":
                file_path = file_data.get("file_path")
                if file_path:
                    if media_type == 'document':
                        bot.send_document(message.chat.id, open(file_path,'rb'), caption=f"File: {name} ({file_data.get('username')})")
                    elif media_type == 'photo':
                        bot.send_photo(message.chat.id, open(file_path,'rb'), caption=f"Photo: {name} ({file_data.get('username')})")
                    elif media_type == 'video':
                       bot.send_video(message.chat.id, open(file_path,'rb'), caption=f"Video: {name} ({file_data.get('username')})")
                    elif media_type == 'audio':
                        bot.send_audio(message.chat.id, open(file_path,'rb'), caption=f"Audio: {name} ({file_data.get('username')})")
                    elif media_type == 'voice':
                        bot.send_voice(message.chat.id, open(file_path,'rb'), caption=f"Voice Note: {name} ({file_data.get('username')})")
                    elif media_type == 'sticker':
                           bot.send_sticker(message.chat.id, open(file_path,'rb'))
                else:
                     bot.reply_to(message, f"File not found in local {name}")
            
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