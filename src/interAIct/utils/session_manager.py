import streamlit as st
import uuid
from datetime import datetime, time
from database import db_service as db

# Cache for session data to reduce database calls
_session_cache = {}
_response_cache = {}


def initialize_session_state():
    """Initialize all session state variables with default values"""
    # Check for existing session ID in session state - may have been set from query params
    if 'db_session_id' not in st.session_state:
        try:
            # Create a new session in the database and get the session ID
            session_id = db.create_session()
            st.session_state.db_session_id = session_id

            # Store session ID in local storage
            st.markdown(
                f"""
                <script>
                    localStorage.setItem('emobuddy_session_id', '{session_id}');
                    console.log('Session ID saved to localStorage: {session_id}');
                </script>
                """,
                unsafe_allow_html=True
            )
        except Exception:
            # Fallback to local session ID if database fails
            fallback_id = str(uuid.uuid4())
            st.session_state.db_session_id = fallback_id

    # Try to restore session data from database - only if we don't have it already
    if 'db_session_id' in st.session_state and 'selected_avatar' not in st.session_state:
        restore_session_from_database(st.session_state.db_session_id)


def restore_session_from_database(session_id):
    """Restore all session data from the database"""
    # Use the cache first if available
    if session_id in _session_cache:
        session_data = _session_cache[session_id]
        if session_data and session_data.get('avatar_id'):
            # Get avatar details
            avatars = db.get_avatars()
            avatar = next((a for a in avatars if a['id'] == session_data['avatar_id']), None)
            if avatar:
                st.session_state.selected_avatar = avatar
    else:
        try:
            # 1. Restore avatar selection
            if 'selected_avatar' not in st.session_state:
                session_data = db.get_session_data(session_id)
                # Cache the session data
                _session_cache[session_id] = session_data

                if session_data and session_data.get('avatar_id'):
                    # Get avatar details
                    avatars = db.get_avatars()
                    avatar = next((a for a in avatars if a['id'] == session_data['avatar_id']), None)
                    if avatar:
                        st.session_state.selected_avatar = avatar
        except Exception:
            pass

    # 2. Restore responses (only if we don't have them already)
    if 'responses' not in st.session_state or not st.session_state.responses:
        # Check cache first
        if session_id in _response_cache:
            previous_responses = _response_cache[session_id]
            if previous_responses:
                # Initialize response collections if needed
                if 'responses' not in st.session_state:
                    st.session_state.responses = []
                if 'phase_responses' not in st.session_state:
                    st.session_state.phase_responses = []

                # Convert database responses to match session state format
                for resp in previous_responses:
                    # Format for regular responses
                    st.session_state.responses.append({
                        "scenario_id": resp['scenario_id'],
                        "response": resp['option_id'],
                        "emotion": resp.get('emotion', 'neutral'),
                        "timestamp": resp.get('timestamp', '')
                    })

                    # Format for phase responses
                    st.session_state.phase_responses.append({
                        "scenario_id": resp['scenario_id'],
                        "phase_id": resp['phase_id'],
                        "response": resp['option_id'],
                        "emotion": resp.get('emotion', 'neutral'),
                        "timestamp": resp.get('timestamp', '')
                    })
        else:
            try:
                # Fetch all previous responses from the database
                previous_responses = db.get_session_responses(session_id)
                # Cache the responses
                _response_cache[session_id] = previous_responses

                if previous_responses:
                    # Initialize response collections if needed
                    if 'responses' not in st.session_state:
                        st.session_state.responses = []
                    if 'phase_responses' not in st.session_state:
                        st.session_state.phase_responses = []

                    # Convert database responses to match session state format
                    for resp in previous_responses:
                        # Format for regular responses
                        st.session_state.responses.append({
                            "scenario_id": resp['scenario_id'],
                            "response": resp['option_id'],
                            "emotion": resp.get('emotion', 'neutral'),
                            "timestamp": resp.get('timestamp', '')
                        })

                        # Format for phase responses
                        st.session_state.phase_responses.append({
                            "scenario_id": resp['scenario_id'],
                            "phase_id": resp['phase_id'],
                            "response": resp['option_id'],
                            "emotion": resp.get('emotion', 'neutral'),
                            "timestamp": resp.get('timestamp', '')
                        })
            except Exception:
                pass

    # Initialize UI state variables if they don't exist (only set what's needed)
    if 'selected_avatar' not in st.session_state:
        st.session_state.selected_avatar = None
    if 'current_scenario_index' not in st.session_state:
        st.session_state.current_scenario_index = 0
    if 'show_parent_alert' not in st.session_state:
        st.session_state.show_parent_alert = False
    if 'camera_enabled' not in st.session_state:
        st.session_state.camera_enabled = False
    if 'sound_enabled' not in st.session_state:
        st.session_state.sound_enabled = True

    # Initialize response tracking arrays if they don't exist
    if 'responses' not in st.session_state:
        st.session_state.responses = []
    if 'phase_responses' not in st.session_state:
        st.session_state.phase_responses = []


