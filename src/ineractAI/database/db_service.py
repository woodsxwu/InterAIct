import sqlite3
import uuid
import json
import threading
from datetime import datetime
from database.db_schema import get_db_connection


# Create a thread-local connection pool
class ConnectionPool:
    _instance = None
    _pool = {}  # Dictionary to store connections per thread
    _max_connections = 5
    _local = threading.local()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ConnectionPool()
        return cls._instance

    def get_connection(self):
        """Get a connection specific to the current thread"""
        thread_id = threading.get_ident()

        # Initialize thread-local pool if needed
        if thread_id not in self._pool:
            self._pool[thread_id] = []

        # Get a connection from the thread's pool or create a new one
        if self._pool[thread_id]:
            return self._pool[thread_id].pop()
        else:
            return get_db_connection()

    def return_connection(self, conn):
        """Return a connection to the thread's pool"""
        thread_id = threading.get_ident()

        # Initialize thread-local pool if needed
        if thread_id not in self._pool:
            self._pool[thread_id] = []

        if len(self._pool[thread_id]) < self._max_connections:
            self._pool[thread_id].append(conn)
        else:
            conn.close()

    def clear_connections(self):
        """Close all connections in all thread pools"""
        for thread_id in list(self._pool.keys()):
            for conn in self._pool[thread_id]:
                try:
                    conn.close()
                except Exception:
                    pass
            self._pool[thread_id] = []


# Updated transaction class that uses the thread-safe connection pool
class DbTransaction:
    """Context manager for database transactions with thread-safe connection pooling"""

    def __init__(self):
        self.conn = None
        self.pool = ConnectionPool.get_instance()

    def __enter__(self):
        self.conn = self.pool.get_connection()
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # An exception occurred, rollback the transaction
            self.conn.rollback()
        else:
            # No exception, commit the transaction
            self.conn.commit()

        # Return the connection to the pool instead of closing it
        self.pool.return_connection(self.conn)
        return False  # Propagate exceptions


class DatabaseError(Exception):
    """Exception raised for database errors"""
    pass


# Avatar Services
def get_avatars():
    """Get all available avatars"""
    try:
        with DbTransaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM avatars")
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        raise DatabaseError(f"Error fetching avatars: {e}")


# Session Services
def create_session(avatar_id=None):
    """Create a new session and return the session ID"""
    try:
        session_id = str(uuid.uuid4())
        with DbTransaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO sessions (id, avatar_id) VALUES (?, ?)",
                (session_id, avatar_id)
            )
            return session_id
    except sqlite3.Error as e:
        raise DatabaseError(f"Error creating session: {e}")


def update_session_avatar(session_id, avatar_id):
    """Update the avatar for a session"""
    try:
        with DbTransaction() as conn:
            cursor = conn.cursor()
            # First check if session exists, if not create it
            cursor.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO sessions (id, avatar_id) VALUES (?, ?)",
                    (session_id, avatar_id)
                )
            else:
                cursor.execute(
                    "UPDATE sessions SET avatar_id = ? WHERE id = ?",
                    (avatar_id, session_id)
                )

            if cursor.rowcount == 0:
                raise DatabaseError(f"Session {session_id} not found")
    except sqlite3.Error as e:
        raise DatabaseError(f"Error updating session avatar: {e}")


def end_session(session_id):
    """Mark a session as ended"""
    try:
        with DbTransaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE sessions SET end_time = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,)
            )
            if cursor.rowcount == 0:
                raise DatabaseError(f"Session {session_id} not found")
    except sqlite3.Error as e:
        raise DatabaseError(f"Error ending session: {e}")


def get_session_data(session_id):
    """Get session data including avatar selection"""
    try:
        with DbTransaction() as conn:
            cursor = conn.cursor()
            # First check if session exists
            cursor.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
            if not cursor.fetchone():
                return None

            # Get full session data with avatar details
            cursor.execute(
                """
                SELECT s.*, a.id as avatar_id, a.name as avatar_name, a.emoji as avatar_emoji, a.color as avatar_color
                FROM sessions s
                LEFT JOIN avatars a ON s.avatar_id = a.id
                WHERE s.id = ?
                """,
                (session_id,)
            )
            session = cursor.fetchone()
            if not session:
                return None

            return dict(session)
    except sqlite3.Error as e:
        raise DatabaseError(f"Error getting session data: {e}")


