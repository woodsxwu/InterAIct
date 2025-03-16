import streamlit as st
from datetime import datetime
import time
import os
from database import db_service as db
from database.scenario_dao import ScenarioDAO
from utils.session_manager import record_response
from pages.tts_helper import text_to_speech, auto_play_prompt
from utils.emotion_detection import get_emotion_feedback


def add_custom_css():
    """Add custom CSS for enhanced UI elements and hiding control buttons"""
    st.markdown("""
    <style>
        /* Enhanced option card with hover effects */
        .option-card {
            padding: 15px;
            border-radius: 15px;
            background-color: #f5f5f5;
            margin-bottom: 10px;
            cursor: pointer;
            transition: all 0.3s ease;
            border: 2px solid transparent;
        }

        .option-card:hover {
            background-color: #e0e0e0;
            transform: scale(1.02);
            border-color: #4287f5;
        }

        .option-card.highlighted {
            transform: scale(1.05);
            box-shadow: 0 0 15px rgba(0,0,0,0.2);
            border: 2px solid #4287f5;
            background-color: #e8f0fe;
        }

        .option-card.disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }

        /* Progress indicator for guided selection */
        .guided-progress {
            width: 100%;
            height: 4px;
            background-color: #e0e0e0;
            margin-top: 5px;
            border-radius: 2px;
            overflow: hidden;
        }

        .guided-progress-bar {
            height: 100%;
            background-color: #4287f5;
            transition: width 0.1s linear;
        }

        /* Hide control buttons */
        button[key="video_complete"], button[key="prompt_complete"] {
            display: none !important;
            opacity: 0 !important;
            position: absolute !important;
            left: -9999px !important;
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

def add_custom_js():
    """Add custom JavaScript for automatic video playback, audio handling, and seamless transitions"""
    st.markdown("""
    <script>
    // Main initialization function
    function initializeAutomatedFlow() {
        setupMouseoverAudio();
        handleVideoAutoplay();
        setupPromptAutoAdvance();
        hideControlButtons();
    }

    // Setup mouseover audio for option cards
    function setupMouseoverAudio() {
        document.querySelectorAll('.option-card').forEach(card => {
            if (card.dataset.audioSetup) return;
            card.dataset.audioSetup = 'true';

            card.addEventListener('mouseenter', () => {
                const optionId = card.id;
                const audioBtn = document.querySelector(`button[data-option="${optionId}"]`);
                if (audioBtn) {
                    audioBtn.click();
                }
            });
        });
    }

    // Handle video autoplay and auto-continue
    function handleVideoAutoplay() {
        const videos = document.querySelectorAll('video');
        videos.forEach(video => {
            // Auto-play video if it's paused
            if (video.paused && !video.ended) {
                video.play().catch(e => console.log('Could not autoplay video:', e));
            }

            // Auto-continue after video ends (if not already set up)
            if (!video.dataset.endedHandlerSet) {
                video.dataset.endedHandlerSet = "true";

                // When video ends, silently trigger completion
                video.addEventListener('ended', function() {
                    console.log('Video ended, auto-advancing');

                    // Click the hidden video complete button
                    setTimeout(function() {
                        const videoCompleteBtn = document.querySelector('button[aria-label="Video Complete"]');
                        if (videoCompleteBtn) {
                            videoCompleteBtn.click();
                        } else {
                            // Fallback: click any button with 'video_complete' in key
                            const fallbackBtn = document.querySelector('button[key*="video_complete"]');
                            if (fallbackBtn) {
                                fallbackBtn.click();
                            }
                        }
                    }, 500);
                });

                // Also set a timeout to auto-advance if video doesn't end naturally
                setTimeout(function() {
                    if (!video.ended) {
                        console.log('Video timeout reached, auto-advancing');
                        const videoCompleteBtn = document.querySelector('button[aria-label="Video Complete"]');
                        if (videoCompleteBtn) {
                            videoCompleteBtn.click();
                        } else {
                            // Fallback: click any button with 'video_complete' in key
                            const fallbackBtn = document.querySelector('button[key*="video_complete"]');
                            if (fallbackBtn) {
                                fallbackBtn.click();
                            }
                        }
                    }
                }, 10000); // 10 seconds timeout
            }
        });

        // If no video found, auto-trigger the video complete button
        if (videos.length === 0) {
            setTimeout(function() {
                console.log('No video found, auto-advancing');
                const videoCompleteBtn = document.querySelector('button[aria-label="Video Complete"]');
                if (videoCompleteBtn) {
                    videoCompleteBtn.click();
                } else {
                    // Fallback: click any button with 'video_complete' in key
                    const fallbackBtn = document.querySelector('button[key*="video_complete"]');
                    if (fallbackBtn) {
                        fallbackBtn.click();
                    }
                }
            }, 1000);
        }
    }

    // Auto-advance after prompt audio completes
    function setupPromptAutoAdvance() {
        const promptAudios = document.querySelectorAll('audio');
        promptAudios.forEach(audio => {
            if (!audio.dataset.endedHandlerSet) {
                audio.dataset.endedHandlerSet = "true";

                audio.addEventListener('ended', function() {
                    console.log('Prompt audio ended, auto-advancing');
                    setTimeout(function() {
                        const promptCompleteBtn = document.querySelector('button[aria-label="Prompt Complete"]');
                        if (promptCompleteBtn) {
                            promptCompleteBtn.click();
                        } else {
                            // Fallback: click any button with 'prompt_complete' in key
                            const fallbackBtn = document.querySelector('button[key*="prompt_complete"]');
                            if (fallbackBtn) {
                                fallbackBtn.click();
                            }
                        }
                    }, 500);
                });

                // Also set a timeout to auto-advance if audio doesn't end naturally
                setTimeout(function() {
                    if (!audio.ended) {
                        console.log('Audio timeout reached, auto-advancing');
                        const promptCompleteBtn = document.querySelector('button[aria-label="Prompt Complete"]');
                        if (promptCompleteBtn) {
                            promptCompleteBtn.click();
                        } else {
                            // Fallback: click any button with 'prompt_complete' in key
                            const fallbackBtn = document.querySelector('button[key*="prompt_complete"]');
                            if (fallbackBtn) {
                                fallbackBtn.click();
                            }
                        }
                    }
                }, 10000); // 10 seconds timeout
            }
        });
    }

    // Hide control buttons for seamless experience
    function hideControlButtons() {
        // Hide the video complete button
        const videoCompleteBtn = document.querySelector('button[key*="video_complete"]');
        if (videoCompleteBtn) {
            videoCompleteBtn.style.display = 'none';
        }

        // Hide the prompt complete button
        const promptCompleteBtn = document.querySelector('button[key*="prompt_complete"]');
        if (promptCompleteBtn) {
            promptCompleteBtn.style.display = 'none';
        }

        // Hide video controls (if any)
        document.querySelectorAll('.stVideo div').forEach(el => {
            const videoControls = el.querySelector('div.element-container');
            if (videoControls) {
                videoControls.style.display = 'none';
            }
        });
    }

    // Run initialization on page load and after Streamlit rerenders
    document.addEventListener('DOMContentLoaded', function() {
        setTimeout(initializeAutomatedFlow, 1000);
    });

    window.addEventListener('message', function(e) {
        if (e.data.type === 'streamlit:render') {
            setTimeout(initializeAutomatedFlow, 1000);
        }
    });
    </script>
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
        st.session_state.current_phase = "entering"  # Restart the scenario from beginning
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

    # Reset state for the next phase
    st.session_state.video_played = False
    st.session_state.prompt_played = False
    st.session_state.options_cycle_complete = False
    st.session_state.current_option_index = -1
    st.session_state.guided_selection_started = False

    # Navigate to feedback page
    st.session_state.page = 'phase_feedback'
    st.rerun()


def show_phase_based_scenario(scenario_index):
    """Display a phase-based social skills scenario with multiple steps and automatic flow"""
    
    # ✅ Keep Custom CSS and JavaScript for UI Improvements
    add_custom_css()
    add_custom_js()

    # ✅ Main container to prevent duplicate elements
    main_container = st.container()

    with main_container:
        # ✅ Initialize State Variables
        if 'guided_selection_started' not in st.session_state:
            st.session_state.guided_selection_started = False
        if 'current_option_index' not in st.session_state:
            st.session_state.current_option_index = -1
        if 'options_cycle_complete' not in st.session_state:
            st.session_state.options_cycle_complete = False
        if 'video_played' not in st.session_state:
            st.session_state.video_played = False
        if 'prompt_played' not in st.session_state:
            st.session_state.prompt_played = False
        if 'option_timer_start' not in st.session_state:
            st.session_state.option_timer_start = time.time()

        # ✅ Get Available Scenarios
        scenarios = get_all_scenarios()

        # ✅ Validate Scenario Index
        if not scenarios or scenario_index >= len(scenarios):
            st.session_state.page = 'report'
            st.rerun()
            return

        scenario_id = scenarios[scenario_index]['id']

        # ✅ Get Scenario Data
        scenario = get_scenario(scenario_id)
        if not scenario:
            st.error(f"Scenario with ID {scenario_id} not found")
            st.session_state.page = 'report'
            st.rerun()
            return

        # ✅ Initialize Current Phase
        if 'current_phase' not in st.session_state:
            st.session_state.current_phase = "entering"

        # ✅ Store Scenario in Session
        st.session_state.current_scenario_id = scenario_id

        # ✅ Find the Current Phase
        current_phase = next((phase for phase in scenario['phases']
                              if phase['phase_id'] == st.session_state.current_phase), None)

        if not current_phase:
            st.error(f"Phase '{st.session_state.current_phase}' not found in scenario.")
            st.session_state.current_phase = "entering"
            st.rerun()
            return

        # ✅ Display Scenario Title & Description
        st.markdown(f"<h1>{scenario['title']}</h1>", unsafe_allow_html=True)
        st.markdown(f"<p style='font-size: 20px;'>{current_phase['description']}</p>", unsafe_allow_html=True)

        # ✅ Embed and Auto-Play Video
        video_path = get_video_path(scenario_id, current_phase['phase_id'])
        if video_path:
            st.video(video_path)

            # ✅ JavaScript to Auto-Detect Video Completion
            st.markdown("""
            <script>
            document.addEventListener('DOMContentLoaded', function() {
                let video = document.querySelector('video');
                if (video) {
                    video.addEventListener('ended', function() {
                        var button = document.querySelector('button#video_complete');
                        if (button) {
                            button.click();
                        }
                    });
                }
            });
            </script>
            """, unsafe_allow_html=True)

        else:
            st.image(scenario['image_path'], use_column_width=True)

        # ✅ Hidden Button to Detect Video Completion
        if st.button("Video Complete", key="video_complete", help="Video completion indicator"):
            st.session_state.video_played = True
            st.rerun()

        # ✅ Display Prompt
        st.markdown(
            f"<div class='avatar-message'><h2>{st.session_state.selected_avatar['name']} asks:</h2>"
            f"<p style='font-size: 20px;'>{current_phase['prompt']}</p></div>",
            unsafe_allow_html=True
        )

        # ✅ Play Text-to-Speech Prompt After Video
        if st.session_state.video_played and not st.session_state.prompt_played:
            prompt_text = f"{st.session_state.selected_avatar['name']} asks: {current_phase['prompt']}"
            audio_data = text_to_speech(prompt_text, auto_play=True)
            
            # ✅ Auto-Play Audio
            if "base64," in audio_data:
                audio_b64 = audio_data.split('base64,')[1]
                st.markdown(f"""
                <div style="display:none;">
                    <audio autoplay>
                        <source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3">
                    </audio>
                </div>
                """, unsafe_allow_html=True)

        # ✅ Hidden Button to Mark Prompt Completion
        if st.button("Prompt Complete", key="prompt_complete", help="Prompt completion indicator"):
            st.session_state.prompt_played = True
            st.session_state.guided_selection_started = True
            st.session_state.current_option_index = 0
            st.session_state.option_timer_start = time.time()
            st.rerun()

        # ✅ Display Choices
        choices = current_phase['options']
        selected_choice = None
        cols = st.columns(len(choices))

        for i, choice in enumerate(choices):
            with cols[i]:
                if st.button(choice["text"], key=f"option_{i}"):
                    selected_choice = choice
                    st.session_state["selected_option"] = selected_choice
                    st.rerun()

        # ✅ Emotion Detection & Logic Handling
        if "selected_option" in st.session_state:
            choice = st.session_state["selected_option"]

            # Detect Emotion
            detected_emotion = get_emotion_feedback()  # Ensure this function is implemented
            
            st.write(f"Emotion detected: {detected_emotion}")

            if detected_emotion == "happy":
                text_to_speech("Great choice! That was a kind response!")
                time.sleep(5)  # Wait before continuing
                st.session_state.page = "scenario_selection"
                st.rerun()

            elif detected_emotion in ["negative", "neutral"]:
                st.warning("Hmm, let's try again.")
                st.session_state["retry_count"] = st.session_state.get("retry_count", 0) + 1
                
                if st.session_state["retry_count"] >= 2:
                    st.error("Taking a break and returning to scenario selection.")
                    st.session_state.page = "scenario_selection"
                    st.rerun()
                else:
                    st.session_state["selected_option"] = None  # Reset choice
                    st.rerun()