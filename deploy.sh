#!/bin/bash

# Install proxychains if not installed
if ! command -v proxychains4 &> /dev/null; then
    echo "Installing proxychains..."
    sudo apt install -y proxychains4

    # Configure proxychains
    sudo bash -c 'echo "socks5 127.0.0.1 1080" >> /etc/proxychains4.conf'
fi

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

# Run the telegram bot in the background with proxychains and save its PID
echo "Starting Telegram bot with proxy..."
proxychains4 python tg_bot/telegram_bot.py > telegram_bot.log 2>&1 &
TG_BOT_PID=$!

# Wait a few seconds to ensure the bot starts properly
sleep 3

# Run the main app with proxychains
echo "Starting main application with proxy..."
proxychains4 python app.py > app.log 2>&1

# If the main app exits, kill the telegram bot
kill $TG_BOT_PID