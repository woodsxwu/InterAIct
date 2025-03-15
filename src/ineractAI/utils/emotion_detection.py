import streamlit as st
import time
import random
from database.db_schema import get_db_connection
from database import db_service as db
from utils.session_manager import record_detected_emotion


class EmotionDetector:
    """
    A placeholder for emotion detection functionality with database storage.
    In a real implementation, this would use computer vision to detect emotions.
    """

    def __init__(self, session_id=None):
        """Initialize the emotion detector"""
        self.enabled = False
        self.emotions = ["happy", "neutral", "confused", "frustrated", "sad"]
        self.current_emotion = "neutral"
        self.confidence = 0.0
        self.last_update = time.time()
        self.update_interval = 2.0  # Update emotion every 2 seconds (in simulation)
        self.session_id = session_id or st.session_state.get('db_session_id')

    def start(self):
        """Start the emotion detector"""
        self.enabled = True
        st.session_state.emotion_detector_running = True

    def stop(self):
        """Stop the emotion detector"""
        self.enabled = False
        st.session_state.emotion_detector_running = False

    def get_current_emotion(self):
        """
        Get the current detected emotion
        In a real implementation, this would process camera frames
        """
        # Check if it's time to update the emotion (for simulation)
        current_time = time.time()
        if current_time - self.last_update > self.update_interval:
            self._simulate_emotion_detection()
            self.last_update = current_time

            # Store the detected emotion in database
            if self.session_id:
                try:
                    record_detected_emotion(self.current_emotion, self.confidence)
                except Exception:
                    pass

            # Fallback to session state storage
            if 'detected_emotions' not in st.session_state:
                st.session_state.detected_emotions = []

            st.session_state.detected_emotions.append({
                "emotion": self.current_emotion,
                "confidence": self.confidence,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            })

        return {
            "emotion": self.current_emotion,
            "confidence": self.confidence
        }

    def _simulate_emotion_detection(self):
        """
        Simulate emotion detection for demonstration purposes
        In a real implementation, this would be replaced with actual computer vision
        """
        # Simulate emotion detection with random values
        emotion_index = random.randint(0, len(self.emotions) - 1)
        self.current_emotion = self.emotions[emotion_index]
        self.confidence = random.uniform(0.7, 0.95)  # Random confidence between 70-95%

    def is_child_distressed(self):
        """
        Check if the child appears distressed based on recent emotions
        In a real implementation, this would analyze emotion patterns
        """
        if not self.enabled:
            return False

        # Get the current emotion
        current = self.get_current_emotion()

        # Check if current emotion indicates distress
        distressed = current["emotion"] in ["frustrated", "sad"] and current["confidence"] > 0.8

        # Create parent alert if distressed
        if distressed and self.session_id:
            try:
                # Get current scenario and phase from session state
                scenario_id = st.session_state.get('current_scenario_id')
                phase_id = st.session_state.get('current_phase')

                if scenario_id and phase_id:
                    db.create_parent_alert(
                        self.session_id,
                        scenario_id,
                        phase_id,
                        current["emotion"]
                    )
            except Exception:
                pass

        return distressed


def initialize_emotion_detection():
    """Initialize the emotion detector in the session state"""
    if 'emotion_detector' not in st.session_state:
        st.session_state.emotion_detector = EmotionDetector(
            session_id=st.session_state.get('db_session_id')
        )

    # Update the enabled state based on camera toggle
    if 'camera_enabled' in st.session_state:
        if st.session_state.camera_enabled:
            st.session_state.emotion_detector.start()
        else:
            st.session_state.emotion_detector.stop()


def render_emotion_detection_ui():
    """Render UI elements for emotion detection (when enabled)"""
    if 'emotion_detector' not in st.session_state or not st.session_state.emotion_detector.enabled:
        return

    # Get the current detected emotion
    emotion_data = st.session_state.emotion_detector.get_current_emotion()

    # Display the emotion detection results in a small container
    with st.container():
        col1, col2 = st.columns([1, 3])
        with col1:
            # Map emotions to emojis
            emotion_emojis = {
                "happy": "😊",
                "neutral": "😐",
                "confused": "🤔",
                "frustrated": "😣",
                "sad": "😢"
            }
            emoji = emotion_emojis.get(emotion_data["emotion"], "😐")
            st.markdown(f"<div style='text-align: center; font-size: 40px;'>{emoji}</div>", unsafe_allow_html=True)

        with col2:
            st.markdown(f"**Detected mood:** {emotion_data['emotion'].capitalize()}")
            st.progress(emotion_data["confidence"])

    # Check if child appears distressed
    if st.session_state.emotion_detector.is_child_distressed():
        # Trigger parent alert if not already triggered
        if not st.session_state.show_parent_alert:
            st.session_state.show_parent_alert = True
            st.session_state.emotion = emotion_data["emotion"]
            st.warning(
                "The system has detected that you might be feeling frustrated or sad. Would you like to take a short break?")
            

def record_significant_mood_changes(emotion, confidence):
    """Log emotion changes only if they differ significantly from the last recorded emotion."""
    if "last_detected_emotion" not in st.session_state:
        st.session_state.last_detected_emotion = None  # Initialize
    
    # Record the first emotion or only log when it changes significantly
    if st.session_state.last_detected_emotion != emotion:
        st.session_state.last_detected_emotion = emotion  # Update stored emotion
        
        # Save in detected emotions timeline
        if "emotion_timeline" not in st.session_state:
            st.session_state.emotion_timeline = []

        st.session_state.emotion_timeline.append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "emotion": emotion,
            "confidence": confidence
        })

        # If distress is detected, trigger parent alert log
        if emotion in ["frustrated", "sad"] and confidence > 0.8:
            record_parent_alert(emotion)  # Log distress event
def get_emotion_feedback():
    """Generate feedback based on the child's detected emotion."""
    if "emotion_detector" not in st.session_state:
        return "No emotion detected."

    emotion_data = st.session_state.emotion_detector.get_current_emotion()
    emotion = emotion_data["emotion"]
    
    # Define feedback messages based on detected emotions
    feedback_messages = {
        "happy": "Great! You seem happy and engaged. Let's continue learning!",
        "neutral": "You seem neutral. Would you like to continue or take a short break?",
        "confused": "I see that you're confused. Let's try explaining things in a different way.",
        "frustrated": "I notice some frustration. Take a deep breath and let's try again together.",
        "sad": "You look a bit sad. Would you like to take a short break?"
    }

    return feedback_messages.get(emotion, "I'm here to help! Let me know how you're feeling.")
