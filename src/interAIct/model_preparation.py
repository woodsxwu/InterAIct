import onnxruntime as ort
import numpy as np
import cv2
import time
import os
import threading
from collections import deque


class EmotionDetector:
    """
    Real-time emotion detection module for the InterAIct project.
    Uses ONNX Runtime with Qualcomm Neural Processing SDK acceleration when available.
    
    This module:
    1. Processes camera input in real-time
    2. Detects emotions using the provided ONNX model
    3. Tracks attention state based on detected emotions
    4. Provides hooks for database integration and UI updates
    """
    
    def __init__(self, 
                 model_path=None, 
                 camera_id=0, 
                 emotion_labels=None,
                 db_callback=None):
        """
        Initialize the emotion detector.
        
        Args:
            model_path (str, optional): Path to the ONNX model file
            camera_id (int, optional): Camera device ID (default: 0 for primary camera)
            emotion_labels (list, optional): Custom emotion class labels
            db_callback (callable, optional): Callback function for database storage
        """
        # Define emotion labels (default or custom)
        self.emotion_labels = emotion_labels or [
            "Natural", "Anger", "Fear", "Joy", "Sadness", "Surprise"
        ]
        self.num_classes = len(self.emotion_labels)
        
        # Set default model path if not provided
        if model_path is None:
            # Get the current script's directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Default model path in models subdirectory
            model_path = os.path.join(current_dir, "models", "emotion_model.onnx")
        
        # Store model path
        self.model_path = model_path
        
        # Camera settings
        self.camera_id = camera_id
        self.camera = None
        self.frame_width = 640
        self.frame_height = 480
        self.fps = 30
        
        # Database callback for storing detections
        self.db_callback = db_callback
        
        # Threading management
        self.running = False
        self.detection_thread = None
        self.lock = threading.Lock()
        
        # Setup Qualcomm HTP execution provider options
        self.execution_provider_option = {
            "backend_path": "QnnHtp.dll",
            "enable_htp_fp16_precision": "1",
            "htp_performance_mode": "high_performance"
        }
        
        # Internal state tracking
        self.current_frame = None
        self.current_result = None
        self.last_update_time = 0
        self.update_interval = 0.5  # Update UI every 0.5 seconds
        
        # Attention tracking
        self.attention_history = deque(maxlen=10)
        
        # Performance tracking
        self.inference_times = deque(maxlen=30)
        
        # Initialize model (done once at startup)
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize the ONNX model with appropriate execution providers."""
        try:
            # First attempt to use QNN HTP acceleration
            print(f"Loading emotion model with QNN HTP acceleration...")
            self.session = ort.InferenceSession(
                self.model_path,
                providers=["QNNExecutionProvider"],
                provider_options=[self.execution_provider_option]
            )
            print("Emotion model loaded successfully with QNN HTP acceleration")
            
        except Exception as e:
            print(f"QNN HTP acceleration failed: {e}")
            print("Falling back to CPU execution provider")
            
            # Fallback to CPU provider if QNN fails
            try:
                self.session = ort.InferenceSession(
                    self.model_path,
                    providers=["CPUExecutionProvider"]
                )
                print("Emotion model loaded successfully with CPU provider")
            except Exception as e:
                print(f"Error loading model: {e}")
                raise RuntimeError(f"Failed to initialize emotion model: {e}")
        
        # Get model input/output details
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
        
        # Get input shape from model metadata
        self.input_shape = self.session.get_inputs()[0].shape
        print(f"Model input shape: {self.input_shape}")
        
        # Extract dimensions from input shape (typically NCHW format)
        if len(self.input_shape) == 4:  # NCHW format
            self.batch_size = 1  # Always process one frame at a time
            self.channels = self.input_shape[1]
            self.target_height = self.input_shape[2]
            self.target_width = self.input_shape[3]
        else:
            # Default values if shape is unexpected
            print("Warning: Unexpected input shape format, using default dimensions")
            self.batch_size = 1
            self.channels = 3
            self.target_height = 224
            self.target_width = 224
        
        print(f"Input dimensions: {self.target_width}x{self.target_height}, channels: {self.channels}")
    
    def start(self):
        """Start the emotion detection thread with camera input."""
        if self.running:
            print("Emotion detection is already running")
            return False
        
        # Initialize camera
        try:
            self.camera = cv2.VideoCapture(self.camera_id)
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
            self.camera.set(cv2.CAP_PROP_FPS, self.fps)
            
            if not self.camera.isOpened():
                raise RuntimeError(f"Failed to open camera with ID {self.camera_id}")
                
            # Start detection thread
            self.running = True
            self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
            self.detection_thread.start()
            print(f"Emotion detection started with camera ID {self.camera_id}")
            return True
            
        except Exception as e:
            print(f"Error starting emotion detection: {e}")
            if self.camera is not None:
                self.camera.release()
                self.camera = None
            return False
    
    def stop(self):
        """Stop the emotion detection thread and release resources."""
        if not self.running:
            return
        
        self.running = False
        
        # Wait for thread to finish
        if self.detection_thread is not None:
            self.detection_thread.join(timeout=1.0)
            self.detection_thread = None
        
        # Release camera
        if self.camera is not None:
            self.camera.release()
            self.camera = None
        
        print("Emotion detection stopped")
    
    def _detection_loop(self):
        """Main detection loop running in a separate thread."""
        while self.running:
            try:
                # Read frame from camera
                ret, frame = self.camera.read()
                if not ret:
                    print("Failed to capture frame from camera")
                    time.sleep(0.1)
                    continue
                
                # Store current frame for UI display
                with self.lock:
                    self.current_frame = frame.copy()
                
                # Process frame
                result = self._process_frame(frame)
                
                # Store result
                with self.lock:
                    self.current_result = result
                
                # Check if it's time to update database
                current_time = time.time()
                if current_time - self.last_update_time >= self.update_interval:
                    self._update_database(result)
                    self.last_update_time = current_time
                
                # Small delay to avoid maxing out CPU
                time.sleep(0.01)
                
            except Exception as e:
                print(f"Error in emotion detection loop: {e}")
                time.sleep(0.1)
    
    def _process_frame(self, frame):
        """
        Process a single frame for emotion detection.
        
        Args:
            frame (ndarray): Input BGR frame from camera
            
        Returns:
            dict: Detection results
        """
        # Preprocess the frame
        input_data = self._preprocess_frame(frame)
        
        # Run inference with timing
        start_time = time.time()
        outputs = self.session.run([self.output_name], {self.input_name: input_data})
        end_time = time.time()
        
        # Calculate execution time in milliseconds
        execution_time = (end_time - start_time) * 1000
        self.inference_times.append(execution_time)
        
        # Process results - get softmax probabilities
        emotion_probs = outputs[0][0]
        
        # Create dictionary mapping emotions to probabilities
        emotions = {}
        for i, label in enumerate(self.emotion_labels):
            if i < len(emotion_probs):
                emotions[label] = float(emotion_probs[i])
        
        # Get dominant emotion (highest probability)
        dominant_emotion = max(emotions.items(), key=lambda x: x[1])
        
        # Process attention state
        attention_result = self._analyze_attention(dominant_emotion[0], dominant_emotion[1])
        
        # Return complete result
        return {
            "timestamp": time.time(),
            "emotions": emotions,
            "dominant_emotion": dominant_emotion[0],
            "confidence": dominant_emotion[1],
            "execution_time_ms": execution_time,
            "avg_execution_time_ms": sum(self.inference_times) / len(self.inference_times),
            "attention_state": attention_result["attention_state"],
            "sustained_attention": attention_result["sustained_attention"]
        }
    
    def _preprocess_frame(self, frame):
        """
        Preprocess a video frame for emotion detection.
        
        Args:
            frame (ndarray): Input BGR frame from camera
            
        Returns:
            ndarray: Preprocessed input tensor ready for inference
        """
        # Make a copy to avoid modifying the original
        processed_frame = frame.copy()
        
        # Convert BGR to RGB if model expects RGB input
        if self.channels == 3:
            processed_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
        elif self.channels == 1:
            # Convert to grayscale if model expects single channel
            processed_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2GRAY)
        
        # Resize to the dimensions expected by the model
        processed_frame = cv2.resize(processed_frame, (self.target_width, self.target_height))
        
        # Normalize pixel values to [0,1] range
        processed_frame = processed_frame.astype(np.float32) / 255.0
        
        # Handle channel dimension based on model requirements
        if self.channels == 1:
            # Add channel dimension for grayscale
            processed_frame = np.expand_dims(processed_frame, axis=0)
        else:
            # Convert from HWC to CHW format (height, width, channels) -> (channels, height, width)
            processed_frame = np.transpose(processed_frame, (2, 0, 1))
        
        # Add batch dimension
        processed_frame = np.expand_dims(processed_frame, axis=0)
        
        return processed_frame
    
    def _analyze_attention(self, emotion, confidence):
        """
        Analyze attention state based on detected emotion.
        
        Args:
            emotion (str): Detected dominant emotion
            confidence (float): Detection confidence
            
        Returns:
            dict: Attention analysis results
        """
        # Map emotions to attention states based on defined rules
        if emotion in ["Natural", "Joy"] and confidence > 0.5:
            attention_state = "Attentive"
        elif emotion in ["Anger", "Surprise"]:
            attention_state = "Partially Attentive"
        elif emotion in ["Fear", "Sadness"]:
            attention_state = "Not Attentive"
        else:
            attention_state = "Unknown"
        
        # Add to attention history
        self.attention_history.append(attention_state)
        
        # Determine sustained attention state from history
        if self.attention_history.count("Unknown") == len(self.attention_history):
            sustained_attention = "Unknown"
        elif self.attention_history.count("Attentive") > len(self.attention_history) / 2:
            sustained_attention = "Attentive"
        elif self.attention_history.count("Not Attentive") > len(self.attention_history) / 2:
            sustained_attention = "Not Attentive"
        else:
            sustained_attention = "Partially Attentive"
        
        return {
            "attention_state": attention_state,
            "sustained_attention": sustained_attention,
            "history": list(self.attention_history)
        }
    
    def _update_database(self, result):
        """
        Update database with detection results using the callback.
        
        Args:
            result (dict): Detection results to store
        """
        if self.db_callback is not None:
            try:
                self.db_callback(
                    emotion=result["dominant_emotion"],
                    confidence=result["confidence"]
                )
            except Exception as e:
                print(f"Error updating emotion database: {e}")
    
    def get_current_state(self):
        """
        Get the current detection state (thread-safe).
        
        Returns:
            tuple: (frame, result) or (None, None) if not available
        """
        with self.lock:
            if self.current_frame is None or self.current_result is None:
                return None, None
            return self.current_frame.copy(), self.current_result.copy()
    
    def get_current_frame_with_overlay(self):
        """
        Get the current frame with detection results overlaid.
        
        Returns:
            ndarray: Frame with detection results, or None if not available
        """
        frame, result = self.get_current_state()
        
        if frame is None or result is None:
            return None
        
        # Create a copy for drawing
        overlay_frame = frame.copy()
        
        # Draw detection results
        emotion = result["dominant_emotion"]
        confidence = result["confidence"]
        attention = result["sustained_attention"]
        exec_time = result["execution_time_ms"]
        
        # Add info text
        cv2.putText(overlay_frame, f"Emotion: {emotion} ({confidence:.2f})", 
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(overlay_frame, f"Attention: {attention}", 
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(overlay_frame, f"Processing: {exec_time:.1f} ms", 
                    (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        return overlay_frame
    
    def is_child_distressed(self):
        """
        Check if the child appears distressed based on recent emotions.
        
        Returns:
            bool: True if distress is detected, False otherwise
        """
        if not self.running:
            return False
            
        with self.lock:
            if self.current_result is None:
                return False
                
            # Check if current emotion indicates distress
            emotion = self.current_result["dominant_emotion"]
            confidence = self.current_result["confidence"]
            
            return (emotion in ["Fear", "Sadness", "Anger"] and confidence > 0.7)


# Integration example with InterAIct project
def create_detector_for_interaict(db_callback=None):
    """
    Create and configure an emotion detector specifically for InterAIct project.
    
    Args:
        db_callback (callable): Callback function for database storage
        
    Returns:
        EmotionDetector: Configured detector instance
    """
    detector = EmotionDetector(
        # Model will be loaded from the default path
        db_callback=db_callback
    )
    
    return detector


# Standalone example for testing
if __name__ == "__main__":
    # Simple database callback for testing
    def test_db_callback(emotion, confidence):
        print(f"DB Update: {emotion} ({confidence:.2f})")
    
    # Create detector
    detector = EmotionDetector(db_callback=test_db_callback)
    
    # Start detection
    if detector.start():
        try:
            # Create display window
            cv2.namedWindow("Emotion Detection Test", cv2.WINDOW_NORMAL)
            
            # Main display loop
            while True:
                # Get current frame with detection overlay
                frame = detector.get_current_frame_with_overlay()
                
                if frame is not None:
                    # Display frame
                    cv2.imshow("Emotion Detection Test", frame)
                
                # Check for exit key (q)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                
                # Short sleep to prevent CPU overuse
                time.sleep(0.01)
                
        except KeyboardInterrupt:
            print("Interrupted by user")
        finally:
            # Stop detection and cleanup
            detector.stop()
            cv2.destroyAllWindows()
    else:
        print("Failed to start emotion detection")