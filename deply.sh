#!/bin/bash

# Create and activate virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt

# Run the telegram bot in the background
echo "Starting Telegram bot..."
python tg_bot/telegram_bot.py &

# Run the main app
echo "Starting main application..."
python app.py