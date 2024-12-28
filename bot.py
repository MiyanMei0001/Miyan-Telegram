import os
import logging
from flask import Flask, request
import telebot
from telebot import types
from pymongo import MongoClient
import gridfs

# Replace the connection string with your own
client = MongoClient('mongodb+srv://misonomiyan:Miyan0001@miyan.wdehd.mongodb.net/?retryWrites=true&w=majority&appName=Miyan')
db = client['Miyan']
fs = gridfs.GridFS(db)
app = Flask(__name__)
bot = telebot.TeleBot('7898850924:AAFKftyshzOm3eUfKPLLlVU-989N51kfbHA')

@bot.message_handler(commands=['save'])
def save_message(message):
    # Extract the name after /save
    parts = message.text.split(' ', 1)
    if len(parts) < 2:
        bot.reply_to(message, 'Please provide a name after /save.')
        return
    name = parts[1].strip()
    # Save the message based on its content type
    if message.text:
        # Save text message
        db.messages.insert_one({'name': name, 'type': 'text', 'content': message.text})
    elif message.photo:
        # Save photo
        file_info = bot.get_file(message.photo[-1].file_id)
        file = bot.download_file(file_info.file_path)
        file_id = fs.put(file, filename=name, contentType='image/jpeg')
        db.messages.insert_one({'name': name, 'type': 'photo', 'file_id': file_id})
    elif message.video:
        # Save video
        file_info = bot.get_file(message.video.file_id)
        file = bot.download_file(file_info.file_path)
        file_id = fs.put(file, filename=name, contentType='video/mp4')
        db.messages.insert_one({'name': name, 'type': 'video', 'file_id': file_id})
    # Add handlers for other message types as needed
    bot.reply_to(message, f'Message saved with name "{name}".')
    
@bot.message_handler(commands=['send'])
def send_message(message):
    # Extract the name after /send
    parts = message.text.split(' ', 1)
    if len(parts) < 2:
        bot.reply_to(message, 'Please provide a name after /send.')
        return
    name = parts[1].strip()
    # Retrieve the message from the database
    msg = db.messages.find_one({'name': name})
    if msg:
        if msg['type'] == 'text':
            bot.send_message(message.chat.id, msg['content'])
        elif msg['type'] == 'photo':
            # Retrieve photo from GridFS
            file_id = msg['file_id']
            file = fs.get(file_id)
            bot.send_photo(message.chat.id, file)
        elif msg['type'] == 'video':
            # Retrieve video from GridFS
            file_id = msg['file_id']
            file = fs.get(file_id)
            bot.send_video(message.chat.id, file)
        # Add handlers for other message types as needed
    else:
        bot.reply_to(message, f'No message found with name "{name}".')

@app.route('/webhook', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
    bot.process_new_updates([update])
    return 'OK'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 3000)), debug=False)
