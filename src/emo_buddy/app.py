import streamlit as st
import os
import gc
import threading
from pages.phase_based_scenario import show_phase_based_scenario,add_custom_js, add_custom_css

# Set page configuration FIRST - before any other Streamlit commands
st.set_page_config(
    page_title="EmoBuddy - Social Skills Learning for Children",
    page_icon="🧩",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configure Streamlit for better performance
st.config.set_option('server.maxUploadSize', 5)
st.config.set_option('deprecation.showPyplotGlobalUse', False)


def prefetch_resources():
    """Background thread to prefetch common resources without causing threading issues"""
    try:
        # Import here to avoid circular imports
        from database.scenario_dao import ScenarioDAO
        from database import db_service as db
        import time

        # Add a small delay to ensure the main thread has initialized
        time.sleep(0.5)

        try:
            # Prefetch all scenarios - this will now use thread-local connections
            scenarios = ScenarioDAO.get_all_scenarios()
            print(f"Prefetched {len(scenarios)} scenarios")

            # Prefetch each individual scenario - using thread-local connections
            for scenario in scenarios:
                ScenarioDAO.get_scenario_by_id(scenario['id'])

            print("Successfully prefetched all scenario details")
        except Exception as e:
            print(f"Error prefetching scenarios: {e}")

        # Clean up ScenarioDAO thread resources when done
        try:
            ScenarioDAO.cleanup_thread()
        except Exception as e:
            print(f"Error cleaning up ScenarioDAO thread: {e}")

        # We won't try to prefetch avatars in the background since they're simple and
        # can be quickly fetched on-demand in the main thread

        print("Prefetch complete: scenarios loaded in background")
    except Exception as e:
        print(f"Prefetch error: {e}")


def optimize_performance():
    """Apply various performance optimizations"""
    # Increase SQLite cache size
    import sqlite3
    sqlite3.enable_callback_tracebacks(True)  # Helpful for debugging SQLite issues

    # Force garbage collection
    import gc
    gc.collect()

    # Start prefetch thread - with proper thread handling
    import threading
    prefetch_thread = threading.Thread(target=prefetch_resources, daemon=True)
    prefetch_thread.start()

    print(f"Started background prefetch thread (ID: {prefetch_thread.ident})")


# ----- DIRECT FIX FOR SESSION PERSISTENCE -----
def fix_session_persistence():
    """Direct approach to ensure session persistence across app restarts"""
    # Create a session_data directory if it doesn't exist
    os.makedirs("session_data", exist_ok=True)

    # Path to store the last session ID
    session_file = os.path.join("session_data", "last_session_id.txt")

    # Check if we already have a session ID in the streamlit session state
    if 'db_session_id' not in st.session_state:
        # Try to read the last session ID from file
        if os.path.exists(session_file):
            try:
                with open(session_file, 'r') as f:
                    last_session_id = f.read().strip()
                    if last_session_id:
                        print(f"Restoring session ID from file: {last_session_id}")
                        st.session_state.db_session_id = last_session_id

                        # Also update localStorage via JavaScript
                        st.markdown(
                            f"""
                            <script>
                                localStorage.setItem('emobuddy_session_id', '{last_session_id}');
                                console.log('Restored session ID to localStorage: {last_session_id}');
                            </script>
                            """,
                            unsafe_allow_html=True
                        )
            except Exception as e:
                print(f"Error reading session ID from file: {e}")

    # If we have a session ID at this point (either from existing session state or from file),
    # ensure it's saved to the file for future app restarts
    if 'db_session_id' in st.session_state:
        try:
            with open(session_file, 'w') as f:
                f.write(st.session_state.db_session_id)
                print(f"Saved session ID to file: {st.session_state.db_session_id}")
        except Exception as e:
            print(f"Error saving session ID to file: {e}")


# Apply the direct fix FIRST
fix_session_persistence()
# ----- END OF DIRECT FIX -----

# Import database schema and path
from database.db_schema import initialize_database, populate_initial_data, DB_PATH

# Make sure the database directory exists
db_dir = os.path.dirname(DB_PATH)
if db_dir and not os.path.exists(db_dir):
    os.makedirs(db_dir, exist_ok=True)
    print(f"Created database directory: {db_dir}")

# Only initialize and populate if the database doesn't exist or is empty
if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) == 0:
    print(f"Database not found or empty, initializing at: {os.path.abspath(DB_PATH)}")
    initialize_database()
    populate_initial_data()
else:
    print(f"Using existing database: {os.path.abspath(DB_PATH)}")
    print(f"Database size: {os.path.getsize(DB_PATH)} bytes")

# Import database service
from database import db_service as db
from database.scenario_dao import ScenarioDAO

# Import page modules
from pages import (
    show_avatar_selection,
    show_scenario_selection,
    show_phase_based_scenario,
    show_phase_feedback,
    show_report,
    show_parent_dashboard
)
from pages.tts_helper import text_to_speech, create_tts_button, auto_play_prompt

# Import session manager and emotion detection
from utils.session_manager import initialize_session_state
from utils.emotion_detection import initialize_emotion_detection, render_emotion_detection_ui

# Clear cache on startup to prevent stale data
st.cache_data.clear()

st.markdown("""
<style>
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    header {visibility: hidden !important;}

    /* This is a more specific selector for just the default navigation links */
    [data-testid="stSidebarNav"] {display: none !important;}

    /* Make sure the rest of the sidebar is visible */
    section[data-testid="stSidebar"] {display: block !important; visibility: visible !important;}
</style>
""", unsafe_allow_html=True)

