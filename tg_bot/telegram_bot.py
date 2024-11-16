import asyncio
import os
import requests
import logging
from telegram import Update
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
        
        # Initialize agent for this user
        try:
            response = requests.post(f'{SERVER_URL}/initialize', json={'user_id': user_id})
            if response.status_code == 200:
                await update.message.reply_text("Welcome! I'm your medical assistant agent. How can I help you today?")
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
            response = requests.post(f'{SERVER_URL}/message', 
                                     json={'user_id': user_id, 'message': message})
            
            if response.status_code == 200:
                agent_responses = response.json().get('response', [])
                
                # Send each response message
                for resp in agent_responses:
                    await update.message.reply_text(resp.get('content', 'No response'))
            else:
                await update.message.reply_text("Sorry, I couldn't process your message.")
        
        except Exception as e:
            logger.error(f"Message processing error: {e}")
            await update.message.reply_text("An error occurred while processing your message.")

    
    async def clear_messages(self, update: Update, context):
        """Clear messages in the chat, including bot messages"""
        user_id = str(update.effective_user.id)
        chat_id = update.effective_chat.id
        message_id = update.message.message_id

        try:
            # Clear messages on the server
            requests.post(f'{SERVER_URL}/remove_user_messages', 
                        json={'user_id': user_id, 'include_bot_messages': True})
            
            # Delete messages starting from the current message and going backwards
            for i in range(message_id, message_id - 100, -1):
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=i)
                except Exception as e:
                    # Skip if message can't be deleted (already deleted or too old)
                    continue

            # Send and then delete a confirmation message
            confirmation = await update.message.reply_text("Messages cleared.")
            await asyncio.sleep(2)  # Wait 2 seconds
            try:
                await confirmation.delete()
            except Exception as e:
                logger.warning(f"Could not delete confirmation message: {e}")

        except Exception as e:
            logger.error(f"Clear messages error: {e}")
            await update.message.reply_text("An error occurred while clearing messages.")

    

    async def clear_context(self, update: Update, context):
        """Clear user context"""
        user_id = str(update.effective_user.id)
        try:
            response = requests.post(f'{SERVER_URL}/remove_user_context', 
                                     json={'user_id': user_id})
            
            if response.status_code == 200:
                await update.message.reply_text("Your conversation context has been cleared.")
            else:
                await update.message.reply_text("Sorry, could not clear context.")
        
        except Exception as e:
            logger.error(f"Clear context error: {e}")
            await update.message.reply_text("An error occurred while clearing context.")

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
    application.add_handler(CommandHandler("clear_messages", bot.clear_messages))
    application.add_handler(CommandHandler("clear_context", bot.clear_context))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))

    # Start the bot
    logging.info("Starting Telegram bot...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
