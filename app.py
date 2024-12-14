import traceback
import requests
from config import IMAGE_INTERPRETATOR_MODEL, IMAGE_INTERPRETATOR_PROMPT
from db.models import Image, MedicalRecord, Message, Session, User
from flask import Flask, request, jsonify
from agents import AgentContainer
from db.database import DatabaseManager
from swarm import Swarm
from datetime import datetime, UTC
import threading
import os
from openai import OpenAI
import logging
from typing import List, Dict
import hashlib
import httpx

import logging

# Configure logging once, at the module level
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('medical_app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
app = Flask(__name__)

# Initialize database manager
db_manager = DatabaseManager('sqlite:///medical_app.db')
db_manager.init_db()

# Dictionary to store AgentContainer instances per user_id
agent_containers = {}
agent_lock = threading.Lock()

# Create HTTP client with proxy configuration
http_client = httpx.Client(
    proxies={
        "http://": "socks5://127.0.0.1:1080",
        "https://": "socks5://127.0.0.1:1080"
    }
)

# Configure OpenAI with custom HTTP client
client = OpenAI(
    base_url=os.environ.get("OPENROUTER_BASE_URL"),
    api_key=os.environ.get("OPENROUTER_API_KEY"),
    http_client=http_client
)

swarm = Swarm()
swarm.client = client

MESSAGE_BUFFER_SIZE = 10  # or whatever size you want

def get_agent_container(external_user_id: str) -> AgentContainer:
    """Get or create AgentContainer for user"""
    logger.info(f"Getting agent container for user: {external_user_id}")

    with agent_lock:
        logger.info("Acquired agent_lock")
        try:
            if external_user_id not in agent_containers:
                logger.info("Creating new AgentContainer")
                agent_containers[external_user_id] = AgentContainer(external_user_id, db_manager)
                logger.info("Created new AgentContainer")
            else:
                logger.info("Using existing AgentContainer")

            return agent_containers[external_user_id]
        except Exception as e:
            logger.error(f"Error in get_agent_container: {str(e)}")
            raise

def get_patient_data_context(db_accessor_agent) -> str:
    """Helper function to format patient data context"""
    medical_history = db_accessor_agent.get_medical_history()
    return f"Patient Data:\n{medical_history}"

def process_single_image(image_data: str) -> str:
    """Direct OpenRouter API call for image interpretation"""
    try:
        response = requests.post(
            os.environ.get("OPENROUTER_BASE_URL") + "/chat/completions",
            headers={
                "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY')}",
                "Content-Type": "application/json"
            },
            json={
                "model": IMAGE_INTERPRETATOR_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": IMAGE_INTERPRETATOR_PROMPT
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
                            }
                        ]
                    }
                ]
            }
        )

        if response.status_code == 200:
            # Add debug logging
            logger.debug(f"OpenRouter API response: {response.json()}")
            try:
                return response.json()['choices'][0]['message']['content']
            except KeyError as ke:
                logger.error(f"Unexpected response structure. Response: {response.json()}")
                logger.error(f"KeyError: {ke}")
                return None
        else:
            logger.error(f"OpenRouter API error: {response.text}")
            return None

    except Exception as e:
        logger.error(f"Error in image processing: {str(e)}")
        logger.error(f"Full exception: {traceback.format_exc()}")
        return None

