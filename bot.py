import os
from flask import Flask, request
import telebot
from telebot import types
from pymongo import MongoClient
import gridfs
import requests

# Set up MongoDB connection with the provided connection string
client = MongoClient('mongodb+srv://misonomiyan:Miyan0001@miyan.wdehd.mongodb.net/?retryWrites=true&w=majority&appName=Miyan')
db = client['Miyan']  # Replace with your actual database name
fs = gridfs.GridFS(db)

# Set up Telegram bot with the provided token
bot = telebot.TeleBot('7772133971:AAHgGq0Yci1c5Hwyb0kz0nZG0sJOYIsXs9M')

# Flask app setup
app = Flask(__name__)

# Handle /save command
@bot.message_handler(commands=['save'])
def save_message(message):
    parts = message.text.split(' ', 1)
    if len(parts) < 2:
        bot.reply_to(message, 'Please provide a name after /save.')
        return
    name = parts[1].strip()
    content_type = message.content_type

    if content_type == 'text':
        db.messages.insert_one({'name': name, 'type': 'text', 'content': message.text})
    elif content_type == 'photo':
        file_info = bot.get_file(message.photo[-1].file_id)
        file = bot.download_file(file_info.file_path)
        file_id = fs.put(file, filename=name, contentType='image/jpeg')
        db.messages.insert_one({'name': name, 'type': 'photo', 'file_id': file_id})
    elif content_type == 'video':
        file_info = bot.get_file(message.video.file_id)
        file = bot.download_file(file_info.file_path)
        file_id = fs.put(file, filename=name, contentType='video/mp4')
        db.messages.insert_one({'name': name, 'type': 'video', 'file_id': file_id})
    elif content_type == 'document':
        file_info = bot.get_file(message.document.file_id)
        file = bot.download_file(file_info.file_path)
        content_type = message.document.mime_type
        file_id = fs.put(file, filename=name, contentType=content_type)
        db.messages.insert_one({'name': name, 'type': 'document', 'file_id': file_id})
    else:
        bot.reply_to(message, f'Unsupported message type: {content_type}')
        return
    bot.reply_to(message, f'Message saved with name "{name}".')

# Handle /send command
@bot.message_handler(commands=['send'])
def send_message(message):
    parts = message.text.split(' ', 1)
    if len(parts) < 2:
        bot.reply_to(message, 'Please provide a name after /send.')
        return
    name = parts[1].strip()
    msg = db.messages.find_one({'name': name})
    if msg:
        if msg['type'] == 'text':
            bot.send_message(message.chat.id, msg['content'])
        elif msg['type'] == 'photo':
            file_id = msg['file_id']
            file = fs.get(file_id)
            bot.send_photo(message.chat.id, file)
        elif msg['type'] == 'video':
            file_id = msg['file_id']
            file = fs.get(file_id)
            bot.send_video(message.chat.id, file)
        elif msg['type'] == 'document':
            file_id = msg['file_id']
            file = fs.get(file_id)
            bot.send_document(message.chat.id, file)
        else:
            bot.reply_to(message, f'Unknown message type: {msg["type"]}')
    else:
        bot.reply_to(message, f'No message found with name "{name}".')

@app.route('/webhook', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
    bot.process_new_updates([update])
    return 'OK'

@app.route("/")
def home():
    return 'OK'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)