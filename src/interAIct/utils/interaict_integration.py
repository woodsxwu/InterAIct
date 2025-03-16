import streamlit as st
import time
import threading

# This file now serves as a compatibility layer for the WebRTC-based emotion detection
# Import WebRTC emotion detection functions
from utils.webrtc_emotion_detection import (
    setup_emotion_detection, 
    render_emotion_display, 
    get_emotion_feedback, 
    get_attention_state,
    is_child_distressed
)

class EmotionDetectionManager:
    """
    Manager for emotion detection integration with InterAIct application.
    Now delegates to WebRTC-based implementation.
    """
    
    _instance = None  # Singleton instance
    
    @classmethod
    def get_instance(cls):
        """Singleton pattern to ensure only one detector is active."""
        if cls._instance is None:
            cls._instance = EmotionDetectionManager()
        return cls._instance
    
    def __init__(self):
        """Initialize the emotion detection manager."""
        # Internal state
        self.running = False
        self.lock = threading.Lock()
        
        # Cache for UI elements
        self.emotion_cache = {
            "emotion": "Unknown",
            "confidence": 0.0,
            "attention": "Unknown",
            "timestamp": time.time()
        }
    
    def initialize(self):
        """Initialize emotion detection for the application."""
        # Nothing to do here with WebRTC approach
        pass
    
    def start(self):
        """Start emotion detection if not already running."""
        with self.lock:
            if self.running:
                return True
            
            # Update state
            self.running = True
            # Set session state for WebRTC
            st.session_state.camera_enabled = True
            return True
    
    def stop(self):
        """Stop emotion detection if running."""
        with self.lock:
            if not self.running:
                return
            
            # Update state
            self.running = False
            # Set session state for WebRTC
            st.session_state.camera_enabled = False
    
    def toggle(self):
        """Toggle emotion detection on/off."""
        if self.running:
            self.stop()
        else:
            self.start()
    
    def _db_callback(self, emotion, confidence):
        """Database callback - for compatibility only."""
        pass  # Handled by WebRTC implementation
    
    def is_running(self):
        """Check if emotion detection is running."""
        with self.lock:
            return self.running
    
    def is_child_distressed(self):
        """
        Check if the child appears distressed based on recent detections.
        Now delegates to WebRTC implementation.
        """
        return is_child_distressed()
    
    def get_current_emotion(self):
        """
        Get the current detected emotion.
        Now delegates to WebRTC implementation.
        """
        # Get emotion from WebRTC implementation
        emotion = get_emotion_feedback()
        attention = get_attention_state()
        
        # Format in the expected structure for compatibility
        return {
            "emotion": emotion,
            "confidence": 0.8,  # Default confidence
            "attention": attention,
            "timestamp": time.time()
        }
    
    def get_current_state(self):
        """
        Get the current state including frames and emotion data.
        
        Returns:
            tuple: (frame, result_dict)
        """
        # Get emotion from WebRTC implementation
        emotion = get_emotion_feedback()
        attention = get_attention_state()
        
        # Format in the expected structure for compatibility
        result = {
            "dominant_emotion": emotion,
            "confidence": 0.8,  # Default confidence
            "sustained_attention": attention,
            "timestamp": time.time()
        }
        
        # Return None for frames since WebRTC handles this differently
        return None, result


def initialize_emotion_detection():
    """Initialize emotion detection for the InterAIct application."""
    # Set up a compatibility instance but use WebRTC under the hood
    manager = EmotionDetectionManager.get_instance()
    
    # Check if camera is enabled in session state
    if st.session_state.get('camera_enabled', False):
        manager.start()
    else:
        manager.stop()


def render_emotion_detection_ui():
    """Render emotion detection UI elements in the InterAIct application."""
    # Only render if camera is enabled
    if st.session_state.get('camera_enabled', False):
        # Set up WebRTC streaming for emotion detection
        webrtc_ctx = setup_emotion_detection()
        
        # If WebRTC is active, render the emotion display
        if webrtc_ctx and webrtc_ctx.state.playing:
            render_emotion_display()
            
            # Also check for distress
            if is_child_distressed():
                st.warning("I notice you might be feeling upset. Would you like to take a short break?")


def get_emotion_feedback():
    """
    Generate feedback based on the child's detected emotion.
    Now delegates to WebRTC implementation.
    """
    return get_emotion_feedback()


def get_attention_state():
    """
    Get the current attention state of the child.
    Delegates to WebRTC implementation.
    """
    return get_attention_state()