@app.route('/process_images', methods=['POST'])
def process_images():
    data = request.get_json()
    external_user_id = data.get('user_id')
    images = data.get('images', [])

    if not external_user_id or not images:
        return jsonify({'error': 'user_id and images are required'}), 400

    try:
        agent_container = get_agent_container(external_user_id)
        interpretations = []

        for image_data in images:
            # Save image to database
            image_record = agent_container.db_accessor_agent.save_image(
                agent_container.user_context['session_id'],
                image_data
            )

            # Get medical interpretation
            interpretation = process_single_image(image_data)

            if interpretation:
                # Save interpretation
                agent_container.db_accessor_agent.save_image_interpretation(
                    image_record['image_id'],
                    interpretation
                )

                # Update medical record if interpretation contains medical info
                agent_container.db_accessor_agent.update_medical_record(
                    f"image_analysis_{image_record['image_id']}",
                    interpretation
                )

                interpretations.append(interpretation)

        # Generate response
        response_message = {
            'role': 'assistant',
            'content': "Интерпретация изображения" +
                      ("".join(interpretations) if interpretations
                       else "В изображениях не обнаружено значимой медицинской информации.")
        }

        # Save assistant's response
        agent_container.db_accessor_agent.save_message(
            agent_container.user_context['session_id'],
            response_message['role'],
            response_message['content'],
            visible_to_user=True,
            message_metadata={
                'timestamp': datetime.now(UTC).isoformat()
            }
        )

        return jsonify({
            'response': [response_message]
        }), 200

    except Exception as e:
        logger.error(f"Error processing images: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/message', methods=['POST'])
def handle_message():
    data = request.get_json()
    external_user_id = data.get('user_id')
    message = data.get('message')

    if not external_user_id or not message:
        return jsonify({'error': 'user_id and message are required'}), 400

    agent_container = get_agent_container(external_user_id)

    try:
        # First save the user's message
        if isinstance(message, str):
            message = {"role": "user", "content": message}

        # Save user message to DB
        agent_container.db_accessor_agent.save_message(
            agent_container.user_context['session_id'],
            message["role"],
            message["content"],
            visible_to_user=True,
            message_metadata={
                'timestamp': datetime.now(UTC).isoformat()
            }
        )

        # Get recent message history including the just-saved message
        with agent_container.db_accessor_agent.db_manager.get_db_session() as session:
            recent_messages = session.query(Message).filter(
                Message.session_id == agent_container.user_context['session_id'],
                Message.visible_to_user == True,
                Message.role != 'tool',
                Message.content.isnot(None),
                Message.content != ''
            ).order_by(
                Message.created_at.desc()
            ).limit(MESSAGE_BUFFER_SIZE).all()

            # Convert to format for swarm excluding tool messages
            conversation_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in reversed(recent_messages)  # Reverse to get chronological order
            ]

        # Get patient data context and prepend as system message
        patient_data_context = get_patient_data_context(agent_container.db_accessor_agent)
        messages = [{"role": "system", "content": patient_data_context}] + conversation_messages

        logger.debug(f"Sending messages to LLM: {messages}")

        # Get current agent
        current_agent = agent_container.current_agent

        # Run conversation
        response = swarm.run(
            agent=current_agent,
            messages=messages,
            stream=False,
            debug=True
        )

        # Handle response and save ALL messages
        visible_messages = []
        if response and response.messages:
            for msg in response.messages:
                # Save ALL messages to DB including tool messages
                visible_to_user = msg.get('role') != 'tool'
                agent_container.db_accessor_agent.save_message(
                    agent_container.user_context['session_id'],
                    msg.get('role', 'assistant'),
                    msg.get('content', ''),
                    visible_to_user=visible_to_user,
                    message_metadata={
                        'agent': current_agent.name,
                        'timestamp': datetime.now(UTC).isoformat()
                    }
                )

                # Only add visible messages to response
                if visible_to_user and msg.get('content'):
                    visible_messages.append({
                        'role': msg.get('role', 'assistant'),
                        'content': msg.get('content')
                    })

            # Handle agent handoff
            if response and response.agent != current_agent:
                handoff_message = {
                    'role': 'assistant',
                    'content': f"Transferring you to {response.agent.name}"
                }
                # Save handoff message
                agent_container.db_accessor_agent.save_message(
                    agent_container.user_context['session_id'],
                    'assistant',
                    handoff_message['content'],
                    visible_to_user=False,
                    message_metadata={
                        'handoff_from': current_agent.name,
                        'handoff_to': response.agent.name,
                        'timestamp': datetime.now(UTC).isoformat()
                    }
                )

                # Update the agent in the container
                agent_container.current_agent = response.agent

        return jsonify({'response': visible_messages}), 200

    except Exception as e:
        logger.error(f"Error processing message: {str(e.with_traceback)}")
        return jsonify({'error': str(e)}), 500

@app.route('/initialize', methods=['POST'])
def initialize_user():
    data = request.get_json()
    external_user_id = data.get('user_id')

    logger.info(f"Initializing user: {external_user_id}")

    if not external_user_id:
        logger.error("No user_id provided")
        return jsonify({'error': 'user_id is required'}), 400

    try:
        logger.info("Getting agent container")
        agent_container = get_agent_container(external_user_id)
        logger.info("Got agent container")

        return jsonify({
            'status': 'success',
            'message': f'Session initialized for user {external_user_id}',
            'session_id': agent_container.user_context['session_id']
        }), 200

    except Exception as e:
        logger.error(f"Error initializing user: {str(e)}", exc_info=True)  # Added exc_info for stack trace
        return jsonify({'error': str(e)}), 500

@app.route('/clear', methods=['POST'])
def clear_user_data():
    """Clear all user data and start fresh"""
    data = request.get_json()
    external_user_id = data.get('user_id')

    if not external_user_id:
        return jsonify({'error': 'user_id is required'}), 400

    try:
        with db_manager.get_db_session() as session:
            # Find user
            user = session.query(User).filter_by(external_id=external_user_id).first()
            if not user:
                return jsonify({'status': 'success', 'message': 'No data to clear'}), 200

            # Delete all related data
            session.query(Message).filter(
                Message.session_id.in_(
                    session.query(Session.id).filter_by(user_id=user.id)
                )
            ).delete(synchronize_session=False)

            session.query(Image).filter(
                Image.session_id.in_(
                    session.query(Session.id).filter_by(user_id=user.id)
                )
            ).delete(synchronize_session=False)

            session.query(Session).filter_by(user_id=user.id).delete()
            session.query(MedicalRecord).filter_by(user_id=user.id).delete()

            # Remove from active containers
            with agent_lock:
                if external_user_id in agent_containers:
                    del agent_containers[external_user_id]

        return jsonify({
            'status': 'success',
            'message': f'All data cleared for user {external_user_id}'
        }), 200

    except Exception as e:
        logger.error(f"Error clearing user data: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Ensure database tables are created
    db_manager.init_db()

    app.run(host='0.0.0.0', port=5000)
