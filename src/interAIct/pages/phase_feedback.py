import streamlit as st
from database.scenario_dao import ScenarioDAO
from pages.tts_helper import text_to_speech, create_tts_button, auto_play_prompt
import time

# Cache for scenarios to avoid repeated database calls
_scenario_cache = {}


def get_scenario(scenario_id):
    """Get a scenario with caching to avoid repeated database calls"""
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


def continue_to_next_phase():
    """Process continuing to the next phase in the current scenario"""
    # Clean up temporary feedback
    if 'temp_feedback' in st.session_state:
        del st.session_state.temp_feedback

    # Get scenarios to check if we need to move to the next scenario
    try:
        scenarios = get_all_scenarios()

        # Capture our current position
        current_scenario_index = st.session_state.get('current_scenario_index', 0)
        current_phase = st.session_state.get('current_phase')

        if current_phase:
            # Check if we've reached a terminal phase ("exit" or a phase starting with "end_")
            is_terminal_phase = (current_phase == "exit" or
                                 current_phase.startswith("end_") or
                                 st.session_state.get('scenario_completed', False))

            if is_terminal_phase:
                # Mark this scenario as completed in our tracking
                if 'scenario_completed_indexes' not in st.session_state:
                    st.session_state.scenario_completed_indexes = []

                if current_scenario_index not in st.session_state.scenario_completed_indexes:
                    st.session_state.scenario_completed_indexes.append(current_scenario_index)

                # Go to scenario selection page after completion
                if 'current_phase' in st.session_state:
                    del st.session_state.current_phase
                # Reset scenario completion flag
                st.session_state.scenario_completed = False
                st.session_state.page = 'scenario_selection'
            else:
                # For all other phases, go back to the scenario page to continue
                st.session_state.page = 'scenario'
        else:
            # No current phase, just go back to the scenario
            st.session_state.page = 'scenario'
    except Exception as e:
        # Default to scenario page if we can't determine next scenario
        st.session_state.page = 'scenario'

    # Minimal cleanup of played audio flags - only clean the current feedback audio
    current_scenario_id = st.session_state.get('current_scenario_id', 0)
    current_phase = st.session_state.get('current_phase', 'unknown')

    # Only clean audio flags directly related to this feedback
    feedback_key = f"feedback_{current_scenario_id}_{current_phase}"
    played_key = f"played_{feedback_key}"
    if played_key in st.session_state:
        del st.session_state[played_key]

    st.rerun()


def handle_continue_button():
    """Handle the continue button click event"""
    # Reset the parent alert flag
    st.session_state.show_parent_alert = False

    # Check if we're in a reminder phase that should progress to a specific next phase
    if st.session_state.get('reminder_phase', False) and 'next_after_reminder' in st.session_state:
        st.session_state.current_phase = st.session_state.next_after_reminder
        # Clear the reminder flags
        st.session_state.reminder_phase = False
        del st.session_state.next_after_reminder
        st.session_state.page = 'scenario'
        st.rerun()
        return

    # Check if this is a terminal phase
    is_terminal_phase = (st.session_state.get('current_phase') == "exit" or
                         st.session_state.get('current_phase', '').startswith("end_") or
                         st.session_state.get('scenario_completed', False))

    # After any phase, provide navigation options
    st.markdown("<div style='text-align: center; margin-top: 20px;'>", unsafe_allow_html=True)

    if is_terminal_phase:
        # For terminal phases, offer three options: new scenario, report, or home
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("Choose another scenario", key="goto_scenario_selection", use_container_width=True):
                # Reset phase for next scenario
                if 'current_phase' in st.session_state:
                    del st.session_state.current_phase
                st.session_state.page = 'scenario_selection'
                st.rerun()

        with col2:
            if st.button("View my progress", key="goto_report", use_container_width=True):
                st.session_state.page = 'report'
                st.rerun()

        with col3:
            if st.button("Go to home", key="goto_home", use_container_width=True):
                st.session_state.page = 'avatar_selection'
                st.rerun()
    else:
        # For regular phases, offer continue or choose another scenario
        col1, col2 = st.columns(2)

        with col1:
            if st.button("Continue with this scenario", key="continue_next_phase", use_container_width=True):
                continue_to_next_phase()

        with col2:
            if st.button("Choose another scenario", key="goto_scenario_selection", use_container_width=True):
                # Reset phase for next scenario
                if 'current_phase' in st.session_state:
                    del st.session_state.current_phase
                st.session_state.page = 'scenario_selection'
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    # JavaScript to automatically continue after a delay
    st.markdown("""
    <script>
    // Auto-continue after delay
    (function() {
        // Wait 5 seconds then click the continue button
        setTimeout(function() {
            const continueButton = document.querySelector('button[key="continue_next_phase"]');
            if (continueButton) {
                console.log('Auto-continuing to next phase');
                continueButton.click();
            } else {
                // For terminal phases, click scenario selection button
                const scenarioButton = document.querySelector('button[key="goto_scenario_selection"]');
                if (scenarioButton) {
                    console.log('Auto-continuing to scenario selection');
                    scenarioButton.click();
                }
            }
        }, 5000);  // 5 second delay
    })();
    </script>
    """, unsafe_allow_html=True)