# Initialize session state
initialize_session_state()
initialize_emotion_detection()

# Make sure sound toggle is initialized
if 'sound_enabled' not in st.session_state:
    st.session_state.sound_enabled = True

# Load CSS
st.markdown("""
<style>
    .main {
        background-color: #f9f7ff;
    }
    .stButton > button {
        border-radius: 20px;
        padding: 15px;
        font-size: 18px;
        font-weight: bold;
        transition: transform 0.2s;
    }
    .stButton > button:hover {
        transform: scale(1.05);
    }
    .avatar-btn {
        text-align: center;
        padding: 20px;
        border-radius: 20px;
        background-color: #f0f0f0;
        transition: all 0.3s;
        cursor: pointer;
    }
    .avatar-btn:hover {
        transform: scale(1.05);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .emoji-large {
        font-size: 60px;
    }
    .avatar-message {
        padding: 15px;
        border-radius: 15px;
        background-color: #e1f5fe;
        margin-bottom: 20px;
    }
    .option-card {
        padding: 15px;
        border-radius: 15px;
        background-color: #f5f5f5;
        margin-bottom: 10px;
        cursor: pointer;
        transition: background-color 0.3s;
    }
    .option-card:hover {
        background-color: #e0e0e0;
    }
    .alert {
        padding: 15px;
        border-radius: 15px;
        background-color: #ffebee;
        margin-bottom: 20px;
        border-left: 5px solid #f44336;
    }
    .nav-button {
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)


# Main app function
def main():
    add_custom_css()
    add_custom_js()
    # Apply performance optimizations
    optimize_performance()

    # Already handled session restoration with our direct fix

    # Create unified sidebar
    with st.sidebar:
        # Add a logo or app title at the top
        st.markdown(f"""
        <div style='text-align: center; margin-bottom: 20px;'>
            <h2 style='color: #9c88ff;'>EmoBuddy</h2>
            <p>Social Skills Learning</p>
        </div>
        """, unsafe_allow_html=True)

        # Navigation buttons group
        if st.button("Home", key="nav_home", use_container_width=True,
                     help="Go to home page"):
            st.session_state.page = 'avatar_selection'
            st.rerun()

        if st.button("Choose Scenarios", key="nav_scenarios", use_container_width=True,
                     help="Choose scenarios to play through"):
            if st.session_state.get('selected_avatar'):
                # Always go to scenario selection page from navigation
                st.session_state.page = 'scenario_selection'
                st.rerun()
            else:
                st.warning("Please select an avatar first!")

        if st.button("Report", key="nav_report", use_container_width=True,
                     help="View your progress report"):
            st.session_state.page = 'report'
            st.rerun()

        if st.button("Parent Dashboard", key="nav_parent", use_container_width=True,
                     help="Access parent/teacher controls"):
            st.session_state.page = 'parent_dashboard'
            st.rerun()

        # Separator
        st.markdown("---")

        # Settings toggles group
        sound_enabled = st.toggle("Enable Sound", value=st.session_state.get('sound_enabled', True),
                                  help="Turn audio narration on/off")
        if sound_enabled != st.session_state.sound_enabled:
            st.session_state.sound_enabled = sound_enabled
            st.rerun()

        camera_enabled = st.toggle("Enable Emotion Detection", value=st.session_state.get('camera_enabled', False),
                                   help="Turn on camera for emotion detection")
        if camera_enabled != st.session_state.get('camera_enabled', False):
            st.session_state.camera_enabled = camera_enabled
            st.rerun()

        # Session info at the bottom
        st.markdown("---")
        if st.session_state.get('selected_avatar'):
            avatar = st.session_state.selected_avatar
            st.markdown(f"""
            <div style='background-color: {avatar['color']}20; padding: 10px; border-radius: 10px; margin-top: 10px;'>
                <p style='text-align: center; margin-bottom: 5px;'>
                    <span style='font-size: 30px;'>{avatar['emoji']}</span>
                </p>
                <p style='text-align: center; font-weight: bold;'>{avatar['name']}</p>
                <p style='text-align: center; font-size: 12px;'>Session ID: {st.session_state.get('db_session_id', 'Not initialized')[:8]}...</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.caption(f"Session ID: {st.session_state.get('db_session_id', 'Not initialized')[:8]}...")

    # Show emotion detection UI if enabled
    if st.session_state.get('emotion_detector_running', False):
        render_emotion_detection_ui()

    # Page navigation
    current_page = st.session_state.get('page', 'avatar_selection')

    if current_page == 'avatar_selection':
        show_avatar_selection()
    elif current_page == 'scenario_selection':
        if not st.session_state.get('selected_avatar'):
            st.warning("Please select an avatar first!")
            st.session_state.page = 'avatar_selection'
            st.rerun()
        else:
            show_scenario_selection()
    elif current_page == 'scenario':
        if not st.session_state.get('selected_avatar'):
            st.warning("Please select an avatar first!")
            st.session_state.page = 'avatar_selection'
            st.rerun()
        else:
            show_phase_based_scenario(st.session_state.get('current_scenario_index', 0))
    elif current_page == 'phase_feedback':
        show_phase_feedback()
    elif current_page == 'report':
        show_report()
    elif current_page == 'parent_dashboard':
        show_parent_dashboard()
    else:
        st.error(f"Unknown page: {current_page}")
        st.session_state.page = 'avatar_selection'
        st.rerun()


# Run the app
if __name__ == "__main__":
    main()