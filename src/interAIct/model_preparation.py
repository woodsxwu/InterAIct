import os
import time
import numpy as np
import cv2
import random

class EmotionProcessor:
    """
    A class to handle emotion detection using an ONNX model.
    This is a simplified version that simulates emotion detection for demonstration purposes.
    """
    
    def __init__(self, model_path=None):
        """Initialize the emotion detection model."""
        if model_path is None:
            # Get the current script's directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Default model path (doesn't need to exist for this simulation)
            model_path = os.path.join(current_dir, "models", "emotion_model.onnx")
        
        # Store model path
        self.model_path = model_path
        
        # Emotion labels - using the original categories requested
        self.emotion_labels = ["natural", "anger", "fear", "joy", "sadness", "surprise"]
        
        # Add state for more realistic simulation
        self.current_emotion = "natural"
        self.emotion_change_time = time.time()
        self.emotion_duration = random.uniform(3.0, 8.0)  # Stay in one emotion for 3-8 seconds
        
        # Add attention state for tracking
        self.current_attention = "Attentive"
        self.attention_change_time = time.time()
        self.attention_duration = random.uniform(5.0, 15.0)  # Attention state lasts 5-15 seconds
        
        # Log initialization
        print(f"Emotion model initialized (simulated). Would use model at: {self.model_path}")
        print(f"Target dimensions: 224x224, channels: 3")
    
    def preprocess_frame(self, frame):
        """Preprocess a video frame for the emotion model."""
        # Make a copy to avoid modifying the original
        processed_frame = frame.copy()
        
        # Convert BGR to RGB
        processed_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
        
        # Resize to target dimensions
        processed_frame = cv2.resize(processed_frame, (224, 224))
        
        # Normalize pixel values
        processed_frame = processed_frame.astype(np.float32) / 255.0
        
        # Convert from HWC to CHW format
        processed_frame = np.transpose(processed_frame, (2, 0, 1))
        
        # Add batch dimension
        processed_frame = np.expand_dims(processed_frame, axis=0)
        
        return processed_frame
    
    def run_emotion_detection(self, frame):
        """
        Simulate running emotion detection on the given frame.
        Provides a more realistic simulation with temporal consistency.
        """
        # Start timing
        start_time = time.time()
        
        # Check if it's time to change emotion
        if time.time() - self.emotion_change_time > self.emotion_duration:
            # Time to change - pick a new emotion
            # Weights adjusted to favor natural and joy more than negative emotions
            weights = [0.5, 0.1, 0.1, 0.2, 0.05, 0.05]  # natural, anger, fear, joy, sadness, surprise
            self.current_emotion = random.choices(self.emotion_labels, weights=weights)[0]
            self.emotion_change_time = time.time()
            self.emotion_duration = random.uniform(3.0, 8.0)
        
        # Generate emotion probabilities with the current emotion being dominant
        emotion_probs = np.random.rand(len(self.emotion_labels)) * 0.3  # Base probabilities
        
        # Make the current emotion dominant
        current_emotion_idx = self.emotion_labels.index(self.current_emotion)
        emotion_probs[current_emotion_idx] = random.uniform(0.6, 0.9)  # High confidence in current emotion
        
        # Normalize to sum to 1
        emotion_probs = emotion_probs / np.sum(emotion_probs)
        
        # Create a dictionary mapping emotions to probabilities
        emotions = {}
        for i, label in enumerate(self.emotion_labels):
            emotions[label] = float(emotion_probs[i])
        
        # Add a brief random delay to simulate processing time
        time.sleep(0.03)
        
        # Calculate execution time
        end_time = time.time()
        execution_time = (end_time - start_time) * 1000  # Convert to ms
        
        # Return results
        return {
            "emotions": emotions,
            "dominant_emotion": self.current_emotion,
            "confidence": emotions[self.current_emotion],
            "execution_time_ms": execution_time
        }
    
    def process_attention(self, emotion_result, attention_history, max_history=10):
        """
        Determine attention state based on emotion results.
        
        Args:
            emotion_result (dict): The result from emotion detection
            attention_history (list): List of previous attention states
            max_history (int): Maximum history to maintain
            
        Returns:
            dict: Containing current attention, sustained attention, and updated history
        """
        dominant_emotion = emotion_result.get("dominant_emotion", "natural")
        
        # Check if it's time to change attention state
        # This makes attention more persistent than emotions
        if time.time() - self.attention_change_time > self.attention_duration:
            # Time to potentially change attention
            # More likely to stay attentive than to become distracted
            if self.current_attention == "Attentive":
                # 70% chance to stay attentive
                self.current_attention = random.choices(
                    ["Attentive", "Partially Attentive", "Not Attentive"],
                    weights=[0.7, 0.2, 0.1]
                )[0]
            elif self.current_attention == "Partially Attentive":
                # Equal chance to improve or worsen
                self.current_attention = random.choices(
                    ["Attentive", "Partially Attentive", "Not Attentive"],
                    weights=[0.3, 0.4, 0.3]
                )[0]
            else:  # Not Attentive
                # 60% chance to stay not attentive
                self.current_attention = random.choices(
                    ["Attentive", "Partially Attentive", "Not Attentive"],
                    weights=[0.2, 0.2, 0.6]
                )[0]
            
            self.attention_change_time = time.time()
            self.attention_duration = random.uniform(5.0, 15.0)
        
        # Influence attention based on current emotion as well
        # For more realism, but with less weight than the temporal consistency
        emotion_based_attention = None
        if dominant_emotion in ["natural", "joy"]:
            emotion_based_attention = "Attentive"
        elif dominant_emotion in ["anger", "surprise"]:
            emotion_based_attention = "Partially Attentive"
        elif dominant_emotion in ["fear", "sadness"]:
            emotion_based_attention = "Not Attentive"
        
        # Small chance (25%) that the emotion will override the current attention state
        if emotion_based_attention and random.random() < 0.25:
            current_attention = emotion_based_attention
        else:
            current_attention = self.current_attention
        
        # Add to history (create a copy to avoid modifying the original)
        new_history = attention_history.copy() if attention_history else []
        new_history.append(current_attention)
        
        # Limit history size
        if len(new_history) > max_history:
            new_history = new_history[-max_history:]
        
        # Determine sustained attention from history
        if len(new_history) == 0:
            sustained_attention = "Unknown"
        elif new_history.count("Attentive") > len(new_history) / 2:
            sustained_attention = "Attentive"
        elif new_history.count("Not Attentive") > len(new_history) / 2:
            sustained_attention = "Not Attentive"
        else:
            sustained_attention = "Partially Attentive"
        
        return {
            "current_attention": current_attention,
            "sustained_attention": sustained_attention,
            "attention_history": new_history
        }