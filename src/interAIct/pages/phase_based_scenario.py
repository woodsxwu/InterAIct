import streamlit as st
from datetime import datetime
import time
import os
from database import db_service as db
from database.scenario_dao import ScenarioDAO
from utils.session_manager import record_response
from pages.tts_helper import text_to_speech, auto_play_prompt
# Update import to use WebRTC-based emotion detection
from utils.webrtc_emotion_detection import get_emotion_feedback


def add_custom_css():
    """Add custom CSS for enhanced UI elements"""
    st.markdown("""
    <style>
        /* Option card styling */
        .option-card {
            padding: 15px;
            border-radius: 15px;
            background-color: #f5f5f5;
            margin-bottom: 15px;
            transition: all 0.3s ease;
            border: 2px solid transparent;
            display: flex;
            align-items: center;
        }
        
        .option-card:hover {
            background-color: #e0e0e0;
            border-color: #4287f5;
        }
        
        /* Sound button styling */
        .sound-button {
            background-color: #4287f5;
            color: white;
            border: none;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-left: 10px;
            cursor: pointer;
        }
        
        .sound-button:hover {
            background-color: #2a6dd9;
        }
        
        /* Emotion feedback display */
        .emotion-feedback {
            margin-top: 15px;
            padding: 10px;
            border-radius: 10px;
            background-color: #f5f5f5;
            border-left: 4px solid #9c88ff;
        }
        
        /* Hide Streamlit video controls but keep the video visible */
        .stVideo > div > div > .element-container.st-emotion-cache-1n76uvr {
            display: none !important;
        }

        /* Make sure the video is visible and autoplays */
        .stVideo video {
            display: block !important;
        }
    </style>
    """, unsafe_allow_html=True)


# Cache for scenarios
_scenario_cache = {}


def get_scenario(scenario_id):
    """Get a scenario with caching"""
    if scenario_id in _scenario_cache:
        return _scenario_cache[scenario_id]

    try:
        scenario = ScenarioDAO.get_scenario_by_id(scenario_id)
        if scenario:
            _scenario_cache[scenario_id] = scenario
        return scenario
    except Exception as e:
        st.error(f"Failed to load scenario details: {e}")
        return None


def get_all_scenarios():
    """Get all scenarios with caching"""
    if 'all_scenarios' in _scenario_cache:
        return _scenario_cache['all_scenarios']

    try:
        scenarios = ScenarioDAO.get_all_scenarios()
        if scenarios:
            _scenario_cache['all_scenarios'] = scenarios
        return scenarios
    except Exception as e:
        st.error(f"Failed to load scenarios: {e}")
        return []


def get_video_path(scenario_id, phase_id):
    """Get the path to the video for the given scenario phase"""
    video_dir = "videos"
    base_filename = f"scenario_{scenario_id}_phase_{phase_id}"

    # Check multiple video formats
    for ext in ['.mp4', '.webm', '.ogg']:
        video_path = os.path.join(video_dir, base_filename + ext)
        if os.path.exists(video_path):
            return video_path

    # Return empty string if no video exists
    return ""


