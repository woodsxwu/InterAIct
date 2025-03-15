import streamlit as st
import time
from pages.tts_helper import text_to_speech
from interactive_components import (
    inject_custom_css_and_js,
    create_hover_audio_button,
    create_video_container,
    setup_guided_option_selection
)


class GuidedScenarioComponent:
    """
    A component that manages a video-first, guided option selection flow for scenarios.

    This component handles:
    1. Playing a video for each phase
    2. Reading the question aloud after video completes
    3. Sequentially highlighting and reading each option
    4. Enabling selection after all options have been presented
    5. Playing audio on mouseover for options
    """

    def __init__(self, scenario_id, phase_id):
        """
        Initialize the component with scenario and phase IDs

        Parameters:
        scenario_id (str/int): ID of the current scenario
        phase_id (str): ID of the current phase
        """
        self.scenario_id = scenario_id
        self.phase_id = phase_id
        self.component_id = f"guided_{scenario_id}_{phase_id}"

        # Initialize state variables if needed
        self._init_session_state()

        # Inject custom CSS and JavaScript for interactivity
        inject_custom_css_and_js()

    def _init_session_state(self):
        """Initialize required session state variables"""
        # Component-specific state keys
        prefix = f"{self.component_id}_"

        if f"{prefix}initialized" not in st.session_state:
            st.session_state[f"{prefix}initialized"] = True
            st.session_state[f"{prefix}video_played"] = False
            st.session_state[f"{prefix}question_read"] = False
            st.session_state[f"{prefix}current_option"] = -1
            st.session_state[f"{prefix}options_cycle_complete"] = False
            st.session_state[f"{prefix}last_option_time"] = 0

    def _get_state(self, key):
        """Get a component-specific state value"""
        return st.session_state.get(f"{self.component_id}_{key}")

    def _set_state(self, key, value):
        """Set a component-specific state value"""
        st.session_state[f"{self.component_id}_{key}"] = value

    def show_video(self, video_path, fallback_image=None):
        """
        Display the video for this phase

        Parameters:
        video_path (str): Path to the video file
        fallback_image (str): Path to fallback image if video can't be played

        Returns:
        bool: Whether the video has been played
        """
        # Check if video has already been played
        if self._get_state("video_played"):
            return True

        # Create a video container with the given video path
        with st.container():
            # Create video element with status overlay
            create_video_container(
                video_path=video_path,
                image_fallback=fallback_image,
                autoplay=True
            )

            # For demo purposes, we'll auto-advance after a delay
            # In a real implementation, this would be triggered by the video's onended event
            if "last_video_time" not in st.session_state:
                st.session_state.last_video_time = time.time()

            # Simulate video completion after 4 seconds
            if time.time() - st.session_state.last_video_time > 4:
                self._set_state("video_played", True)
                # Reset the timer for next video
                st.session_state.last_video_time = time.time()
                # Return True but also rerun to update UI
                st.rerun()

            # Show status message
            st.info("Please watch the video to continue...")

            return False

    def show_question(self, avatar_name, question_text):
        """
        Display and read aloud the question

        Parameters:
        avatar_name (str): Name of the avatar asking the question
        question_text (str): The question text

        Returns:
        bool: Whether the question has been read
        """
        # Only proceed if the video has been played
        if not self._get_state("video_played"):
            return False

        # Display the question
        st.markdown(
            f"<div class='avatar-message'><h2>{avatar_name} asks:</h2>"
            f"<p style='font-size: 20px;'>{question_text}</p></div>",
            unsafe_allow_html=True
        )

        # Read the question aloud if not done already
        if not self._get_state("question_read"):
            # Build the full text to read
            prompt_text = f"{avatar_name} asks: {question_text}"

            # Play the audio
            audio_html = text_to_speech(prompt_text, auto_play=True)
            st.markdown(audio_html, unsafe_allow_html=True)

            # Mark as read after a delay to allow audio to complete
            # In a real implementation, this would be triggered by an audio ended event
            if "question_start_time" not in st.session_state:
                st.session_state.question_start_time = time.time()

            # Wait about 3 seconds plus 0.1 second per character in the text
            wait_time = 3 + (len(prompt_text) * 0.1)
            if time.time() - st.session_state.question_start_time > wait_time:
                self._set_state("question_read", True)
                # Start option cycle
                self._set_state("current_option", 0)
                # Reset the timer
                st.session_state.question_start_time = time.time()
                # Return True but also rerun to update UI
                st.rerun()

            return False

        return True

    def show_options(self, options, emotion_icons, handle_selection_callback):
        """
        Display and manage the guided option selection process

        Parameters:
        options (list): List of option objects
        emotion_icons (dict): Mapping of emotions to emoji icons
        handle_selection_callback (function): Callback function when an option is selected

        Returns:
        bool: Whether an option was selected
        """
        # Only proceed if question has been read
        if not self._get_state("question_read"):
            return False

        # Get the current state
        current_option = self._get_state("current_option")
        options_cycle_complete = self._get_state("options_cycle_complete")

        # Setup JavaScript for guided option highlighting
        setup_guided_option_selection(
            options=options,
            current_index=current_option,
            cycle_complete=options_cycle_complete
        )

        # Calculate how many columns we need (max 2)
        num_options = len(options)
        num_columns = min(2, num_options)

        # Create columns for options
        cols = st.columns(num_columns)

        # Auto-advance through options
        if current_option >= 0 and not options_cycle_complete:
            # Check if we need to move to the next option
            if "last_option_time" not in st.session_state:
                st.session_state.last_option_time = time.time()

            # Get the current option being highlighted
            current_opt = options[current_option]

            # Play audio for the current option
            option_text = current_opt['text']
            st.markdown(text_to_speech(option_text, auto_play=True), unsafe_allow_html=True)

            # Wait for audio to complete (estimate based on length)
            wait_time = 2 + (len(option_text) * 0.1)  # 2 seconds + 0.1 second per character

            if time.time() - st.session_state.last_option_time > wait_time:
                # Time to move to next option
                next_option = current_option + 1

                if next_option >= len(options):
                    # We've cycled through all options
                    self._set_state("options_cycle_complete", True)
                    self._set_state("current_option", -1)  # Reset selection for user to choose
                else:
                    # Move to next option
                    self._set_state("current_option", next_option)

                # Reset the timer
                st.session_state.last_option_time = time.time()
                # Rerun to update the UI
                st.rerun()

        # Display options with appropriate styles based on current state
        selected_option = None

        for i, option in enumerate(options):
            col_index = i % num_columns
            with cols[col_index]:
                # Use the icon from the option if available, otherwise use the emotion icon
                display_icon = option.get('icon', emotion_icons.get(option.get('emotion', 'neutral'), "😐"))

                # Check if this option is currently highlighted in the guided selection
                is_highlighted = current_option == i
                is_selectable = options_cycle_complete or is_highlighted

                # Change the styling based on highlight state
                highlight_style = ""
                if is_highlighted:
                    # Highlighted style - make it stand out
                    highlight_style = "transform: scale(1.05); box-shadow: 0 0 15px rgba(0,0,0,0.2); border: 2px solid #4287f5;"
                elif not options_cycle_complete:
                    # Dimmed style for options not being highlighted during guided selection
                    highlight_style = "opacity: 0.6;"

                # Create the option card with appropriate styling
                option_id = f"option_{option['option_id']}"
                st.markdown(f"""
                <div class="option-card" id="{option_id}" style="{highlight_style}">
                    <div style="display: flex; align-items: center;">
                        <span style="font-size: 40px; margin-right: 15px;">{display_icon}</span>
                        <span style="font-size: 18px;">{option['text']}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Create the audio hover button (hidden but triggered by JavaScript)
                create_hover_audio_button(
                    option_id=option_id,
                    audio_text=option['text'],
                    visible=False
                )

                # Create button for selecting this option - only enabled if selectable
                button_key = f"select_{self.scenario_id}_{self.phase_id}_{option['option_id']}"

                if is_selectable:
                    if st.button(f"{display_icon} Choose", key=button_key, use_container_width=True):
                        # Call the selection callback
                        handle_selection_callback(option)
                        selected_option = option
                else:
                    # Disabled button styling
                    st.markdown(f"""
                    <div style="width: 100%; text-align: center; padding: 15px;
                                border-radius: 20px; background-color: #e0e0e0;
                                opacity: 0.6; color: #666666; font-weight: bold;">
                        {display_icon} Choose
                    </div>
                    """, unsafe_allow_html=True)

        # Display a helpful instruction
        if not self._get_state("video_played"):
            message = "Please watch the video to continue"
        elif not self._get_state("question_read"):
            message = "Listening to the question..."
        elif not options_cycle_complete:
            message = "Please watch and listen to all choices"
        else:
            message = "Hover over a choice to hear it again, then click to select"

        st.markdown(f"<div style='text-align: center; margin-top: 20px; opacity: 0.7;'>"
                    f"<p>{message}</p></div>",
                    unsafe_allow_html=True)

        return selected_option is not None

    def reset(self):
        """Reset all state variables for this component"""
        prefix = f"{self.component_id}_"

        for key in list(st.session_state.keys()):
            if key.startswith(prefix):
                del st.session_state[key]

        self._init_session_state()


# Example usage:
if __name__ == "__main__":
    st.title("Guided Scenario Demo")

    # Initialize component
    guided = GuidedScenarioComponent(scenario_id=1, phase_id="entering")

    # Show video
    video_played = guided.show_video(
        video_path="https://example.com/videos/scenario1_entering.mp4",
        fallback_image="https://placehold.co/600x400/9c88ff/FFF?text=Scenario+Video"
    )

    if video_played:
        # Show question
        question_read = guided.show_question(
            avatar_name="Buddy the Dog",
            question_text="What would you like to do?"
        )

        if question_read:
            # Define options
            options = [
                {"option_id": "a", "text": "Go introduce yourself to a group", "icon": "🙋", "emotion": "positive"},
                {"option_id": "b", "text": "Watch what games they're playing first", "icon": "👀", "emotion": "thoughtful"},
                {"option_id": "c", "text": "Play by yourself for now", "icon": "🧩", "emotion": "shy"}
            ]

            # Define emotion icons
            emotion_icons = {
                "positive": "😊",
                "negative": "😠",
                "thoughtful": "🤔",
                "shy": "😳"
            }

            # Define selection callback
            def handle_selection(option):
                st.success(f"Selected option: {option['option_id']}")

            # Show options
            guided.show_options(options, emotion_icons, handle_selection)