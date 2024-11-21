import sqlite3
from dataclasses import dataclass
from typing import Dict, List
from datetime import datetime

@dataclass
class SharedContext:
    """Shared context with SQL persistence focusing on patient data and last agent."""
    
    user_id: str
    patient_data: str = ""
    db_path: str = "shared_context.db"
    max_context_messages: int = 10
    
    def __post_init__(self):
        """Initialize database and load patient data."""
        self._init_database()
        self.patient_data = self._get_context_value("patient_data", "")
    
    def _init_database(self):
        """Create database tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Main context table for patient data and agent info
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_context (
                    user_id TEXT,
                    key TEXT,
                    value TEXT,
                    PRIMARY KEY (user_id, key)
                )
            ''')
            # Simplified message history
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS message_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    role TEXT,
                    content TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
    
    def _save_context_value(self, key: str, value):
        """Save context value to database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_context (user_id, key, value) 
                VALUES (?, ?, ?)
            ''', (self.user_id, key, str(value)))
            conn.commit()
    
    def _get_context_value(self, key: str, default=None):
        """Get context value from database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT value FROM user_context WHERE user_id = ? AND key = ?', 
                (self.user_id, key)
            )
            result = cursor.fetchone()
            return result[0] if result else default
    
    def append_patient_data(self, additional_data: str) -> dict:
        """Append new data to patient data."""
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
        """Replace entire patient data."""
        self.patient_data = new_data
        self._save_context_value("patient_data", new_data)
        return {
            "status": "success", 
            "message": "Patient data completely replaced",
            "new_data": new_data
        }
    
    def update_message_history(self, new_message: Dict) -> None:
        """Save message to history."""
        if new_message.get('role') != 'tool' and new_message.get('content'):
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO message_history (user_id, role, content)
                    VALUES (?, ?, ?)
                ''', (
                    self.user_id,
                    new_message.get('role', ''),
                    new_message.get('content', '')
                ))
                conn.commit()
    
    def get_full_message_history(self) -> List[Dict]:
        """Get recent message history."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT role, content 
                FROM message_history 
                WHERE user_id = ?
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (self.user_id, self.max_context_messages))
            messages = cursor.fetchall()
            return [
                {"role": role, "content": content}
                for role, content in reversed(messages)
            ]
    
    def update_last_handoff(self, handoff_time: datetime) -> dict:
        """Update last agent handoff time."""
        self._save_context_value("last_handoff", handoff_time.isoformat())
        return {
            "status": "success",
            "message": "Last handoff time updated",
            "handoff_time": handoff_time.isoformat()
        }
    
    def update_current_agent(self, agent_name: str) -> dict:
        """Update current agent name."""
        self._save_context_value("current_agent", agent_name)
        return {
            "status": "success",
            "message": "Current agent updated",
            "agent_name": agent_name
        }
    
    def remove_all_user_context(self) -> dict:
        """Remove all user context data."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM user_context WHERE user_id = ?', (self.user_id,))
            conn.commit()
        self.patient_data = ""
        return {
            "status": "success",
            "message": "All user context entries removed"
        }
    
    def remove_user_messages(self) -> dict:
        """Remove message history."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM message_history WHERE user_id = ?', (self.user_id,))
            conn.commit()
        return {
            "status": "success",
            "message": f"Message history removed for user_id {self.user_id}"
        }
