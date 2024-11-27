# app.py
from db.models import Image, MedicalRecord, Message, Session, User
from flask import Flask, request, jsonify
from agents import AgentContainer
from db.database import DatabaseManager
from swarm import Swarm
from datetime import UTC, datetime
import threading
import os
from openai import OpenAI
import logging
from typing import List, Dict

logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize database manager
db_manager = DatabaseManager('sqlite:///medical_app.db')
db_manager.init_db()

# Dictionary to store AgentContainer instances per user_id
agent_containers = {}
agent_lock = threading.Lock()

client = OpenAI(
    base_url=os.environ.get("OPENROUTER_BASE_URL"),
    api_key=os.environ.get("OPENROUTER_API_KEY")
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


def process_single_image(agent_container: AgentContainer, image_data: str) -> Dict:
    """Process single image and save interpretation"""
    # Save image to database
    image_save_result = agent_container.db_accessor_agent.save_image(
        agent_container.user_context['session_id'],
        image_data
    )

    if "error" in image_save_result:
        return {"error": "Failed to save image"}

    # Create message for image processing agent
    image_message = [{
        "role": "user",
        "content": [{
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
        }]
    }]

    # Get image analysis
    try:
        image_analysis = swarm.run(
            agent=agent_container.image_processing_agent,
            messages=image_message,
            stream=False,
            debug=True
        )

        if image_analysis and image_analysis.messages:
            # Save interpretation
            interpretation = image_analysis.messages[-1].get('content', '')
            agent_container.db_accessor_agent.save_image_interpretation(
                image_save_result["image_id"],
                interpretation
            )
            return {"status": "success", "interpretation": interpretation}
    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        return {"error": str(e)}

@app.route('/process_images', methods=['POST'])
def process_images():
    data = request.get_json()
    external_user_id = data.get('user_id')
    images = data.get('images', [])  # Expect list of base64 images

    if not external_user_id or not images:
        return jsonify({'error': 'user_id and images are required'}), 400

    agent_container = get_agent_container(external_user_id)

    # Save initial response that images are being processed
    agent_container.db_accessor_agent.save_message(
        agent_container.user_context['session_id'],
        "assistant",
        f"Processing {len(images)} images... Please wait.",
        visible_to_user=True
    )

    interpretations = []
    for image in images:
        result = process_single_image(agent_container, image)
        if "error" not in result:
            interpretations.append(result["interpretation"])

    if interpretations:
        # Create message with all interpretations for medical assistant
        combined_analysis = "\n\n".join(interpretations)
        messages = [{
            "role": "system",
            "content": f"Image Analysis Results:\n{combined_analysis}\n\nConsider these findings in your assessment."
        }]

        # Get medical assistant's response
        response = swarm.run(
            agent=agent_container.medical_assistant_agent,
            messages=messages,
            stream=False,
            debug=True
        )

        # Save and return visible messages
        visible_messages = []
        if response and response.messages:
            for msg in response.messages:
                if msg.get('role') != 'tool':
                    # Save to database
                    agent_container.db_accessor_agent.save_message(
                        agent_container.user_context['session_id'],
                        msg.get('role', 'assistant'),
                        msg.get('content', ''),
                        visible_to_user=True
                    )
                    if msg.get('content'):
                        visible_messages.append({
                            'role': msg.get('role', 'assistant'),
                            'content': msg.get('content')
                        })

        return jsonify({'response': visible_messages}), 200

    return jsonify({'error': 'Failed to process images'}), 500


@app.route('/message', methods=['POST'])
def handle_message():
    data = request.get_json()
    external_user_id = data.get('user_id')
    message = data.get('message')

    if not external_user_id or not message:
        return jsonify({'error': 'user_id and message are required'}), 400

    agent_container = get_agent_container(external_user_id)

    try:
        # First, save the user's message
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


        medical_history = agent_container.db_accessor_agent.get_medical_history()

        # Update agent instructions with patient data
        patient_data_context = f"Patient Data: {medical_history.get('medical_history', 'No data available')}"
        
        agent_container.medical_assistant_agent.instructions = agent_container.medical_assistant_agent.instructions + "\n\n" + patient_data_context
        agent_container.doctor_agent.instructions = agent_container.doctor_agent.instructions + "\n\n" + patient_data_context
        
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

            # Convert to format for swarm, excluding tool messages
            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in reversed(recent_messages)  # Reverse to get chronological order
            ]

        logger.debug(f"Sending messages to LLM: {messages}")  # Add logging

        # Get current agent
        current_agent = agent_container.medical_assistant_agent

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
                # Save ALL messages to DB, including tool messages
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
            if response.agent != current_agent:
                handoff_message = {
                    'role': 'assistant',
                    'content': f"Transferring you to {response.agent.name}..."
                }
                visible_messages.append(handoff_message)
                agent_container.db_accessor_agent.save_message(
                    agent_container.user_context['session_id'],
                    'assistant',
                    handoff_message['content'],
                    visible_to_user=True,
                    message_metadata={
                        'handoff_from': current_agent.name,
                        'handoff_to': response.agent.name,
                        'timestamp': datetime.now(UTC).isoformat()
                    }
                )

        return jsonify({'response': visible_messages}), 200

    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
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

        logger.info("Saving initial greeting message")
        agent_container.db_accessor_agent.save_message(
            agent_container.user_context['session_id'],
            "assistant",
            "Greeting message",
            visible_to_user=True
        )
        logger.info("Saved greeting message")

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

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('medical_app.log'),
            logging.StreamHandler()
        ]
    )

    app.run(host='0.0.0.0', port=5000)
