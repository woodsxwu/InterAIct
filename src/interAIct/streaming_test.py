import streamlit as st
from utils.webrtc_emotion_detection import setup_emotion_detection, render_emotion_display, get_emotion_feedback

# Set page configuration
st.set_page_config(
    page_title="WebRTC Emotion Detection Test",
    page_icon="🎥",
    layout="wide"
)

st.title("WebRTC Emotion Detection Test")

# Create a sidebar for controls
with st.sidebar:
    st.header("Controls")
    camera_enabled = st.toggle("Enable Camera", value=True)

# Only show WebRTC components if camera is enabled
if camera_enabled:
    st.header("Camera Feed")
    st.write("Please allow camera access when prompted by your browser.")
    
    # Setup WebRTC - This will create the video feed
    webrtc_ctx = setup_emotion_detection()
    
    # Display emotion data if WebRTC is active
    if webrtc_ctx.state.playing:
        st.success("Camera is active!")
        
        # Emotion display
        st.header("Detected Emotion")
        render_emotion_display()
        
        # Show the mapped emotion for the app
        st.header("Emotion Feedback")
        mapped_emotion = get_emotion_feedback()
        st.write(f"Emotion category for app feedback: **{mapped_emotion}**")
    else:
        st.warning("Camera is not active. Please allow camera access in your browser.")
else:
    st.info("Toggle 'Enable Camera' in the sidebar to start emotion detection.")

# Add some instructions
st.markdown("""
## Instructions

1. Toggle "Enable Camera" in the sidebar
2. Allow camera access when prompted by your browser
3. Your camera feed will appear with emotion detection 
4. Move your face and express different emotions to test

## Troubleshooting

- If the camera doesn't start, try refreshing the page
- Make sure no other application is using your camera
- Check that your browser has permission to access your camera
""")