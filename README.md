# Medical Assistant API

## API Endpoints

### Initialize Agent
```bash
curl -X POST http://localhost:5000/initialize \
     -H "Content-Type: application/json" \
     -d '{"user_id": "user123"}'
```

### Send Message
```bash
curl -X POST http://localhost:5000/message \
     -H "Content-Type: application/json" \
     -d '{
         "user_id": "user123", 
         "message": "I have been experiencing chest pain and shortness of breath."
     }'
```

### Remove Patient Data
```bash
curl -X POST http://localhost:5000/remove_user_context \
     -H "Content-Type: application/json" \
     -d '{"user_id": "user123"}'
```

### Remove User Messages
```bash
curl -X POST http://localhost:5000/remove_user_messages \
     -H "Content-Type: application/json" \
     -d '{"user_id": "user123"}'
```

## Setup and Running

### Prerequisites
- Python 3.8+
- Required dependencies listed in requirements.txt

### Installation
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up environment variables for OpenRouter API
4. Run the application: `python app.py`

## Environment Variables

The following environment variables are used in the project:

### OpenRouter Configuration
- `OPENROUTER_BASE_URL`: Base URL for OpenRouter API
- `OPENROUTER_API_KEY`: API key for OpenRouter

### Telegram Bot Configuration
- `SERVER_URL`: URL of the server (default: http://localhost:5000)
- `TELEGRAM_BOT_TOKEN`: Token for the Telegram bot

### User Configuration
- `USER_ID`: User identifier

### Usage

To run the project, set these environment variables:

```bash
export OPENROUTER_BASE_URL=your_openrouter_base_url
export OPENROUTER_API_KEY=your_openrouter_api_key
export SERVER_URL=your_server_url
export TELEGRAM_BOT_TOKEN=your_telegram_bot_token
export USER_ID=your_user_id
