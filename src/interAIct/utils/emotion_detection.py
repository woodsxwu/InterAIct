import streamlit as st
import time

# This file now functions as a compatibility layer between the old emotion detection approach
# and the new WebRTC-based approach. Most functionality is delegated to webrtc_emotion_detection.py

# Import WebRTC emotion detection functions
from utils.webrtc_emotion_detection import (
    get_emotion_feedback as webrtc_get_emotion_feedback,
    get_attention_state as webrtc_get_attention_state,
    is_child_distressed as webrtc_is_distressed,
    setup_emotion_detection,
    render_emotion_display
)

class EmotionDetector:
    """
    Legacy EmotionDetector class that now delegates to WebRTC-based implementation.
    Maintained for backward compatibility with existing code.
    """

    def __init__(self, session_id=None, db_callback=None):
        """Initialize the emotion detector"""
        self.enabled = False
        self.session_id = session_id or st.session_state.get('db_session_id')
        self.db_callback = db_callback
        
        # Initialize minimal state for compatibility
        self.current_emotion = "neutral"
        self.confidence = 0.0
        self.sustained_attention = "Unknown"
        self.last_update = time.time()
    
    def start(self):
        """Start the emotion detector - delegates to WebRTC-based setup"""
        # Set the flag that would normally be used
        self.enabled = True
        st.session_state.emotion_detector_running = True
        return True
    
    def stop(self):
        """Stop the emotion detector"""
        self.enabled = False
        st.session_state.emotion_detector_running = False
    
    def get_current_emotion(self):
        """
        Get the current detected emotion using WebRTC-based detection
        """
        # Call WebRTC implementation and format result for compatibility
        emotion = webrtc_get_emotion_feedback()
        confidence = 0.8  # Using a default confidence value
        
        return {
            "emotion": emotion,
            "confidence": confidence,
            "attention": webrtc_get_attention_state(),  # Use the new attention function
            "timestamp": time.time()
        }
    
    def get_current_state(self):
        """
        Get the current state for compatibility
        
        Returns:
            tuple: (frame, result_dict)
        """
        # Get emotion data from WebRTC implementation
        emotion = webrtc_get_emotion_feedback()
        attention = webrtc_get_attention_state()
        
        # Return minimal compatible format
        result = {
            "dominant_emotion": emotion,
            "confidence": 0.8,  # Default confidence
            "sustained_attention": attention,  # Use the new attention state
            "timestamp": time.time()
        }
        
        # Return None for frames since WebRTC handles this differently
        return None, result
    
    def is_child_distressed(self):
        """
        Check if the child appears distressed - delegates to WebRTC implementation
        """
        return webrtc_is_distressed()


def initialize_emotion_detection():
    """Initialize emotion detection - now delegates to WebRTC setup"""
    # Maintain backward compatibility by setting up the legacy detector
    # in session state if it doesn't exist
    if 'emotion_detector' not in st.session_state:
        st.session_state.emotion_detector = EmotionDetector(
            session_id=st.session_state.get('db_session_id')
        )
    
    # Update the enabled state based on camera toggle
    if st.session_state.get('camera_enabled', False):
        if not st.session_state.get('emotion_detector_running', False):
            print("Starting emotion detector")
            st.session_state.emotion_detector.start()
            st.session_state.emotion_detector_running = True
    else:
        if st.session_state.get('emotion_detector_running', False):
            print("Stopping emotion detector")
            st.session_state.emotion_detector.stop()
            st.session_state.emotion_detector_running = False


def render_emotion_detection_ui():
    """
    Render emotion detection UI - now delegates to WebRTC implementation
    """
    # Only render if camera is enabled
    if st.session_state.get('camera_enabled', False):
        # Set up WebRTC streaming for emotion detection
        webrtc_ctx = setup_emotion_detection()
        
        # If WebRTC is active, render the emotion display
        if webrtc_ctx and webrtc_ctx.state.playing:
            render_emotion_display()
            
            # Also check for distress
            if webrtc_is_distressed():
                st.warning("I notice you might be feeling upset. Would you like to take a short break?")


def get_emotion_feedback():
    """
    Generate feedback based on the child's detected emotion.
    Now delegates to WebRTC implementation.
    """
    return webrtc_get_emotion_feedback()


def get_attention_state():
    """
    Get the current attention state of the child.
    Delegates to WebRTC implementation.
    """
    return webrtc_get_attention_state()