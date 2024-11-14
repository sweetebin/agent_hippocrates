env variables:

OPENROUTER_API_KEY 
OPENROUTER_BASE_URL 
PERPLEXICA_API_URL (optional for perplexica tool)

# Create virtual environment
python -m venv agent_hippocrates

# activate env
source venv/bin/activate

# Install requirements
pip install -r requirements.txt




API фласки

# Initialize agent for a specific user
curl -X POST http://localhost:5000/initialize \
     -H "Content-Type: application/json" \
     -d '{"user_id": "user123"}'


# Send a message to the medical assistant
curl -X POST http://localhost:5000/message \
     -H "Content-Type: application/json" \
     -d '{
         "user_id": "user123", 
         "message": "I have been experiencing chest pain and shortness of breath."
     }'