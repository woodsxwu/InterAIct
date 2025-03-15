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
        """Get all available scenarios with thread-safe caching"""
        # Check cache first
        with _scenario_cache_lock:
            if 'all_scenarios' in _scenario_cache:
                return _scenario_cache['all_scenarios']

        # Need to query the database
        conn = None
        try:
            conn = ScenarioDAO._get_thread_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scenarios ORDER BY id")
            scenarios = [dict(row) for row in cursor.fetchall()]

            # Update cache
            with _scenario_cache_lock:
                _scenario_cache['all_scenarios'] = scenarios

            return scenarios
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []
        finally:
            # We don't close the connection here as it's tied to the thread
            pass

    @staticmethod
    def get_scenario_by_id(scenario_id):
        """Get a complete scenario with all phases, options, and feedback"""
        # Check cache first
        cache_key = f'scenario_{scenario_id}'
        with _scenario_cache_lock:
            if cache_key in _scenario_cache:
                return _scenario_cache[cache_key]

        # Need to query the database
        conn = None
        try:
            conn = ScenarioDAO._get_thread_connection()
            cursor = conn.cursor()

            # Get the basic scenario info
            cursor.execute("SELECT * FROM scenarios WHERE id = ?", (scenario_id,))
            scenario_row = cursor.fetchone()

            if not scenario_row:
                return None

            scenario = dict(scenario_row)
            scenario['phases'] = []

            # Get all phases for this scenario
            cursor.execute(
                "SELECT * FROM phases WHERE scenario_id = ? ORDER BY id",
                (scenario_id,)
            )

            for phase_row in cursor.fetchall():
                phase = dict(phase_row)
                phase_id = phase['id']  # Database ID
                phase_identifier = phase['phase_id']  # String identifier (e.g., "entering")

                # Get options for this phase
                cursor.execute(
                    "SELECT * FROM options WHERE phase_id = ? ORDER BY option_id",
                    (phase_id,)
                )
                options = [dict(row) for row in cursor.fetchall()]

                # Get feedback for this phase
                cursor.execute(
                    "SELECT * FROM feedback WHERE phase_id = ?",
                    (phase_id,)
                )

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
            print(f"Database error: {e}")
            return None
        finally:
            # We don't close the connection here as it's tied to the thread
            pass

    @staticmethod
    def add_scenario(scenario_data):
        """Add a new scenario to the database"""
        conn = None
        try:
            conn = ScenarioDAO._get_thread_connection()
            cursor = conn.cursor()

            conn.execute("BEGIN TRANSACTION")

            # Insert the scenario
            cursor.execute(
                """
                INSERT INTO scenarios (id, title, description, image_path)
                VALUES (?, ?, ?, ?)
                """,
                (
                    scenario_data['id'],
                    scenario_data['title'],
                    scenario_data['description'],
                    scenario_data['image_path']
                )
            )

            # Check for phases
            if 'phases' in scenario_data:
                for phase_data in scenario_data['phases']:
                    # Insert phase
                    cursor.execute(
                        """
                        INSERT INTO phases (scenario_id, phase_id, description, prompt)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            scenario_data['id'],
                            phase_data['phase_id'],
                            phase_data['description'],
                            phase_data['prompt']
                        )
                    )

                    phase_id = cursor.lastrowid

                    # Insert options
                    for option in phase_data['options']:
                        cursor.execute(
                            """
                            INSERT INTO options (phase_id, option_id, text, icon, emotion, next_phase)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                phase_id,
                                option['id'],
                                option['text'],
                                option.get('icon'),
                                option.get('emotion'),
                                option.get('next_phase')
                            )
                        )

                    # Insert feedback
                    for option_id, feedback in phase_data['feedback'].items():
                        cursor.execute(
                            """
                            INSERT INTO feedback (phase_id, option_id, text, positive, guidance)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                phase_id,
                                option_id,
                                feedback['text'],
                                feedback.get('positive', False),
                                feedback.get('guidance', False)
                            )
                        )

            conn.commit()

            # Clear cache after modification
            with _scenario_cache_lock:
                _scenario_cache.clear()

            return True
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            print(f"Database error: {e}")
            return False
        finally:
            # We don't close the connection here as it's tied to the thread
            pass

    @staticmethod
    def update_scenario(scenario_id, scenario_data):
        """Update an existing scenario"""
        conn = None
        try:
            conn = ScenarioDAO._get_thread_connection()
            cursor = conn.cursor()

            conn.execute("BEGIN TRANSACTION")

            # Update the scenario
            cursor.execute(
                """
                UPDATE scenarios
                SET title = ?, description = ?, image_path = ?
                WHERE id = ?
                """,
                (
                    scenario_data['title'],
                    scenario_data['description'],
                    scenario_data['image_path'],
                    scenario_id
                )
            )

            # For simplicity, delete and recreate phases, options, and feedback
            # In a production system, you might want to update existing records instead

            # Get all phase IDs for this scenario
            cursor.execute("SELECT id FROM phases WHERE scenario_id = ?", (scenario_id,))
            phase_ids = [row[0] for row in cursor.fetchall()]

            # Delete options and feedback for these phases
            for phase_id in phase_ids:
                cursor.execute("DELETE FROM options WHERE phase_id = ?", (phase_id,))
                cursor.execute("DELETE FROM feedback WHERE phase_id = ?", (phase_id,))

            # Delete phases
            cursor.execute("DELETE FROM phases WHERE scenario_id = ?", (scenario_id,))

            # Insert new phases, options, and feedback
            if 'phases' in scenario_data:
                for phase_data in scenario_data['phases']:
                    # Insert phase
                    cursor.execute(
                        """
                        INSERT INTO phases (scenario_id, phase_id, description, prompt)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            scenario_id,
                            phase_data['phase_id'],
                            phase_data['description'],
                            phase_data['prompt']
                        )
                    )

                    phase_id = cursor.lastrowid

                    # Insert options
                    for option in phase_data['options']:
                        cursor.execute(
                            """
                            INSERT INTO options (phase_id, option_id, text, icon, emotion, next_phase)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                phase_id,
                                option['id'],
                                option['text'],
                                option.get('icon'),
                                option.get('emotion'),
                                option.get('next_phase')
                            )
                        )

                    # Insert feedback
                    for option_id, feedback in phase_data['feedback'].items():
                        cursor.execute(
                            """
                            INSERT INTO feedback (phase_id, option_id, text, positive, guidance)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                phase_id,
                                option_id,
                                feedback['text'],
                                feedback.get('positive', False),
                                feedback.get('guidance', False)
                            )
                        )

            conn.commit()

            # Clear cache after modification
            with _scenario_cache_lock:
                _scenario_cache.clear()

            return True
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            print(f"Database error: {e}")
            return False
        finally:
            # We don't close the connection here as it's tied to the thread
            pass

    @staticmethod
    def delete_scenario(scenario_id):
        """Delete a scenario and all related data"""
        conn = None
        try:
            conn = ScenarioDAO._get_thread_connection()
            cursor = conn.cursor()

            conn.execute("BEGIN TRANSACTION")

            # Get all phase IDs for this scenario
            cursor.execute("SELECT id FROM phases WHERE scenario_id = ?", (scenario_id,))
            phase_ids = [row[0] for row in cursor.fetchall()]

            # Delete options and feedback for these phases
            for phase_id in phase_ids:
                cursor.execute("DELETE FROM options WHERE phase_id = ?", (phase_id,))
                cursor.execute("DELETE FROM feedback WHERE phase_id = ?", (phase_id,))

            # Delete phases
            cursor.execute("DELETE FROM phases WHERE scenario_id = ?", (scenario_id,))

            # Delete the scenario
            cursor.execute("DELETE FROM scenarios WHERE id = ?", (scenario_id,))

            conn.commit()

            # Clear cache after modification
            with _scenario_cache_lock:
                _scenario_cache.clear()

            return True
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            print(f"Database error: {e}")
            return False
        finally:
            # We don't close the connection here as it's tied to the thread
            pass

    @staticmethod
    def clear_cache():
        """Clear the entire scenario cache"""
        with _scenario_cache_lock:
            _scenario_cache.clear()

    @staticmethod
    def cleanup_thread():
        """Clean up resources for the current thread"""
        ScenarioDAO._close_thread_connection()