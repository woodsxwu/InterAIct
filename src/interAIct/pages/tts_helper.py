import streamlit as st
import base64
from gtts import gTTS
import tempfile
import os
import hashlib
import time
import atexit
import threading

# Create a cache for TTS audio to avoid regenerating the same audio multiple times
_tts_cache = {}
_temp_files = []
_temp_files_lock = threading.Lock()

# Register cleanup function to remove temp files at exit
def _cleanup_temp_files():
    with _temp_files_lock:
        for file_path in _temp_files:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception:
                pass
        _temp_files.clear()

# Register the cleanup function
atexit.register(_cleanup_temp_files)

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
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_file.close()  # Close the file to allow gTTS to write to it
        
        try:
            # Generate speech audio file
            tts = gTTS(text=text, lang=language, slow=slow)
            tts.save(temp_file.name)
            
            # Read the audio file
            with open(temp_file.name, 'rb') as audio_file:
                audio_bytes = audio_file.read()
            
            # Add file to cleanup list - but don't delete now
            with _temp_files_lock:
                _temp_files.append(temp_file.name)
                
            # Encode audio to base64
            audio_b64 = base64.b64encode(audio_bytes).decode()
            
            # Cache the result (limit cache size to 50 items)
            if len(_tts_cache) >= 50:
                # Remove oldest item (first key)
                oldest_key = next(iter(_tts_cache))
                del _tts_cache[oldest_key]
            
            _tts_cache[cache_key] = audio_b64
            
        except Exception as e:
            print(f"Error generating TTS: {e}")
            return ""  # Return empty string on error

    # Create HTML audio player with proper autoplay attribute
    # The autoplay attribute needs to be "autoplay" not "true" or "false"
    autoplay_attr = "autoplay" if auto_play else ""
    display_style = "display:none;" if auto_play else ""
    
    audio_player = f"""
    <audio {autoplay_attr} controls style="{display_style}">
        <source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3">
        Your browser does not support the audio element.
    </audio>
    """

    return audio_player

# The rest of your functions can remain the same
def create_tts_button(text, button_text="🔊", key=None):
    """Creates a button that plays audio when clicked"""
    # Implementation remains the same
    pass

def auto_play_prompt(text, key=None):
    """Automatically plays the prompt/question audio"""
    # Implementation remains the same
    pass

def _cleanup_old_tts_keys():
    """Cleans up old TTS keys from session state"""
    # Implementation remains the same
    pass