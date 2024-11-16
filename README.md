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
