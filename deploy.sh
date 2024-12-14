#!/bin/bash

# Create and activate virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install requirements
echo "Installing main requirements..."
pip install Flask gunicorn openai dataclasses python-telegram-bot requests sqlalchemy pillow

# Verify installation was successful
if [ $? -ne 0 ]; then
    echo "Error: Failed to install requirements"
    exit 1
fi

# Run the telegram bot normally in the background
echo "Starting Telegram bot..."
python tg_bot/telegram_bot.py > telegram_bot.log 2>&1 &
TG_BOT_PID=$!

# Wait a few seconds to ensure the bot starts properly
sleep 3

# Run the main app with proxy
echo "Starting main application with proxy..."
export https_proxy="socks5://127.0.0.1:1080"
export http_proxy="socks5://127.0.0.1:1080"
python app.py > app.log 2>&1

# If the main app exits, kill the telegram bot
kill $TG_BOT_PID