def select_avatar(avatar):
    """Select an avatar and update the database"""
    st.session_state.selected_avatar = avatar

    # Update global cache
    if 'db_session_id' in st.session_state:
        session_id = st.session_state.db_session_id
        if session_id in _session_cache:
            # Check if _session_cache[session_id] is None or not a dictionary
            if _session_cache[session_id] is None:
                _session_cache[session_id] = {'avatar_id': avatar['id']}
            else:
                _session_cache[session_id]['avatar_id'] = avatar['id']

    try:
        # Update the session in the database
        db.update_session_avatar(st.session_state.db_session_id, avatar['id'])
    except Exception:
        pass

def record_response(scenario_id, phase_id, option_id, emotion=None):
    """Record a user's response in the database and session state"""
    try:
        # Prevent duplicate responses by checking if this exact response already exists
        duplicate = False

        if hasattr(st.session_state, 'responses') and st.session_state.responses:
            for existing_resp in st.session_state.responses:
                if (existing_resp.get('scenario_id') == scenario_id and
                        existing_resp.get('phase_id') == phase_id and
                        existing_resp.get('response') == option_id):
                    duplicate = True
                    break

        if not duplicate:
            # Record the response in database (asynchronously if possible)
            response_id = db.record_response(
                st.session_state.db_session_id,
                scenario_id,
                phase_id,
                option_id,
                emotion
            )

            # Clear the response cache to ensure fresh data next time
            session_id = st.session_state.db_session_id
            if session_id in _response_cache:
                del _response_cache[session_id]

            # Also store in session state for immediate use
            if 'responses' not in st.session_state:
                st.session_state.responses = []
            if 'phase_responses' not in st.session_state:
                st.session_state.phase_responses = []

            # Add to responses only if not duplicate
            response_data = {
                "scenario_id": scenario_id,
                "phase_id": phase_id,
                "response": option_id,
                "emotion": emotion,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            st.session_state.responses.append(response_data)
            st.session_state.phase_responses.append(response_data)

    except Exception:
        # Fallback to session state storage
        if 'responses' not in st.session_state:
            st.session_state.responses = []
        if 'phase_responses' not in st.session_state:
            st.session_state.phase_responses = []

        # Check for duplicates before adding
        duplicate = False
        for existing_resp in st.session_state.responses:
            if (existing_resp.get('scenario_id') == scenario_id and
                    existing_resp.get('phase_id') == phase_id and
                    existing_resp.get('response') == option_id):
                duplicate = True
                break

        if not duplicate:
            # Add to responses
            response_data = {
                "scenario_id": scenario_id,
                "phase_id": phase_id,
                "response": option_id,
                "emotion": emotion,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            st.session_state.responses.append(response_data)
            st.session_state.phase_responses.append(response_data)


def record_detected_emotion(emotion, confidence):
    """Record a detected emotion in the database"""
    try:
        db.record_emotion_detection(
            st.session_state.db_session_id,
            emotion,
            confidence
        )
    except Exception:
        # Fallback to session state storage
        if 'detected_emotions' not in st.session_state:
            st.session_state.detected_emotions = []

        st.session_state.detected_emotions.append({
            "emotion": emotion,
            "confidence": confidence,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })


def get_session_report():
    """Get a comprehensive report for the current session"""
    try:
        report_data = db.generate_report(st.session_state.db_session_id)
        return report_data
    except Exception:
        return None


def reset_session():
    """Reset the entire session state and end the current database session"""
    global _session_cache, _response_cache

    try:
        # End the current session in the database
        if 'db_session_id' in st.session_state:
            session_id = st.session_state.db_session_id
            db.end_session(session_id)

            # Clear caches
            if session_id in _session_cache:
                del _session_cache[session_id]
            if session_id in _response_cache:
                del _response_cache[session_id]

            # Clear the session ID from localStorage
            st.markdown(
                """
                <script>
                    localStorage.removeItem('emobuddy_session_id');
                    console.log('Session ID removed from localStorage');
                </script>
                """,
                unsafe_allow_html=True
            )
    except Exception:
        pass

    # Clear all session state variables
    for key in list(st.session_state.keys()):
        del st.session_state[key]

    # Reinitialize necessary session state
    initialize_session_state()

def record_parent_alert(emotion):
    """Record distress alerts for parents when child emotions indicate distress."""
    if "parent_alerts" not in st.session_state:
        st.session_state.parent_alerts = []
    
    st.session_state.parent_alerts.append({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "emotion": emotion
    })