def handle_option_selection(option, current_phase, scenario_id, scenario_index, scenarios):
    """Handle option selection and page navigation"""
    # Get detected emotion if camera is enabled
    detected_emotion = None
    if st.session_state.get('camera_enabled', False) and st.session_state.get('webrtc_ctx_active', False):
        detected_emotion = get_emotion_feedback()
        # Override option emotion if detected
        if detected_emotion:
            option['emotion'] = detected_emotion
            
        # Log the detected emotion
        print(f"Detected emotion: {detected_emotion}")
    
    # Record the response in the database
    try:
        record_response(
            scenario_id,
            current_phase['phase_id'],
            option['option_id'],
            option.get('emotion')
        )
    except Exception as e:
        print(f"Error recording response: {e}")

    # Handle the next phase transition
    next_phase = option.get('next_phase')

    # Check if next_phase is "real_exit" which means scenario is complete
    if next_phase == "real_exit":
        st.session_state.scenario_completed = True

        # Advance to next scenario on next visit
        current_index = st.session_state.current_scenario_index
        if 'scenario_completed_indexes' not in st.session_state:
            st.session_state.scenario_completed_indexes = []

        if current_index not in st.session_state.scenario_completed_indexes:
            st.session_state.scenario_completed_indexes.append(current_index)

        # Setup for next scenario
        if current_index < len(scenarios) - 1:
            st.session_state.current_scenario_index = current_index + 1
            # Reset current phase for next scenario
            if 'current_phase' in st.session_state:
                del st.session_state.current_phase
        else:
            # No more scenarios, will go to report
            pass

        # Set exit phase for feedback
        st.session_state.current_phase = "exit"

    # Regular phase transition handling
    elif next_phase == "restart":
        # Get the first phase of the scenario instead of hardcoding "entering"
        scenario = get_scenario(scenario_id)
        if scenario and scenario['phases'] and len(scenario['phases']) > 0:
            st.session_state.current_phase = scenario['phases'][0]['phase_id']
        else:
            # If we can't find the first phase, just go to exit
            st.session_state.current_phase = "exit"
    elif next_phase == "end_waiting" or next_phase == "end_no_slide":
        # These are exit paths - mark as complete and move to next scenario
        st.session_state.current_phase = next_phase  # Use the actual exit phase
    elif next_phase == "waiting_reminder":
        # Special case for the waiting reminder - it should advance to sliding afterwards
        # Store that we're in a reminder phase
        st.session_state.reminder_phase = True
        st.session_state.next_after_reminder = "sliding"
        st.session_state.current_phase = next_phase
    elif next_phase:
        # Regular phase transition - store the next phase
        st.session_state.current_phase = next_phase
    else:
        # No next_phase specified - assume we should advance to the next scenario
        st.session_state.current_phase = "exit"

    # Save the feedback in session state for the feedback page
    feedback_text = current_phase['feedback'].get(option['option_id'], {}).get('text', 'Great choice!')
    is_positive = current_phase['feedback'].get(option['option_id'], {}).get('positive', True)
    needs_guidance = current_phase['feedback'].get(option['option_id'], {}).get('guidance', False)
    
    # Store feedback information
    st.session_state.temp_feedback = {
        'text': feedback_text,
        'positive': is_positive,
        'guidance': needs_guidance,
        'emotion': detected_emotion
    }

    # Navigate to feedback page
    st.session_state.page = 'phase_feedback'
    st.rerun()


