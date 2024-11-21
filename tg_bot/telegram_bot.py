import asyncio
import os
import requests
import logging
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Configure logging correctly
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Server configuration
SERVER_URL = os.environ.get('SERVER_URL', 'http://localhost:5000')

class TelegramAgentBot:
    def __init__(self, token):
        self.token = token
        self.user_sessions = {}

    async def start(self, update: Update, context):
        """Handler for /start command"""
        user_id = str(update.effective_user.id)
        
        try:
            # First initialize agent to ensure session exists
            response_init = requests.post(f'{SERVER_URL}/initialize', json={'user_id': user_id})
            if response_init.status_code != 200:
                await update.message.reply_text("Sorry, there was an issue initializing your agent.")
                return

            # Then clear context and messages
            response_clear_context = requests.post(f'{SERVER_URL}/remove_user_context', 
                                                   json={'user_id': user_id})
            if response_clear_context.status_code != 200:
                logger.error(f"Failed to clear context: {response_clear_context.text}")
                
            response_clear_messages = requests.post(f'{SERVER_URL}/remove_user_messages', 
                                                    json={'user_id': user_id})
            if response_clear_messages.status_code != 200:
                logger.error(f"Failed to clear messages: {response_clear_messages.text}")

            # Finally reinitialize agent with clean state
            response_reinit = requests.post(f'{SERVER_URL}/initialize', json={'user_id': user_id})
            if response_reinit.status_code == 200:
                await update.message.reply_text("Добрый день! Я ассистент медицинской диагностики, не могли бы вы представится и мы можем начать")
            else:
                await update.message.reply_text("Sorry, there was an issue initializing your agent.")
                
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            await update.message.reply_text("An error occurred while starting the bot.")

    async def handle_message(self, update: Update, context):
        """Process incoming messages and send to server"""
        user_id = str(update.effective_user.id)
        message = update.message.text

        try:
            # Send processing message
            processing_message = await update.message.reply_text("Обрабатываю ваш запрос...")

            response = requests.post(f'{SERVER_URL}/message', 
                                     json={'user_id': user_id, 'message': message})
            
            if response.status_code == 200:
                agent_responses = response.json().get('response', [])
                
                # Send each response message
                for resp in agent_responses:
                    await update.message.reply_text(resp.get('content', 'No response'))
            else:
                await update.message.reply_text("Sorry, I couldn't process your message.")
            
            # Delete the processing message
            await processing_message.delete()

        except Exception as e:
            logger.error(f"Message processing error: {e}")
            await update.message.reply_text("An error occurred while processing your message.")
            # Attempt to delete the processing message in case of error
            try:
                await processing_message.delete()
            except:
                pass

def main():
    # Get Telegram bot token from environment
    TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not TOKEN:
        logging.error("No Telegram bot token provided")
        return

    # Create the Application and pass it your bot's token
    application = Application.builder().token(TOKEN).build()

    # Create bot instance
    bot = TelegramAgentBot(TOKEN)

    # Register handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))

    # Start the bot
    logging.info("Starting Telegram bot...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
