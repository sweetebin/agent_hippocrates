import requests
import json
import os

def perform_ai_internet_search(query):
    """Performs an intelligent internet search with natural language.
    Expected params:
    -query: String"""
    
    perplexity_api = os.environ.get("PERPLEXICA_API_URL")
    
    request_payload = {
        "chatModel": {
            "provider": "custom_openai",
            "model": "meta-llama/llama-3.2-3b-instruct:free",
            "customOpenAIBaseURL": os.environ.get("OPENROUTER_BASE_URL"),
            "customOpenAIKey": os.environ.get("OPENROUTER_API_KEY")
        },
        "optimizationMode": "speed",
        "focusMode": "webSearch",
        "query": query,  # Use the provided query argument
        "history": [
            ["human", "Hi, how are you?"],
            ["assistant", "I am doing well, how can I help you today?"]
        ]
    }
    
    # Headers for the request
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        # Make the POST request to the API
        response = requests.post(perplexity_api, headers=headers, data=json.dumps(request_payload))
        
        # Check if the request was successful
        if response.status_code == 200:
            response_data = response.json()
            # Extract and print the message
            message = response_data.get("message")
            # Extract and print the sources
            sources = [
                {
                    "title": source["metadata"]["title"],
                    "url": source["metadata"]["url"]
                }
                for source in response_data.get("sources", [])
            ]
            # return message, sources
            return message
        else:
            return f"Error: {response.status_code}", None
    except Exception as e:
        return f"An error occurred: {str(e)}", None
    
    