def show_phase_based_scenario(scenario_index):
    """Display a phase-based social skills scenario with multiple steps and automatic flow"""
    
    # Apply custom CSS
    add_custom_css()

    # Main container to prevent duplicate elements
    main_container = st.container()

    with main_container:
        # Get available scenarios
        scenarios = get_all_scenarios()

        # Validate scenario index
        if not scenarios or scenario_index >= len(scenarios):
            st.session_state.page = 'report'
            st.rerun()
            return

        scenario_id = scenarios[scenario_index]['id']

        # Get scenario data
        scenario = get_scenario(scenario_id)
        if not scenario:
            st.error(f"Scenario with ID {scenario_id} not found")
            st.session_state.page = 'report'
            st.rerun()
            return

        # Initialize current phase if needed
        if 'current_phase' not in st.session_state:
            # Get the first phase instead of hardcoding "entering"
            if scenario['phases'] and len(scenario['phases']) > 0:
                # Use the first phase in the list
                st.session_state.current_phase = scenario['phases'][0]['phase_id']
            else:
                st.error("No phases found in this scenario")
                st.session_state.page = 'scenario_selection'
                st.rerun()
                return

        # Store scenario in session
        st.session_state.current_scenario_id = scenario_id

        # Find the current phase
        current_phase = next((phase for phase in scenario['phases']
                              if phase['phase_id'] == st.session_state.current_phase), None)

        if not current_phase:
            st.error(f"Phase '{st.session_state.current_phase}' not found in scenario.")
            # Reset to first phase instead of hardcoding "entering"
            if scenario['phases'] and len(scenario['phases']) > 0:
                st.session_state.current_phase = scenario['phases'][0]['phase_id']
                st.rerun()
            else:
                st.session_state.page = 'scenario_selection'
                st.rerun()
            return

        # Display scenario title and description
        st.markdown(f"<h1>{scenario['title']}</h1>", unsafe_allow_html=True)
        st.markdown(f"<p style='font-size: 20px;'>{current_phase['description']}</p>", unsafe_allow_html=True)

        # Display current emotion if enabled
        if st.session_state.get('camera_enabled', False) and st.session_state.get('webrtc_ctx_active', False):
            try:
                # Get emotion feedback
                emotion = get_emotion_feedback()
                
                # Map emotions to emojis
                emotion_emojis = {
                    "happy": "😊",
                    "neutral": "😐",
                    "negative": "😢",
                    "thoughtful": "🤔"
                }
                
                emoji = emotion_emojis.get(emotion, "😐")
                
                # Display current emotion
                st.markdown(f"""
                <div class="emotion-feedback">
                    <div style="display: flex; align-items: center;">
                        <div style="font-size: 30px; margin-right: 10px;">{emoji}</div>
                        <div>
                            <strong>Current mood:</strong> {emotion.capitalize()}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            except Exception as e:
                print(f"Error displaying emotion: {e}")

        # Embed video - video plays automatically with st.video
        video_path = get_video_path(scenario_id, current_phase['phase_id'])
        if video_path:
            st.video(video_path, start_time=0)
        else:
            st.image(scenario['image_path'], use_column_width=True)

        # Display prompt
        st.markdown(
            f"<div class='avatar-message'><h2>{st.session_state.selected_avatar['name']} asks:</h2>"
            f"<p style='font-size: 20px;'>{current_phase['prompt']}</p></div>",
            unsafe_allow_html=True
        )

        # Play text-to-speech prompt
        if st.session_state.get('sound_enabled', True):
            prompt_text = f"{st.session_state.selected_avatar['name']} asks: {current_phase['prompt']}"
            # Generate a key that is unique to this prompt
            prompt_key = f"prompt_{scenario_id}_{current_phase['phase_id']}"
            
            # Create the audio element for auto-play
            audio_html = text_to_speech(prompt_text, auto_play=True)
            st.markdown(f"<div>{audio_html}</div>", unsafe_allow_html=True)

        # Display choices with direct click and sound buttons
        choices = current_phase['options']
        
        # Create a separate column for each choice
        for i, choice in enumerate(choices):
            # Create a container for the option
            option_container = st.container()
            
            # Create two columns - one for the option card and one for buttons
            col1, col2 = option_container.columns([4, 1])
            
            with col1:
                # Option button - clicking this selects the option
                if st.button(f"{choice.get('icon', '🔹')} {choice['text']}", 
                            key=f"option_{i}", 
                            use_container_width=True):
                    handle_option_selection(choice, current_phase, scenario_id, scenario_index, scenarios)
            
            with col2:
                # Sound button - clicking this reads the option text aloud
                prompt_key = f"sound_option_{i}"
                if st.button("🔊", key=prompt_key, help="Read option aloud"):
                    # This is just to trigger the audio generation below
                    st.session_state[f"play_{prompt_key}"] = True
                
                # If sound button was clicked, generate and play the audio
                if st.session_state.get(f"play_{prompt_key}", False):
                    audio_html = text_to_speech(choice['text'], auto_play=True)
                    st.markdown(f"<div>{audio_html}</div>", unsafe_allow_html=True)
                    # Reset for next time
                    st.session_state[f"play_{prompt_key}"] = False
            
        # Add emotion detection feedback
        if st.session_state.get('camera_enabled', False) and st.session_state.get('webrtc_ctx_active', False):
            emotion_container = st.container()
            with emotion_container:
                try:
                    # Get current emotion
                    emotion = get_emotion_feedback()
                    
                    # If emotion is distressed, show supportive message
                    if emotion == "negative":
                        st.warning("I notice you seem a bit upset. Would you like to take a short break or talk about how you're feeling?")
                    elif emotion == "happy":
                        st.success("I can see you're enjoying this! That's wonderful!")
                except Exception as e:
                    print(f"Error processing emotion feedback: {e}")