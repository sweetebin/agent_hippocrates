import asyncio
import os
import requests
import logging
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import base64
from io import BytesIO
from PIL import Image

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

SERVER_URL = os.environ.get('SERVER_URL', 'http://localhost:5000')

class TelegramAgentBot:
    def __init__(self, token):
        self.token = token

    async def start(self, update: Update, context):
        """Handler for /start command"""
        user_id = str(update.effective_user.id)

        try:
            # Initialize new session
            response = requests.post(
                f'{SERVER_URL}/initialize',
                json={'user_id': user_id}
            )

            if response.status_code == 200:
                # Clear any existing data
                requests.post(
                    f'{SERVER_URL}/clear',
                    json={'user_id': user_id}
                )

                # Reinitialize
                response = requests.post(
                    f'{SERVER_URL}/initialize',
                    json={'user_id': user_id}
                )

                await update.message.reply_text(
                    "Добрый день! Я ассистент медицинской диагностики, не могли бы вы представится и мы можем начать"
                )
            else:
                await update.message.reply_text("Sorry, there was an issue initializing your session.")

        except Exception as e:
            logger.error(f"Initialization error: {e}")
            await update.message.reply_text("An error occurred while starting the bot.")

    async def handle_photo(self, update: Update, context):
        """Handle incoming photos"""
        user_id = str(update.effective_user.id)

        try:
            # Get only the highest quality photo (last in the list)
            photo = update.message.photo[-1]  # Telegram sorts photos by size, last one is the biggest
            base64_images = []

            # Show processing message
            processing_message = await update.message.reply_text(
                "Обрабатываю изображения..."
            )

            # Process the photo
            photo_file = await context.bot.get_file(photo.file_id)
            photo_bytes = await photo_file.download_as_bytearray()

            # Convert to base64
            img_buffer = BytesIO(photo_bytes)
            img = Image.open(img_buffer)

            # Optionally, you can add image optimization here
            # For example, resize if too large
            max_size = 1024  # Maximum dimension
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = tuple(int(dim * ratio) for dim in img.size)
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=85)  # Adjust quality as needed
            base64_images.append(base64.b64encode(buffer.getvalue()).decode('utf-8'))

            # Send image for processing
            response = requests.post(
                f'{SERVER_URL}/process_images',
                json={
                    'user_id': user_id,
                    'images': base64_images
                }
            )

            if response.status_code == 200:
                agent_responses = response.json().get('response', [])
                for resp in agent_responses:
                    if resp.get('content'):
                        await update.message.reply_text(resp['content'])
            else:
                await update.message.reply_text(
                    "Извините, не удалось обработать изображение."
                )

            await processing_message.delete()

        except Exception as e:
            logger.error(f"Image processing error: {e}")
            await update.message.reply_text(
                "Произошла ошибка при обработке изображения."
            )

    async def handle_message(self, update: Update, context):
        """Process incoming messages"""
        user_id = str(update.effective_user.id)
        message = update.message.text

        try:
            # Show typing indicator
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=ChatAction.TYPING
            )

            # Send message to server
            response = requests.post(
                f'{SERVER_URL}/message',
                json={
                    'user_id': user_id,
                    'message': {
                        'role': 'user',
                        'content': message
                    }
                }
            )

            if response.status_code == 200:
                agent_responses = response.json().get('response', [])
                for resp in agent_responses:
                    if resp.get('content'):
                        await update.message.reply_text(resp['content'])
            else:
                await update.message.reply_text(
                    "Извините, произошла ошибка при обработке сообщения."
                )

        except Exception as e:
            logger.error(f"Message processing error: {e}")
            await update.message.reply_text(
                "Произошла ошибка при обработке вашего сообщения."
            )

def main():
    TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not TOKEN:
        logging.error("No Telegram bot token provided")
        return

    application = Application.builder().token(TOKEN).build()
    bot = TelegramAgentBot(TOKEN)

    # Register handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, bot.handle_photo))

    logging.info("Starting Telegram bot...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()