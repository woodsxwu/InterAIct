import streamlit as st
import av
import cv2
import numpy as np
import threading
import time
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
from model_preparation import EmotionProcessor
from database import db_service as db
from utils.session_manager import record_detected_emotion, record_attention_metric

# Global variables for thread-safe access to detection results
lock = threading.RLock()
latest_emotion = "neutral"
latest_confidence = 0.0
latest_face_frame = None
emotion_history = []
attention_history = []
latest_attention = "Unknown"
MAX_HISTORY = 10
is_distressed = False

# RTC Configuration with STUN servers for WebRTC
rtc_configuration = RTCConfiguration(
    {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
)

# Initialize the emotion processor once
emotion_processor = EmotionProcessor()


def video_frame_callback(frame):
    """Process video frames from WebRTC stream and detect emotions"""
    global latest_emotion, latest_confidence, latest_face_frame, emotion_history, is_distressed
    global attention_history, latest_attention
    
    # Get the image from the frame
    img = frame.to_ndarray(format="bgr24")
    
    # Process frame for emotion detection
    try:
        # Detect faces
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        # Process face if found
        if len(faces) > 0:
            # Process the largest face
            x, y, w, h = max(faces, key=lambda rect: rect[2] * rect[3])
            
            # Extract face region
            face_roi = img[y:y+h, x:x+w]
            
            # Draw face rectangle
            cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)
            
            # Store face frame for UI display
            with lock:
                latest_face_frame = face_roi.copy()
            
            # Run emotion detection
            result = emotion_processor.run_emotion_detection(face_roi)
            
            # Extract results
            emotions = result["emotions"]
            dominant_emotion = result["dominant_emotion"].lower()
            confidence = result.get("confidence", max(emotions.values()))
            
            # Update state with lock
            with lock:
                # Check if emotion has changed
                emotion_changed = latest_emotion != dominant_emotion
                
                latest_emotion = dominant_emotion
                latest_confidence = confidence
                
                # Add to history for distress analysis
                emotion_history.append({
                    "emotion": dominant_emotion,
                    "confidence": confidence,
                    "timestamp": time.time()
                })
                
                # Limit history size
                if len(emotion_history) > MAX_HISTORY:
                    emotion_history = emotion_history[-MAX_HISTORY:]
                
                # Check for distress emotions, but preserve the original emotion labels
                distress_count = sum(1 for entry in emotion_history 
                                   if entry["emotion"] in ["sadness", "fear", "anger"] 
                                   and entry["confidence"] > 0.7)
                is_distressed = distress_count >= 3
            
                # Process attention based on emotion
                attention_result = emotion_processor.process_attention(
                    {"dominant_emotion": dominant_emotion}, 
                    attention_history
                )
                
                attention_history = attention_result["attention_history"]
                latest_attention = attention_result["sustained_attention"]
            
            # Store in database if session ID is available
            session_id = st.session_state.get('db_session_id')
            if session_id:
                try:
                    # Record emotion if it changed or it's the first detection
                    if emotion_changed or len(emotion_history) == 1:
                        record_detected_emotion(dominant_emotion, confidence)
                    
                    # Record attention state (we'll record on changes or periodically)
                    if len(attention_history) == 1 or (len(attention_history) > 1 and attention_history[-1] != attention_history[-2]):
                        record_attention_metric(latest_attention, confidence)
                except Exception as e:
                    print(f"Error recording emotion/attention: {e}")
            
            # Draw emotion text on image
            cv2.putText(img, f"{dominant_emotion.capitalize()} ({confidence:.2f})", 
                       (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    
    except Exception as e:
        print(f"Error in video frame processing: {e}")
    
    # Return the processed frame with annotations
    return av.VideoFrame.from_ndarray(img, format="bgr24")


def get_emotion_feedback():
    """
    Get the detected emotion directly without mapping to broader categories.
    This preserves all original emotion labels from the model.
    """
    global latest_emotion, latest_confidence
    
    if not st.session_state.get('camera_enabled', False) or not st.session_state.get('webrtc_ctx_active', False):
        return "natural"  # Default when detection is off
    
    with lock:
        # Return the exact emotion detected
        return latest_emotion


def get_attention_state():
    """Get the current attention state of the child."""
    global latest_attention
    
    if not st.session_state.get('camera_enabled', False) or not st.session_state.get('webrtc_ctx_active', False):
        return "Unknown"  # Default when detection is off
    
    with lock:
        attention = latest_attention
    
    return attention


def is_child_distressed():
    """Check if the child appears distressed based on recent emotions"""
    global is_distressed
    with lock:
        return is_distressed


def setup_emotion_detection():
    """Set up WebRTC-based emotion detection and return the context"""
    webrtc_ctx = webrtc_streamer(
        key="emotion-detection",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=rtc_configuration,
        video_frame_callback=video_frame_callback,
        media_stream_constraints={"video": True, "audio": False},
        async_processing=True,
    )
    
    # Store the active state in session
    st.session_state.webrtc_ctx_active = webrtc_ctx.state.playing
    
    return webrtc_ctx


def render_emotion_display():
    """Render the emotion detection results"""
    # Get current emotion data
    with lock:
        emotion = latest_emotion
        confidence = latest_confidence
        face_frame = latest_face_frame
        attention = latest_attention
    
    # Create columns for display
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Map emotions to emojis
        emotion_emojis = {
            "natural": "😐",
            "neutral": "😐",
            "happy": "😊",
            "joy": "😄",
            "angry": "😠",
            "anger": "😠",
            "fear": "😨",
            "sad": "😢",
            "sadness": "😢",
            "surprise": "😲"
        }
        
        emoji = emotion_emojis.get(emotion, "😐")
        
        # Display emoji and emotion - use the original emotion label
        st.markdown(f"""
        <div style="text-align: center;">
            <div style="font-size: 60px; margin-bottom: 10px;">{emoji}</div>
            <div style="font-weight: bold; font-size: 24px;">{emotion.capitalize()}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Show face if available
        if face_frame is not None:
            face_rgb = cv2.cvtColor(face_frame, cv2.COLOR_BGR2RGB)
            st.image(face_rgb, caption="Detected Face", use_column_width=True)
        else:
            st.info("No face detected yet")
    
    # Display confidence bar
    st.markdown(f"**Confidence**: {confidence:.2f}")
    st.progress(min(confidence, 1.0))
    
    # Display attention state
    st.markdown(f"**Attention**: {attention}")
    
    # Map attention states to colors for visual feedback
    attention_colors = {
        "Attentive": "#7CFC00",       # Green
        "Partially Attentive": "#FFD700", # Yellow/gold
        "Not Attentive": "#FF6347",    # Red-ish
        "Unknown": "#A9A9A9"           # Gray
    }
    
    attention_color = attention_colors.get(attention, "#A9A9A9")
    
    # Display visual attention indicator
    st.markdown(f"""
    <div style="
        background-color: {attention_color}; 
        padding: 10px; 
        border-radius: 5px; 
        text-align: center;
        color: black;
        font-weight: bold;
        margin-bottom: 10px;">
        {attention}
    </div>
    """, unsafe_allow_html=True)
    
    # Check for distress, but don't categorize the emotions
    if is_child_distressed():
        st.warning("The system has detected signs of distress. Would you like to take a break?")