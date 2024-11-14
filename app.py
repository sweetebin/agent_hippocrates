from flask import Flask, request, jsonify
from agents import AgentContainer
from shared_context import SharedContext
from swarm import Swarm
from datetime import datetime
import threading
import os
from openai import OpenAI

app = Flask(__name__)

# Dictionary to store AgentContainer instances per user_id
agent_containers = {}
agent_lock = threading.Lock()

client = OpenAI(
        base_url=os.environ.get("OPENROUTER_BASE_URL"),
        api_key=os.environ.get("OPENROUTER_API_KEY")  # Use environment variable
    )

swarm = Swarm()
swarm.client = client

@app.route('/message', methods=['POST'])
def handle_message():
    data = request.get_json()
    user_id = data.get('user_id')
    message = data.get('message')

    if not user_id or not message:
        return jsonify({'error': 'user_id and message are required'}), 400

    with agent_lock:
        if user_id not in agent_containers:
            agent_containers[user_id] = AgentContainer(user_id)
    
    agent_container = agent_containers[user_id]
    shared_context = agent_container.shared_context

    # Append user message to history
    shared_context.update_message_history({"role": "user", "content": message})
    
    # Prepare messages
    messages = shared_context.get_full_message_history()
    if shared_context.patient_data:
        messages.append({
            "role": "system",
            "content": f"Patient Data: {shared_context.patient_data}"
        })
    
    try:
        response = swarm.run(
            agent=agent_container.medical_assistant_agent,
            messages=messages,
            stream=False,
            debug=True
        )
        
        if response and response.messages:
            # Process response messages
            for msg in response.messages:
                if msg.get("role") != "tool":
                    shared_context.update_message_history(msg)
            
            # Update current agent and handoff time
            agent_container.shared_context.update_last_handoff(datetime.now())
            agent_container.shared_context.update_current_agent(response.agent.name)
            
            # Extract assistant messages for response
            assistant_messages = [
                {
                    "role": msg["role"],
                    "content": msg["content"]
                }
                for msg in response.messages if msg["role"] != "tool"
            ]
            
            return jsonify({'response': assistant_messages}), 200
        else:
            return jsonify({'response': 'No response received from agent.'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/initialize', methods=['POST'])
def initialize_agent():
    data = request.get_json()
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400

    with agent_lock:
        if user_id not in agent_containers:
            agent_containers[user_id] = AgentContainer(user_id)
    
    agent_container = agent_containers[user_id]
    shared_context = agent_container.shared_context

    # Retrieve initial agent from DB or use the first one
    
    initial_agent = agent_container.medical_assistant_agent
   
    
    shared_context.update_current_agent(initial_agent)
    
    return jsonify({'message': f'Agent initialized for user_id {user_id} with agent {initial_agent}.'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
