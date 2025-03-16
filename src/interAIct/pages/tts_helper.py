import base64
import tempfile
import os
import hashlib
import time

# Create a cache for TTS audio to avoid regenerating the same audio multiple times
_tts_cache = {}


def text_to_speech(text, language='en', slow=False, auto_play=False):
    """
    Convert text to speech using gTTS and return an HTML audio player.
    Uses caching to avoid regenerating the same audio multiple times.
    Respects the sound_enabled setting in session state.

    Parameters:
    text (str): The text to convert to speech
    language (str): Language code (default: 'en' for English)
    slow (bool): Whether to read the text slowly (default: False)
    auto_play (bool): Whether to automatically play the audio

    Returns:
    str: HTML audio player with the speech audio, or empty string if sound is disabled
    """
    # Check if sound is enabled in session state
    if not st.session_state.get('sound_enabled', True):
        return ""  # Return empty string if sound is disabled

    # Create a cache key from the text, language, and speed
    cache_key = hashlib.md5(f"{text}_{language}_{slow}".encode()).hexdigest()

    # Check if this audio is already in cache
    if cache_key in _tts_cache:
        audio_b64 = _tts_cache[cache_key]
    else:
        # Not in cache, need to generate
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
            # Generate speech audio file
            tts = gTTS(text=text, lang=language, slow=slow)
            tts.save(fp.name)

            # Read the audio file
            with open(fp.name, 'rb') as audio_file:
                audio_bytes = audio_file.read()

            # Clean up the temp file
            os.unlink(fp.name)

        # Encode audio to base64
        audio_b64 = base64.b64encode(audio_bytes).decode()

        # Cache the result (limit cache size to 50 items)
        if len(_tts_cache) >= 50:
            # Remove oldest item (first key)
            oldest_key = next(iter(_tts_cache))
            del _tts_cache[oldest_key]

        _tts_cache[cache_key] = audio_b64

    # Create HTML audio player with controls but hide it visually if auto-play is enabled
    # This prevents unnecessary UI elements while still allowing audio playback
    display_style = "display:none;" if auto_play else ""
    audio_player = f"""
    <audio autoplay={auto_play} controls style="{display_style}">
        <source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3">
        Your browser does not support the audio element.
    </audio>
    """

    return audio_player


def create_tts_button(text, button_text="🔊", key=None):
    """
    Create a button that will read text aloud when clicked without causing page refresh.
    Uses a simplified approach with Streamlit components.
    Respects the sound_enabled setting in session state.

    Parameters:
    text (str): The text to read aloud
    button_text (str): Text to display on the button
    key (str): A unique key for the button

    Returns:
    None: Shows the button in the Streamlit app
    """
    # Only show the button if sound is enabled
    if not st.session_state.get('sound_enabled', True):
        return

    # Generate a consistent key for the button
    button_key = key or f"tts_button_{hash(text) % 10000000}"  # Limit hash size
    play_key = f"play_{button_key}"

    # Add a button without using columns
    if st.button(button_text, key=button_key, help="Play audio"):
        st.session_state[play_key] = True

    # Show audio player if button was clicked and sound is enabled
    if st.session_state.get(play_key) and st.session_state.get('sound_enabled', True):
        # Add hidden audio element
        audio_html = text_to_speech(text, auto_play=True)
        st.markdown(f"<div style='display:none;'>{audio_html}</div>", unsafe_allow_html=True)

        # Reset state after a short delay to allow button to be clicked again
        st.session_state[play_key] = False


def auto_play_prompt(text, key=None):
    """
    Automatically play the prompt/question audio.
    Respects the sound_enabled setting in session state.

    Parameters:
    text (str): The text to convert to speech
    key (str): A unique key for the component

    Returns:
    None: Plays audio automatically if sound is enabled
    """
    # Generate a predictable key that doesn't depend on the full text hash
    # This prevents key explosion but still provides uniqueness
    if key is None:
        # Create a shorter, more stable key
        key = f"auto_prompt_{hash(text[:50]) % 10000000}"  # Use only first 50 chars and limit hash size

    component_key = key

    # Only play once per session state key and if sound is enabled
    if not st.session_state.get(f"played_{component_key}", False) and st.session_state.get('sound_enabled', True):
        audio_html = text_to_speech(text, auto_play=True)
        # Use a hidden container to prevent UI elements from showing
        st.markdown(f"<div style='display:none;'>{audio_html}</div>", unsafe_allow_html=True)
        st.session_state[f"played_{component_key}"] = True

    # Cleanup old played keys periodically (every ~5 minutes)
    # This prevents session state bloat over time
    if not hasattr(st.session_state, '_last_tts_cleanup'):
        st.session_state._last_tts_cleanup = time.time()
    elif time.time() - st.session_state._last_tts_cleanup > 300:  # 5 minutes
        _cleanup_old_tts_keys()
        st.session_state._last_tts_cleanup = time.time()


def _cleanup_old_tts_keys():
    """Clean up old TTS keys from session state to prevent bloat"""
    keys_to_remove = []
    current_keys = []

    # Find all played_auto_prompt keys
    for key in st.session_state.keys():
        if key.startswith('played_auto_prompt_'):
            # Keep the 20 most recently added keys
            current_keys.append(key)
            if len(current_keys) > 20:
                keys_to_remove.append(key)

    # Remove old keys
    for key in keys_to_remove:
        if key in st.session_state:
            del st.session_state[key]

    # Also clean up the TTS cache if it gets too large
    global _tts_cache
    if len(_tts_cache) > 50:
        # Keep only the 30 most recent items
        keys_to_keep = list(_tts_cache.keys())[-30:]
        _tts_cache = {k: _tts_cache[k] for k in keys_to_keep}