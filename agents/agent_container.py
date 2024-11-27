from swarm import Agent
from .db_agent import DBAccessorAgent
from config import *
import logging
from db.models import User, Session


logger = logging.getLogger(__name__)

class AgentContainer:
    def __init__(self, user_id: str, db_manager):
        logger.info(f"Initializing AgentContainer for user_id: {user_id}")

        # Create initial session and get user context
        with db_manager.get_db_session() as session:
            user = session.query(User).filter_by(external_id=user_id).first()
            if not user:
                user = User(external_id=user_id)
                session.add(user)
                session.flush()

            active_session = session.query(Session).filter_by(
                user_id=user.id,
                is_active=True
            ).first()

            if not active_session:
                active_session = Session(user_id=user.id, is_active=True)
                session.add(active_session)
                session.flush()

            # Store user context
            self.user_context = {
                'user_id': user.id,
                'session_id': active_session.id,
                'external_user_id': user_id
            }

        # Initialize DB Accessor with user context
        self.db_accessor_agent = DBAccessorAgent(db_manager, self.user_context)
        
        def transfer_to_doctor():
            """Transfers to doctor agent"""
            return self.doctor_agent

        def transfer_to_medical_assistant():
            """Transfers to medical assistant agent"""
            return self.medical_assistant_agent

            
        # Add DB operations as available functions
        shared_context_functions = [
            self.db_accessor_agent.update_medical_record,
            self.db_accessor_agent.get_medical_history,
            transfer_to_doctor,
            transfer_to_medical_assistant
        ]

        self.image_processing_agent = Agent(
            name="Интерпретатор изображений",
            instructions="""Вы интерпретатор пользовательских изображений, вам нужно интерпретировать данные в текст для дальнейшей обработки
Отвечай на русском""",
            model="openai/gpt-4o",
            functions=[self.db_accessor_agent.save_image_interpretation]
        )
        
        self.medical_assistant_agent = Agent(
            name="Medical Assistant",
            instructions=MEDICAL_ASSISTANT_BASE_INSTRUCTION,
            model=MEDICAL_ASSISTANT_MODEL,
            functions=shared_context_functions
        )

        self.doctor_agent = Agent(
            name="Doctor",
            instructions="""Вы - эндокринолог. Ваша роль:
1. Просмотр данных пациента
2. Фокус на проблемах, связанных с эндокринной системой
3. Предоставление предварительных рекомендаций на основе симптомов и данных
4. Используй персональный подход к пациенту
5. Никогда не направляйте к врачу, вы - ВРАЧ
Используй грамотный русский язык.
Начинай диалог проактивно""",
            model="openai/chatgpt-4o-latest",
            functions=shared_context_functions
        )
