import sqlite3
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
import os

@dataclass
class SharedContext:
    """Shared context with multi-user support using SQLite for persistence."""
    
    user_id: str  # User ID will be sent to the service
    patient_data: str = "Empty"
    max_context_messages: int = 10  # Only used for agent context window
    db_path: str = "shared_context.db"
    
    def __post_init__(self):
        """Initialize the SQLite database and load patient data."""
        self._init_database()
        self.patient_data = self._get_context_value("patient_data", "")
    
    def _init_database(self):
        """Create the database and necessary tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create tables with user_id for multi-user support
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_context (
                    user_id TEXT,
                    key TEXT,
                    value TEXT,
                    PRIMARY KEY (user_id, key)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS message_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    role TEXT,
                    content TEXT,
                    sender TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    def _save_context_value(self, key: str, value):
        """Save a context value to the database for the current user."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_context (user_id, key, value) VALUES (?, ?, ?)
            ''', (self.user_id, key, str(value)))
            conn.commit()
    
    def _get_context_value(self, key: str, default=None):
        """Retrieve a context value from the database for the current user."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM user_context WHERE user_id = ? AND key = ?', (self.user_id, key))
            result = cursor.fetchone()
            return result[0] if result else default
    
    def append_patient_data(self, additional_data: str) -> dict:
        """
        Appends new data to the existing patient data for the current user.
        
        Args:
            additional_data (str): New information to add to patient data.
        
        Returns:
            dict: Confirmation of data update with status and details.
        """
        current_data = self._get_context_value("patient_data", "") or ""
        new_data = f"{current_data}\n{additional_data}" if current_data else additional_data
        self.patient_data = new_data
        self._save_context_value("patient_data", new_data)
        return {
            "status": "success",
            "message": "Patient data updated",
            "added_data": additional_data
        }
    
    def replace_patient_data(self, new_data: str) -> dict:
        """
        Replaces the entire patient data for the current user.
        
        Args:
            new_data (str): Complete new patient data to replace existing data.
        
        Returns:
            dict: Confirmation of data replacement with status and details.
        """
        self.patient_data = new_data
        self._save_context_value("patient_data", new_data)
        return {
            "status": "success", 
            "message": "Patient data completely replaced",
            "new_data": new_data
        }
    
    def update_message_history(self, new_message: Dict) -> None:
        """Saves a new message to the history for the current user."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Insert new message with sender and user_id
            cursor.execute('''
                INSERT INTO message_history (user_id, role, content, sender) VALUES (?, ?, ?, ?)
            ''', (
                self.user_id,
                new_message.get('role', ''),
                new_message.get('content', ''),
                new_message.get('sender', 'user' if new_message.get('role') == 'user' else 'assistant')
            ))
            
            conn.commit()
    
    def get_full_message_history(self) -> List[Dict]:
        """Retrieves all messages from history for the current user."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT role, content, sender 
                FROM message_history 
                WHERE user_id = ?
                ORDER BY timestamp ASC
            ''', (self.user_id,))
            return [
                {
                    "role": row[0],
                    "content": row[1],
                    "sender": row[2]
                }
                for row in cursor.fetchall()
            ]
    
    def get_full_context(self) -> str:
        """Returns a string representation of the full context."""
        context_parts = [
            f"User ID: {self.user_id}",
            f"Patient Data: {self.patient_data}",
            f"Max Context Messages: {self.max_context_messages}"
        ]
        return "\n".join(context_parts)
    
    def update_shared_notes(self, key: str, value: Any) -> dict:
        """
        Updates a shared note in the database for the current user.
        
        Args:
            key (str): The key for the shared note.
            value (Any): The value to store for the given key.
        
        Returns:
            dict: Confirmation of note update with status and details.
        """
        self._save_context_value(f"shared_note_{key}", value)
        return {
            "status": "success",
            "message": f"Shared note updated for key: {key}",
            "key": key,
            "value": value
        }
    
    def update_last_handoff(self, handoff_time: datetime) -> dict:
        """
        Updates the timestamp of the last agent handoff for the current user.
        
        Args:
            handoff_time (datetime): The timestamp of the last agent handoff.
        
        Returns:
            dict: Confirmation of handoff time update with status and details.
        """
        self._save_context_value("last_handoff", handoff_time.isoformat())
        return {
            "status": "success",
            "message": "Last handoff time updated",
            "handoff_time": handoff_time.isoformat()
        }
    
    def update_current_agent(self, agent_name: str) -> dict:
        """
        Updates the current agent handling the context for the current user.
        
        Args:
            agent_name (str): The name of the current agent.
        
        Returns:
            dict: Confirmation of current agent update with status and details.
        """
        self._save_context_value("current_agent", agent_name)
        return {
            "status": "success",
            "message": "Current agent updated",
            "agent_name": agent_name
        }
