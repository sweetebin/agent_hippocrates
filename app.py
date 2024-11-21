from flask import Flask, request, jsonify
from agents import AgentContainer
from shared_context import SharedContext
from swarm import Swarm
from datetime import datetime
import threading
import os
from openai import OpenAI
import logger

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

agent_messages_buffer = 10

# In app.py, modify the process_image endpoint:

@app.route('/process_image', methods=['POST'])
def process_image():
    data = request.get_json()
    user_id = data.get('user_id')
    base64_image = data.get('image')

    if not user_id or not base64_image:
        return jsonify({'error': 'user_id and image are required'}), 400

    with agent_lock:
        if user_id not in agent_containers:
            agent_containers[user_id] = AgentContainer(user_id)
    
    agent_container = agent_containers[user_id]
    
    
    # Create message for image processing agent
    image_message = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                }
            ]
        }
    ]

    # Get image analysis from Image Processing Agent
    image_analysis = swarm.run(
        agent=agent_container.image_processing_agent,
        messages=image_message,
        stream=False,
        debug=True
    )

    # Forward findings to Medical Assistant
    if image_analysis and image_analysis.messages:
        # Extract the analysis
        analysis_content = image_analysis.messages[-1].get('content', '')
        cached_messages = agent_container.shared_context.get_full_message_history()
        # Create message for medical assistant
        cached_messages.append({
            "role": "system",
            "content": f"<Анализ изображения от пользователя>{analysis_content}\n\nУчти данные и запиши, если релевантны, в этом же сообщении продолжи общение с пользователем (либо продолжай опрос либо переводи к врачу)</Анализ изображения от пользователя>"
        })
        
        
        
        # Get medical assistant's response
        response = swarm.run(
            agent=agent_container.medical_assistant_agent,
            messages=cached_messages,
            stream=False,
            debug=True
        )

        # Extract response messages, ensuring we only include messages with content
        response_messages = []
        if response and response.messages:
            for msg in response.messages:
                if msg.get('role') != 'tool' and msg.get('content'):
                            response_messages.append({
                                'role': msg.get('role', 'assistant'),
                                'content': msg.get('content')
                            })
        
        return jsonify({'response': response_messages}), 200
        
    return jsonify({'response': [{'role': 'assistant', 'content': 'Не удалось обработать изображение.'}]}), 200



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

    # Normalize message to dictionary if it's a string
    if isinstance(message, str):
        message = {"role": "user", "content": message}

    # Check and update message history based on role and content
    if message.get('role') != 'tool' and message.get('content'):
        shared_context.update_message_history(message)
    
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
            messages=messages[-agent_messages_buffer:],
            stream=False,
            debug=True
        )
        
        if response and response.messages:
            # Process response messages
            for msg in response.messages:
                # Check role and content before updating
                if msg.get('role') != 'tool' and msg.get('content'):
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
                for msg in response.messages if msg["role"] != "tool" and msg.get("content")
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

@app.route('/remove_user_context', methods=['POST'])
def remove_user_context():
    data = request.get_json()
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400

    with agent_lock:
        if user_id not in agent_containers:
            # Treat as success since there's no context to remove
            return jsonify({'status': 'success', 'message': f"No context to remove for user_id {user_id}"}), 200

    agent_container = agent_containers[user_id]
    shared_context = agent_container.shared_context

    # Remove patient data using SharedContext method
    result = shared_context.remove_all_user_context()

    return jsonify(result), 200


@app.route('/remove_user_messages', methods=['POST'])
def remove_user_messages():
    data = request.get_json()
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400

    with agent_lock:
        if user_id not in agent_containers:
            # Treat as success since there's nothing to remove
            return jsonify({'status': 'success', 'message': f"No messages to remove for user_id {user_id}"}), 200

    agent_container = agent_containers[user_id]
    shared_context = agent_container.shared_context

    # Remove user messages using SharedContext method
    result = shared_context.remove_user_messages()

    return jsonify(result), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
