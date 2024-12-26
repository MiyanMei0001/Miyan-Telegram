import os
from dotenv import load_dotenv
import telebot
from pymongo import MongoClient
from flask import Flask, request
from bson.objectid import ObjectId

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DBNAME = os.getenv("MONGODB_DBNAME")
client = MongoClient(MONGODB_URI)
db = client[MONGODB_DBNAME]
files_collection = db['files']

useWebhook = False

app = Flask(__name__)

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

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Halo! Saya bot untuk menyimpan dan mengirim media.\n\nGunakan:\n/save [nama] - untuk menyimpan media dengan nama\n/send [nama] - untuk mengirim media berdasarkan nama")

@bot.message_handler(commands=['save'])
def save_media(message):
    try:
        command_parts = message.text.split(' ', 1)
        if len(command_parts) < 2:
            bot.reply_to(message, "Format salah, gunakan: /save [nama]")
            return

        name = command_parts[1].strip()
        media_type, file_id = get_media_type(message)

        if not file_id:
             bot.reply_to(message, "Maaf, perintah ini hanya bisa untuk menyimpan file media (dokumen, foto, video, audio, dll)")
             return

        if not is_valid_file_id(file_id):
             bot.reply_to(message, "File Id tidak valid")
             return
        
        existing_file = files_collection.find_one({"name": name})

        if existing_file:
            bot.reply_to(message, "Maaf, nama file sudah ada. Silakan gunakan nama lain.")
        else:
            file_info = get_file_info(file_id)
            file_data = {
                "name": name,
                "file_id": file_id,
                "media_type": media_type,
                "user_id": message.from_user.id,
                "username": message.from_user.username,
                "file_info": file_info_to_dict(file_info)
            }
            files_collection.insert_one(file_data)
            bot.reply_to(message, f"Media dengan nama '{name}' berhasil disimpan.")
    except Exception as e:
        bot.reply_to(message, f"Terjadi kesalahan: {str(e)}")

@bot.message_handler(commands=['send'])
def send_media(message):
    try:
        command_parts = message.text.split(' ', 1)
        if len(command_parts) < 2:
            bot.reply_to(message, "Format salah, gunakan: /send [nama]")
            return

        name = command_parts[1].strip()
        file_data = files_collection.find_one({"name": name})

        if file_data:
            file_id = file_data["file_id"]
            media_type = file_data["media_type"]
            
            if media_type == 'document':
                bot.send_document(message.chat.id, file_id, caption=f"File: {name} ({file_data.get('username')})")
            elif media_type == 'photo':
                bot.send_photo(message.chat.id, file_id, caption=f"Foto: {name} ({file_data.get('username')})")
            elif media_type == 'video':
                bot.send_video(message.chat.id, file_id, caption=f"Video: {name} ({file_data.get('username')})")
            elif media_type == 'audio':
                bot.send_audio(message.chat.id, file_id, caption=f"Audio: {name} ({file_data.get('username')})")
            elif media_type == 'voice':
                bot.send_voice(message.chat.id, file_id, caption=f"Voice Note: {name} ({file_data.get('username')})")
            elif media_type == 'sticker':
                bot.send_sticker(message.chat.id, file_id)
            else:
                bot.reply_to(message, "Tipe media tidak dikenal.")
        else:
            bot.reply_to(message, f"Tidak ada media dengan nama '{name}'")
    except Exception as e:
           bot.reply_to(message, f"Terjadi kesalahan: {str(e)}")

@app.route("/")
def webhook():
   if useWebhook && request.headers.get('content-type') == 'application/json':
       json_string = request.get_data().decode('utf-8')
       update = telebot.types.Update.de_json(json_string)
       bot.process_new_updates([update])
       return '', 200
   else:
       return 'ok', 200


if __name__ == "__main__":
    bot.remove_webhook()
    bot.polling(none_stop=True)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 1000)))