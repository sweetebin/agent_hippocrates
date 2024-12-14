#!/bin/bash

# Check if virtual environment exists, create only if it doesn't
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
echo "Installing main requirements..."
pip install Flask gunicorn openai dataclasses python-telegram-bot requests sqlalchemy pillow httpx

# Run the telegram bot normally in the background
echo "Starting Telegram bot..."
nohup python tg_bot/telegram_bot.py > telegram_bot.log 2>&1 &
TG_BOT_PID=$!

sleep 3

# Run Flask app normally
echo "Starting main application..."
nohup python app.py > app.log 2>&1 &
APP_PID=$!

echo "Services started:"
echo "Telegram bot PID: $TG_BOT_PID"
echo "App PID: $APP_PID"

trap "kill $TG_BOT_PID $APP_PID; exit" SIGINT SIGTERM

wait $TG_BOT_PID $APP_PID