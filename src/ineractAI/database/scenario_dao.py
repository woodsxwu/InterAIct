import sqlite3
import threading
from database.db_schema import get_db_connection, DB_PATH

# Thread-local storage for connections
_thread_local = threading.local()

# Cache with lock for thread safety
_scenario_cache_lock = threading.RLock()
_scenario_cache = {}


class ScenarioDAO:
    """Thread-safe Data Access Object for scenarios, phases, options, and feedback"""

    @staticmethod
    def _get_thread_connection():
        """Get a connection specific to the current thread"""
        if not hasattr(_thread_local, 'connection'):
            _thread_local.connection = get_db_connection()
        return _thread_local.connection

    @staticmethod
    def _close_thread_connection():
        """Close the thread's connection if it exists"""
        if hasattr(_thread_local, 'connection'):
            try:
                _thread_local.connection.close()
            except Exception:
                pass
            delattr(_thread_local, 'connection')

    @staticmethod
    def get_all_scenarios():
        """Retrieve all scenarios including video paths, thread-safe with caching"""
        with _scenario_cache_lock:
            if 'all_scenarios' in _scenario_cache:
                return _scenario_cache['all_scenarios']

        conn = None
        try:
            conn = ScenarioDAO._get_thread_connection()
            cursor = conn.cursor()
            
            # ✅ Ensure video_path is included explicitly
            cursor.execute("SELECT id, title, description, video_path FROM scenarios ORDER BY id")
            
            scenarios = []
            for row in cursor.fetchall():
                scenarios.append({
                    "id": row[0],
                    "title": row[1],
                    "description": row[2],
                    "video_path": row[3] if row[3] else "src/ineractAI/videos/default.mp4"  # Fallback if NULL
                })

            # Update cache
            with _scenario_cache_lock:
                _scenario_cache['all_scenarios'] = scenarios

            return scenarios
        except sqlite3.Error as e:
            print(f"⚠️ Database error in get_all_scenarios(): {e}")
            return []
    
    @staticmethod
    def get_scenario_by_id(scenario_id):
        """Retrieve a complete scenario including video path, phases, options, and feedback"""
        cache_key = f'scenario_{scenario_id}'
        with _scenario_cache_lock:
            if cache_key in _scenario_cache:
                return _scenario_cache[cache_key]

        conn = None
        try:
            conn = ScenarioDAO._get_thread_connection()
            cursor = conn.cursor()

            # ✅ Ensure video_path is included
            cursor.execute("SELECT id, title, description, video_path FROM scenarios WHERE id = ?", (scenario_id,))
            scenario_row = cursor.fetchone()

            if not scenario_row:
                return None

            scenario = {
                "id": scenario_row[0],
                "title": scenario_row[1],
                "description": scenario_row[2],
                "video_path": scenario_row[3] if scenario_row[3] else "src/ineractAI/videos/default.mp4"
            }
            scenario['phases'] = []

            # Get all phases for this scenario
            cursor.execute("SELECT * FROM phases WHERE scenario_id = ? ORDER BY id", (scenario_id,))
            for phase_row in cursor.fetchall():
                phase = dict(phase_row)
                phase_id = phase['id']
                phase_identifier = phase['phase_id']

                # Get options for this phase
                cursor.execute("SELECT * FROM options WHERE phase_id = ? ORDER BY option_id", (phase_id,))
                options = [dict(row) for row in cursor.fetchall()]

                # Get feedback for this phase
                cursor.execute("SELECT * FROM feedback WHERE phase_id = ?", (phase_id,))
                feedback = {}
                for feedback_row in cursor.fetchall():
                    feedback_dict = dict(feedback_row)
                    feedback[feedback_dict['option_id']] = {
                        'text': feedback_dict['text'],
                        'positive': bool(feedback_dict['positive']),
                        'guidance': bool(feedback_dict['guidance'])
                    }

                # Add the complete phase to the scenario
                scenario['phases'].append({
                    'phase_id': phase_identifier,
                    'description': phase['description'],
                    'prompt': phase['prompt'],
                    'options': options,
                    'feedback': feedback
                })

            # Update cache
            with _scenario_cache_lock:
                _scenario_cache[cache_key] = scenario

            return scenario
        except sqlite3.Error as e:
            print(f"⚠️ Database error in get_scenario_by_id(): {e}")
            return None

    @staticmethod
    def clear_cache():
        """Clear the entire scenario cache"""
        with _scenario_cache_lock:
            _scenario_cache.clear()

    @staticmethod
    def cleanup_thread():
        """Clean up resources for the current thread"""
        ScenarioDAO._close_thread_connection()
