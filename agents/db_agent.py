from swarm import Agent
from typing import Any, Dict, List, Optional
from datetime import UTC, datetime
from db.models import User, Session, Message, Image, MedicalRecord
from pydantic import Field
import logging


logger = logging.getLogger(__name__)

class DBAccessorAgent(Agent):
    # Declare db_manager as a model field
    db_manager: Any = Field(default=None, exclude=True)

    def __init__(self, db_manager, user_context):
        logger.info("Initializing DBAccessorAgent")
        logger.info(f"Received db_manager: {db_manager}")

        super().__init__(
            name="DB Accessor",
            instructions="Internal agent for database operations. Do not interact with users directly.",
            model="gpt-4",
            functions=[
                self.get_user_context,
                self.save_message,
                self.save_image_interpretation,
                self.update_medical_record,
                self.get_medical_history,
                self.create_or_get_session,
                self.save_image,
                self.get_pending_images,
                self.mark_image_processed
            ]
        )
        # Set db_manager after super().__init__
        object.__setattr__(self, 'db_manager', db_manager)
        object.__setattr__(self, 'user_context', user_context)
        logger.info("Completed DBAccessorAgent initialization")

    def get_user_context(self, external_user_id: str) -> Dict:
        """Get user's current context including active session and medical records"""
        with self.db_manager.get_db_session() as session:
            user = session.query(User).filter_by(external_id=external_user_id).first()
            if not user:
                return {"error": "User not found"}

            active_session = session.query(Session).filter_by(
                user_id=user.id,
                is_active=True
            ).first()

            medical_records = session.query(MedicalRecord).filter_by(
                user_id=user.id
            ).all()

            return {
                "user_id": user.id,
                "session_id": active_session.id if active_session else None,
                "medical_records": [
                    {"type": record.data_type, "data": record.data}
                    for record in medical_records
                ]
            }

    def create_or_get_session(self, external_user_id: str) -> Dict:
        """Create new session or get active session for user"""
        with self.db_manager.get_db_session() as session:
            # Find or create user
            user = session.query(User).filter_by(external_id=external_user_id).first()
            if not user:
                user = User(external_id=external_user_id)
                session.add(user)
                session.flush()

            # Deactivate any existing active sessions
            session.query(Session).filter_by(
                user_id=user.id,
                is_active=True
            ).update({"is_active": False})

            # Create new session
            new_session = Session(
                user_id=user.id,
                is_active=True,
                current_agent="Medical Assistant"
            )
            session.add(new_session)
            session.flush()

            return {
                "session_id": new_session.id,
                "user_id": user.id
            }

    def save_message(self, session_id: int, role: str, content: str, visible_to_user: bool = True, message_metadata: Dict = None) -> Dict:
        """Save message to database"""
        with self.db_manager.get_db_session() as session:
            message = Message(
                session_id=session_id,
                role=role,
                content=content,
                visible_to_user=visible_to_user,
                message_metadata=message_metadata or {}  # Match the column name in Message model
            )
            session.add(message)
            session.query(Session).filter_by(id=session_id).update({
                "last_interaction": datetime.now(UTC)
            })
            return {"status": "success", "message_id": message.id}

    def save_image(self, session_id: int, image_data: str) -> Dict:
        """Save new image to database"""
        with self.db_manager.get_db_session() as session:
            image = Image(
                session_id=session_id,
                image_data=image_data,
                processed=False
            )
            session.add(image)
            session.flush()
            return {"status": "success", "image_id": image.id}

    def save_image_interpretation(self, image_id: int, interpretation: str) -> Dict:
        """Save interpretation for processed image"""
        with self.db_manager.get_db_session() as session:
            image = session.query(Image).filter_by(id=image_id).first()
            if not image:
                return {"error": "Image not found"}

            image.interpretation = interpretation
            image.processed = True
            return {"status": "success", "image_id": image_id}

    def get_pending_images(self, session_id: int) -> List[Dict]:
        """Get unprocessed images for session"""
        with self.db_manager.get_db_session() as session:
            images = session.query(Image).filter_by(
                session_id=session_id,
                processed=False
            ).all()
            return [
                {"id": img.id, "image_data": img.image_data}
                for img in images
            ]

    def mark_image_processed(self, image_id: int) -> Dict:
        """Mark image as processed"""
        with self.db_manager.get_db_session() as session:
            image = session.query(Image).filter_by(id=image_id).first()
            if not image:
                return {"error": "Image not found"}

            image.processed = True
            return {"status": "success", "image_id": image_id}

    def update_medical_record(self, key_name : str, data: str) -> Dict:
        """
    Update or create a medical record in the database.

    Parameters:
        key_name (str): The name of the data field to update or create. 
                        This should be a descriptive key in English (e.g., 'blood_pressure', 'allergies').
        data (str): The string value to be stored or updated for the specified key_name.
    """
        with self.db_manager.get_db_session() as session:
            record = session.query(MedicalRecord).filter_by(
                user_id=self.user_context['user_id'],
                data_type= key_name
            ).first()

            if record:
                record.data = data
            else:
                record = MedicalRecord(
                    user_id= self.user_context['user_id'],
                    data_type=key_name,
                    data=data
                )
                session.add(record)

            session.flush()
            return {"status": "success", "record_id": record.id}

    def get_medical_history(self) -> Dict:
        """Get all medical records for user"""
        with self.db_manager.get_db_session() as session:
            records = session.query(MedicalRecord).filter_by(user_id=self.user_context['user_id']).all()
            return {
                "medical_history": [
                    {
                        "type": record.data_type,
                        "data": record.data,
                        "created_at": record.created_at.isoformat()
                    }
                    for record in records
                ]
            }
