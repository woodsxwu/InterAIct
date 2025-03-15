import streamlit as st


def inject_custom_css_and_js():
    """Inject custom CSS and JavaScript for enhanced interactivity"""

    # Add custom CSS for interactive elements
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

        /* Animation for highlighted options */
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(66, 135, 245, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(66, 135, 245, 0); }
            100% { box-shadow: 0 0 0 0 rgba(66, 135, 245, 0); }
        }

        .option-card.highlighted {
            animation: pulse 2s infinite;
        }

        /* Video container styling */
        .video-container {
            position: relative;
            border-radius: 10px;
            overflow: hidden;
            margin-bottom: 20px;
        }

        /* Overlay for video status */
        .video-overlay {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
            background-color: rgba(0,0,0,0.5);
            color: white;
            font-size: 24px;
            z-index: 10;
        }
    </style>
    """, unsafe_allow_html=True)

    # Add JavaScript for enhanced interactivity
    st.markdown("""
    <script>
        // Function to play audio when hovering over options
        function setupOptionHoverAudio() {
            // Wait for DOM to be fully loaded
            setTimeout(() => {
                // Get all option cards
                const optionCards = document.querySelectorAll('.option-card');

                optionCards.forEach(card => {
                    // Get the option ID from the card
                    const optionId = card.id;
                    if (!optionId) return;

                    // Only attach listeners to enabled cards
                    if (!card.classList.contains('disabled')) {
                        // Find the corresponding audio button for this option
                        const audioBtn = document.querySelector(`button[data-option="${optionId}"]`);

                        if (audioBtn) {
                            // Add mouseover event listener
                            card.addEventListener('mouseenter', () => {
                                // Click the audio button to play the sound
                                audioBtn.click();
                            });
                        }
                    }
                });

                console.log('Hover audio listeners attached to options');
            }, 1000); // 1 second delay to ensure DOM is loaded
        }

        // Function to handle video playback and state communication
        function setupVideoHandling() {
            // This would handle actual video element in a real implementation
            console.log('Video handling initialized');

            // For demo: Dispatch event when video completes
            const videoContainer = document.querySelector('.video-container');
            if (videoContainer) {
                const videoElement = videoContainer.querySelector('video');
                if (videoElement) {
                    videoElement.onended = () => {
                        // Signal that video has completed
                        window.parent.postMessage({
                            type: 'streamlit:videoPlayed',
                            status: 'complete'
                        }, '*');

                        // Remove overlay if present
                        const overlay = videoContainer.querySelector('.video-overlay');
                        if (overlay) overlay.style.display = 'none';
                    };
                }
            }
        }

        // Initialize all interactive components
        function initInteractiveComponents() {
            setupOptionHoverAudio();
            setupVideoHandling();
        }

        // Run setup when page loads and after Streamlit re-renders
        document.addEventListener('DOMContentLoaded', initInteractiveComponents);

        // Also attach to Streamlit's render event
        window.addEventListener('message', (e) => {
            if (e.data.type === 'streamlit:render') {
                setTimeout(initInteractiveComponents, 100);
            }
        });
    </script>
    """, unsafe_allow_html=True)


def create_hover_audio_button(option_id, audio_text, visible=False):
    """
    Create a hidden button that can be triggered via JavaScript for mouseover audio

    Parameters:
    option_id (str): ID of the option this button is associated with
    audio_text (str): Text to be read when audio is played
    visible (bool): Whether to make the button visible (for debugging)

    Returns:
    None: Creates a button in the Streamlit app
    """
    # Generate a consistent key for this specific option
    button_key = f"hover_audio_{option_id}"

    # Create a button that's either hidden or visible (for debugging)
    display_style = "" if visible else "display:none; position:absolute;"

    # Create a button with data attribute linking it to the option
    st.markdown(f"""
    <button 
        id="{button_key}" 
        data-option="{option_id}" 
        style="{display_style}"
        onclick="playAudioForOption('{audio_text}')">
        🔊
    </button>
    """, unsafe_allow_html=True)


def play_audio_for_option(audio_text):
    """JavaScript function to play audio for an option using the TTS API"""
    st.markdown(f"""
    <script>
        function playAudioForOption(text) {{
            // Create audio element
            const audio = new Audio();

            // Use TTS API to generate audio
            const ttsUrl = `https://api.streamlit.io/text-to-speech?text=${{encodeURIComponent(text)}}`;
            audio.src = ttsUrl;

            // Play the audio
            audio.play();
        }}
    </script>
    """, unsafe_allow_html=True)


def create_video_container(video_path, image_fallback=None, autoplay=True):
    """
    Create a styled video container with overlay for video status

    Parameters:
    video_path (str): Path to the video file
    image_fallback (str): Path to fallback image if video can't be loaded
    autoplay (bool): Whether to autoplay the video

    Returns:
    None: Creates a video container in the Streamlit app
    """
    # Create a container for the video
    with st.container():
        st.markdown(f"""
        <div class="video-container">
            <div class="video-overlay" id="video-status-overlay">
                <span>Video is playing...</span>
            </div>
            <video 
                width="100%" 
                controls
                autoplay="{autoplay}"
                onended="videoEnded()"
                style="border-radius: 10px;">
                <source src="{video_path}" type="video/mp4">
                Your browser does not support the video tag.
            </video>
        </div>

        <script>
            function videoEnded() {
                // Signal that video has completed
                window.parent.postMessage({
                    type: 'streamlit:videoPlayed',
                    status: 'complete'
                }, '*');

                // Hide the overlay
                document.getElementById('video-status-overlay').style.display = 'none';
        }
        </script>
        """, unsafe_allow_html = True)

        # If video can't be loaded, display the fallback image
        if image_fallback:
            st.markdown(f"""
            <script>
                // Check if video fails to load
                document.querySelector('.video-container video').addEventListener('error', function() {{
                    // Replace video with fallback image
                    this.style.display = 'none';
                    const container = this.parentElement;
                    container.innerHTML += '<img src="{image_fallback}" style="width:100%; border-radius:10px;" />';

                    // Hide the overlay after a brief delay
                    setTimeout(() => {{
                        document.getElementById('video-status-overlay').style.display = 'none';
                    }}, 2000);

                    // Signal that we're using fallback
                    window.parent.postMessage({{
                        type: 'streamlit:videoFallback',
                        status: 'using_image'
                    }}, '*');
                }});
            </script>
            """, unsafe_allow_html=True)


def setup_guided_option_selection(options, current_index, cycle_complete):
    """
    Setup JavaScript for guided option selection with sequencing

    Parameters:
    options (list): List of option objects
    current_index (int): Index of the currently highlighted option
    cycle_complete (bool): Whether all options have been shown

    Returns:
    None: Injects JavaScript for option highlighting
    """
    # Convert options to a JavaScript-friendly string
    options_json = str(options).replace("'", '"')

    st.markdown(f"""
    <script>
        // Options data
        const options = {options_json};
        let currentIndex = {current_index};
        let cycleComplete = {str(cycle_complete).lower()};

        function highlightCurrentOption() {{
            // Remove highlight from all options
            document.querySelectorAll('.option-card').forEach(card => {{
                card.classList.remove('highlighted');
                card.classList.add('disabled');
            }});

            if (currentIndex >= 0 && currentIndex < options.length) {{
                // Highlight current option
                const optionId = options[currentIndex].option_id;
                const card = document.getElementById(`option_${{optionId}}`);

                if (card) {{
                    card.classList.add('highlighted');
                    card.classList.remove('disabled');

                    // Scroll to the highlighted option
                    card.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                }}
            }}

            // If cycle complete, enable all options
            if (cycleComplete) {{
                document.querySelectorAll('.option-card').forEach(card => {{
                    card.classList.remove('disabled');
                }});
            }}
        }}

        // Run highlight function when content loads
        document.addEventListener('DOMContentLoaded', highlightCurrentOption);
        window.addEventListener('load', highlightCurrentOption);

        // Also run after Streamlit rerenders
        window.addEventListener('message', (e) => {{
            if (e.data.type === 'streamlit:render') {{
                setTimeout(highlightCurrentOption, 100);
            }}
        }});
    </script>
    """, unsafe_allow_html=True)