def record_response(session_id, scenario_id, phase_id, option_id, emotion=None):
    """Record a user's response to a scenario phase"""
    try:
        with DbTransaction() as conn:
            cursor = conn.cursor()

            # First check if this exact response already exists to avoid duplicates
            cursor.execute(
                """
                SELECT id FROM responses 
                WHERE session_id = ? AND scenario_id = ? AND phase_id = ? AND option_id = ?
                """,
                (session_id, scenario_id, phase_id, option_id)
            )

            existing = cursor.fetchone()
            if existing:
                return existing[0]  # Return existing ID

            # Insert the new response
            cursor.execute(
                """
                INSERT INTO responses (session_id, scenario_id, phase_id, option_id, emotion)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, scenario_id, phase_id, option_id, emotion)
            )

            # If emotion indicates distress, create a parent alert in the same transaction
            if emotion in ['angry', 'sad', 'negative']:
                cursor.execute(
                    """
                    INSERT INTO parent_alerts (session_id, scenario_id, phase_id, emotion)
                    VALUES (?, ?, ?, ?)
                    """,
                    (session_id, scenario_id, phase_id, emotion)
                )

            return cursor.lastrowid
    except sqlite3.Error as e:
        raise DatabaseError(f"Error recording response: {e}")


def record_emotion_detection(session_id, emotion, confidence):
    """Record a detected emotion"""
    try:
        with DbTransaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO emotion_detections (session_id, emotion, confidence)
                VALUES (?, ?, ?)
                """,
                (session_id, emotion, confidence)
            )
            return cursor.lastrowid
    except sqlite3.Error as e:
        raise DatabaseError(f"Error recording emotion: {e}")


def create_parent_alert(session_id, scenario_id, phase_id, emotion):
    """Create a parent alert for concerning emotions"""
    try:
        with DbTransaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO parent_alerts (session_id, scenario_id, phase_id, emotion)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, scenario_id, phase_id, emotion)
            )
            return cursor.lastrowid
    except sqlite3.Error as e:
        raise DatabaseError(f"Error creating parent alert: {e}")


# Thread-safe cache with locks
_cache_lock = threading.RLock()
_cached_responses = {}


def get_session_responses(session_id):
    """Get all responses for a session with detailed information"""

    # Thread-safe cache access
    with _cache_lock:
        # Check if we have a cache hit for this session
        if session_id in _cached_responses:
            return _cached_responses[session_id]

    try:
        with DbTransaction() as conn:
            cursor = conn.cursor()

            # Join with scenarios, phases, options, and feedback for detailed information
            cursor.execute(
                """
                SELECT 
                    r.id,
                    r.session_id,
                    r.scenario_id,
                    r.phase_id,
                    r.option_id,
                    r.emotion,
                    r.timestamp,
                    s.title as scenario_title,
                    p.description as phase_description,
                    o.text as option_text,
                    f.text as feedback_text,
                    f.positive as positive,
                    f.guidance as guidance
                FROM responses r
                JOIN scenarios s ON r.scenario_id = s.id
                JOIN phases p ON r.scenario_id = p.scenario_id AND r.phase_id = p.phase_id
                LEFT JOIN options o ON p.id = o.phase_id AND r.option_id = o.option_id
                LEFT JOIN feedback f ON p.id = f.phase_id AND r.option_id = f.option_id
                WHERE r.session_id = ?
                ORDER BY r.timestamp
                """,
                (session_id,)
            )

            responses = [dict(row) for row in cursor.fetchall()]

            # Deduplicate responses
            unique_responses = []
            seen_keys = set()

            for resp in responses:
                key = (resp['scenario_id'], resp['phase_id'], resp['option_id'])
                if key not in seen_keys:
                    seen_keys.add(key)
                    unique_responses.append(resp)

            # Thread-safe cache update
            with _cache_lock:
                _cached_responses[session_id] = unique_responses

            return unique_responses
    except sqlite3.Error as e:
        raise DatabaseError(f"Error getting session responses: {e}")


def generate_report(session_id):
    """Generate a comprehensive report for a session"""
    try:
        with DbTransaction() as conn:
            cursor = conn.cursor()

            # Get session info
            cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            session = cursor.fetchone()

            if not session:
                return None

            # Get all responses with detailed information
            responses = get_session_responses(session_id)

            # Get emotion detections
            cursor.execute(
                """
                SELECT * FROM emotion_detections 
                WHERE session_id = ?
                ORDER BY timestamp
                """,
                (session_id,)
            )

            emotion_detections = [dict(row) for row in cursor.fetchall()]

            # Compile the report data
            report = {
                'session': dict(session),
                'responses': responses,
                'emotion_detections': emotion_detections
            }

            return report
    except sqlite3.Error as e:
        raise DatabaseError(f"Error generating report: {e}")


# Function to clear the cache when needed (e.g., after adding new responses)
def clear_response_cache(session_id=None):
    """Clear the responses cache for a specific session or all sessions"""
    with _cache_lock:
        global _cached_responses
        if session_id:
            if session_id in _cached_responses:
                del _cached_responses[session_id]
        else:
            _cached_responses = {}