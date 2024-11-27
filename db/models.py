from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    external_id = Column(String(50), unique=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    sessions = relationship("Session", back_populates="user")
    medical_records = relationship("MedicalRecord", back_populates="user")

class Session(Base):
    __tablename__ = 'sessions'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    is_active = Column(Boolean, default=True)
    current_agent = Column(String(50))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_interaction = Column(DateTime, default=datetime.datetime.utcnow)
    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session")
    images = relationship("Image", back_populates="session")

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('sessions.id'))
    role = Column(String(20))  # user, assistant, system, tool
    content = Column(Text)
    visible_to_user = Column(Boolean, default=True)
    message_metadata = Column(JSON)  # Renamed from metadata to message_metadata
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    session = relationship("Session", back_populates="messages")

class Image(Base):
    __tablename__ = 'images'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('sessions.id'))
    image_data = Column(Text)  # Base64 encoded image
    interpretation = Column(Text)
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    session = relationship("Session", back_populates="images")

class MedicalRecord(Base):
    __tablename__ = 'medical_records'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    data_type = Column(String(50))  # symptoms, diagnosis, etc.
    data = Column(JSON)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    user = relationship("User", back_populates="medical_records")