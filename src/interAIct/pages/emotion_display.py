import streamlit as st

# This file now functions as a compatibility layer that delegates to the WebRTC implementation
# This prevents breaking existing code that might be calling these functions
from utils.webrtc_emotion_detection import (
    get_emotion_feedback as webrtc_get_emotion_feedback,
    render_emotion_display as webrtc_render_emotion_display
)

def render_sidebar_emotion_detection():
    """
    Create a real-time updating emotion detection display for the sidebar.
    Now delegates to the WebRTC implementation.
    """
    # This is a compatibility wrapper that delegates to the WebRTC implementation
    return webrtc_render_emotion_display()


def create_emotion_display(detector):
    """
    Create a dedicated component for displaying emotion detection results.
    Now delegates to the WebRTC implementation.
    
    Args:
        detector: The emotion detector instance (ignored in the WebRTC implementation)
    """
    # This function is maintained for compatibility but now delegates to the WebRTC implementation
    return webrtc_render_emotion_display()


def get_emotion_feedback():
    """
    Generate feedback based on the child's detected emotion.
    Now delegates to the WebRTC implementation.
    """
    return webrtc_get_emotion_feedback()