def show_phase_feedback():
    """Display feedback for phase-based scenarios before proceeding to the next phase"""
    # Create a main container to prevent duplicate elements
    main_container = st.container()

    with main_container:
        # Get the temporary feedback saved from the phase handler
        if 'temp_feedback' not in st.session_state:
            # No feedback available, go back to scenario
            st.session_state.page = 'scenario'
            st.rerun()
            return

        feedback = st.session_state.temp_feedback

        # Display avatar reaction
        col1, col2 = st.columns([1, 3])
        with col1:
            emoji = "😊" if feedback.get("positive", False) else "🤔"
            st.markdown(
                f"<div style='text-align: center;'><span style='font-size: 80px;'>{st.session_state.selected_avatar['emoji']}</span><br><span style='font-size: 40px;'>{emoji}</span></div>",
                unsafe_allow_html=True)

        with col2:
            st.markdown(
                f"<div class='avatar-message'><h2>{st.session_state.selected_avatar['name']} says:</h2><p style='font-size: 20px;'>{feedback['text']}</p></div>",
                unsafe_allow_html=True)

        # Auto-play the feedback
        feedback_text = f"{st.session_state.selected_avatar['name']} says: {feedback['text']}"
        # Generate a simpler key for this feedback to avoid key explosion
        current_scenario_id = st.session_state.get('current_scenario_id', 0)
        current_phase = st.session_state.get('current_phase', 'unknown')
        feedback_key = f"feedback_{current_scenario_id}_{current_phase}"

        # Use cached audio playback
        auto_play_prompt(feedback_text, feedback_key)

        # Parent alert if needed
        if st.session_state.get('show_parent_alert', False):
            st.markdown("""
            <div class="alert">
                <h3>⚠️ Parent Alert</h3>
                <p>The system has detected potential emotional distress. A notification would be sent to the parent in a real implementation.</p>
            </div>
            """, unsafe_allow_html=True)

        # Add a countdown display for auto-continue
        st.markdown("""
        <div style="text-align: center; margin-top: 10px; opacity: 0.7;">
            <p>Continuing automatically in <span id="countdown">5</span> seconds...</p>
        </div>

        <script>
        // Countdown timer
        (function() {
            let seconds = 5;
            const countdown = document.getElementById('countdown');
            if (countdown) {
                const interval = setInterval(function() {
                    seconds--;
                    if (seconds < 0) {
                        clearInterval(interval);
                        return;
                    }
                    countdown.textContent = seconds;
                }, 1000);
            }
        })();
        </script>
        """, unsafe_allow_html=True)

        # Use a simpler, consistent key for the continue button
        continue_btn_key = f"continue_{current_scenario_id}_{current_phase}"

        # Display navigation options through handle_continue_button
        # This handles both terminal phases and regular phases
        handle_continue_button()