import streamlit as st
import cv2
import time
import threading
from emotion_detection_module import EmotionDetector
from database import db_service as db


class EmotionDetectionManager:
    """
    Manager for emotion detection integration with InterAIct application.
    
    This class handles:
    1. Initialization of emotion detection
    2. Thread-safe state management
    3. Streamlit UI integration
    4. Database integration
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
        self.detector = None
        self.running = False
        self.lock = threading.Lock()
        
        # UI update frequency control
        self.last_ui_update = 0
        self.ui_update_interval = 0.5  # Update UI every 0.5 seconds
        
        # Cache for UI elements
        self.emotion_cache = {
            "emotion": "Unknown",
            "confidence": 0.0,
            "attention": "Unknown",
            "timestamp": time.time()
        }
    
    def initialize(self):
        """Initialize emotion detection for the application."""
        # Create the detector with database callback
        if self.detector is None:
            self.detector = EmotionDetector(
                db_callback=self._db_callback
            )
    
    def start(self):
        """Start emotion detection if not already running."""
        with self.lock:
            if self.running:
                return True
            
            # Initialize if needed
            if self.detector is None:
                self.initialize()
            
            # Start the detector
            if self.detector.start():
                self.running = True
                return True
            return False
    
    def stop(self):
        """Stop emotion detection if running."""
        with self.lock:
            if not self.running:
                return
            
            if self.detector is not None:
                self.detector.stop()
                self.running = False
    
    def toggle(self):
        """Toggle emotion detection on/off."""
        if self.running:
            self.stop()
        else:
            self.start()
    
    def _db_callback(self, emotion, confidence):
        """
        Database callback for storing emotion detections.
        
        Args:
            emotion (str): Detected emotion
            confidence (float): Detection confidence
        """
        try:
            # Get current session ID from Streamlit session state
            session_id = st.session_state.get('db_session_id')
            if session_id is None:
                print("Warning: No session ID available for emotion detection database update")
                return
            
            # Record the emotion in the database
            db.record_emotion_detection(session_id, emotion, confidence)
            
            # Check for distress and create parent alert if needed
            if emotion in ["Sadness", "Fear", "Anger"] and confidence > 0.7:
                # Get current scenario and phase info
                scenario_id = st.session_state.get('current_scenario_id')
                phase_id = st.session_state.get('current_phase')
                
                if scenario_id is not None and phase_id is not None:
                    # Create parent alert
                    db.create_parent_alert(session_id, scenario_id, phase_id, emotion)
                    
                    # Set UI flag for parent alert
                    st.session_state.show_parent_alert = True
        
        except Exception as e:
            print(f"Error storing emotion detection: {e}")
    
    def is_running(self):
        """Check if emotion detection is running."""
        with self.lock:
            return self.running
    
    def is_child_distressed(self):
        """
        Check if the child appears distressed based on recent detections.
        
        Returns:
            bool: True if distress is detected, False otherwise
        """
        with self.lock:
            if not self.running or self.detector is None:
                return False
            return self.detector.is_child_distressed()
    
    def get_current_emotion(self):
        """
        Get the current detected emotion.
        
        Returns:
            dict: Current emotion state
        """
        # Check if it's time to update the UI
        current_time = time.time()
        if current_time - self.last_ui_update >= self.ui_update_interval:
            self.last_ui_update = current_time
            
            with self.lock:
                if not self.running or self.detector is None:
                    return self.emotion_cache
                
                # Get current detection state
                _, result = self.detector.get_current_state()
                
                if result is not None:
                    # Update cache with new values
                    self.emotion_cache = {
                        "emotion": result["dominant_emotion"],
                        "confidence": result["confidence"],
                        "attention": result["sustained_attention"],
                        "timestamp": result["timestamp"]
                    }
        
        # Return cached values (either fresh or from previous call)
        return self.emotion_cache
    
    def render_emotion_ui(self):
        """Render emotion detection UI elements in the Streamlit interface."""
        if not self.running:
            st.info("Emotion detection is not enabled. Enable it in the sidebar to see live emotion feedback.")
            return
        
        # Get current emotion state
        emotion_data = self.get_current_emotion()
        
        # Display the emotion detection results in a small container
        with st.container():
            col1, col2 = st.columns([1, 3])
            with col1:
                # Map emotions to emojis
                emotion_emojis = {
                    "Natural": "😐",
                    "Joy": "😊",
                    "Anger": "😠",
                    "Fear": "😨",
                    "Sadness": "😢",
                    "Surprise": "😲",
                    "Unknown": "❓"
                }
                
                emoji = emotion_emojis.get(emotion_data["emotion"], "❓")
                st.markdown(f"<div style='text-align: center; font-size: 40px;'>{emoji}</div>", unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"**Detected mood:** {emotion_data['emotion']}")
                st.progress(emotion_data["confidence"])
                st.caption(f"Attention state: {emotion_data['attention']}")


def initialize_emotion_detection():
    """Initialize emotion detection for the InterAIct application."""
    # Initialize manager
    manager = EmotionDetectionManager.get_instance()
    manager.initialize()
    
    # Check if camera is enabled in session state
    if st.session_state.get('camera_enabled', False):
        manager.start()
    else:
        manager.stop()


def render_emotion_detection_ui():
    """Render emotion detection UI elements in the InterAIct application."""
    manager = EmotionDetectionManager.get_instance()
    manager.render_emotion_ui()
    
    # Check for distress and trigger alert
    if manager.is_child_distressed():
        # Only show alert if not already showing
        if not st.session_state.get('show_parent_alert', False):
            st.session_state.show_parent_alert = True
            
            # Get current emotion
            emotion_data = manager.get_current_emotion()
            st.session_state.emotion = emotion_data["emotion"]
            
            # Display alert to user
            st.warning(
                f"I notice you might be feeling {emotion_data['emotion'].lower()}. Would you like to take a short break?"
            )


def get_emotion_feedback():
    """
    Generate feedback based on the child's detected emotion.
    
    Returns:
        str: The current detected emotion (for use in scenario logic)
    """
    manager = EmotionDetectionManager.get_instance()
    
    if not manager.is_running():
        return "neutral"
    
    emotion_data = manager.get_current_emotion()
    return emotion_data["emotion"].lower()