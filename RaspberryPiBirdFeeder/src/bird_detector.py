#!/usr/bin/env python3
"""
Bird Detector Module
Uses motion detection combined with TensorFlow Lite object detection
to identify when birds are present at the feeder.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Try importing TensorFlow Lite
TFLITE_AVAILABLE = False
try:
    import tflite_runtime.interpreter as tflite
    TFLITE_AVAILABLE = True
    logger.info("TFLite Runtime available")
except ImportError:
    try:
        import tensorflow as tf
        tflite = tf.lite
        TFLITE_AVAILABLE = True
        logger.info("TensorFlow Lite available via TensorFlow")
    except ImportError:
        logger.warning("TensorFlow Lite not available")

# Try importing OpenCV for motion detection
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    logger.warning("OpenCV not available for motion detection")


class BirdDetector:
    """Detects birds using motion detection and object detection."""

    # COCO dataset bird-related class IDs
    BIRD_CLASS_IDS = [
        16,  # bird
    ]

    # Additional animal classes that might be at feeder
    ANIMAL_CLASS_IDS = [
        16,  # bird
        18,  # dog
        17,  # cat
        21,  # cow
        19,  # horse
        20,  # sheep
    ]

    def __init__(self, config):
        """Initialize the bird detector."""
        self.config = config
        self.interpreter = None
        self.input_details = None
        self.output_details = None

        # Motion detection settings
        self.motion_threshold = config.get('detection.motion_threshold', 25)
        self.min_area = config.get('detection.min_motion_area', 500)
        self.previous_frame = None

        # Detection confidence threshold
        self.confidence_threshold = config.get('detection.confidence_threshold', 0.5)

        # Detection mode
        self.use_ml = config.get('detection.use_ml_detection', True)
        self.use_motion = config.get('detection.use_motion_detection', True)

        # Initialize ML model if enabled
        if self.use_ml and TFLITE_AVAILABLE:
            self._load_model()

        logger.info(f"Bird detector initialized (ML: {self.use_ml}, Motion: {self.use_motion})")

    def _load_model(self):
        """Load the TensorFlow Lite model for object detection."""
        model_path = self.config.get(
            'detection.model_path',
            '/home/pi/bird_feeder/models/detect.tflite'
        )

        # Check for model file
        if not Path(model_path).exists():
            logger.warning(f"Model not found at {model_path}, will download on first run")
            self._download_model(model_path)

        try:
            # Load TFLite model
            self.interpreter = tflite.Interpreter(model_path=model_path)
            self.interpreter.allocate_tensors()

            # Get input and output details
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()

            # Get model input shape
            self.input_shape = self.input_details[0]['shape']
            logger.info(f"Model loaded successfully. Input shape: {self.input_shape}")

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self.interpreter = None

    def _download_model(self, model_path: str):
        """Download the object detection model."""
        import urllib.request

        # Create models directory
        Path(model_path).parent.mkdir(parents=True, exist_ok=True)

        # Use EfficientDet-Lite0 for good balance of speed and accuracy
        model_url = (
            "https://storage.googleapis.com/tfhub-lite-models/"
            "tensorflow/lite-model/efficientdet/lite0/detection/metadata/1.tflite"
        )

        logger.info(f"Downloading detection model from {model_url}...")

        try:
            urllib.request.urlretrieve(model_url, model_path)
            logger.info(f"Model downloaded to {model_path}")
        except Exception as e:
            logger.error(f"Failed to download model: {e}")

    def detect(self, frame: np.ndarray) -> Dict:
        """
        Detect birds in the frame.

        Args:
            frame: RGB image as numpy array

        Returns:
            Dictionary with detection results
        """
        result = {
            'bird_detected': False,
            'confidence': 0.0,
            'bounding_box': None,
            'motion_detected': False,
            'detections': []
        }

        # First check for motion (faster, early exit)
        if self.use_motion:
            motion_result = self._detect_motion(frame)
            result['motion_detected'] = motion_result['detected']

            if not motion_result['detected']:
                return result

        # If motion detected, run ML detection
        if self.use_ml and self.interpreter is not None:
            ml_result = self._detect_with_ml(frame)
            result.update(ml_result)
        elif self.use_motion and result['motion_detected']:
            # If only motion detection is enabled, treat motion as bird detection
            result['bird_detected'] = True
            result['confidence'] = 0.7  # Lower confidence for motion-only

        return result

    def _detect_motion(self, frame: np.ndarray) -> Dict:
        """
        Detect motion in the frame using frame differencing.

        Args:
            frame: RGB image as numpy array

        Returns:
            Dictionary with motion detection result
        """
        result = {'detected': False, 'area': 0, 'contours': []}

        if not OPENCV_AVAILABLE:
            return result

        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        # Initialize previous frame if needed
        if self.previous_frame is None:
            self.previous_frame = gray
            return result

        # Compute difference between frames
        frame_delta = cv2.absdiff(self.previous_frame, gray)
        thresh = cv2.threshold(frame_delta, self.motion_threshold, 255, cv2.THRESH_BINARY)[1]

        # Dilate to fill gaps
        thresh = cv2.dilate(thresh, None, iterations=2)

        # Find contours
        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        motion_detected = False
        total_area = 0

        for contour in contours:
            area = cv2.contourArea(contour)
            if area > self.min_area:
                motion_detected = True
                total_area += area

        # Update previous frame
        self.previous_frame = gray

        result['detected'] = motion_detected
        result['area'] = total_area
        result['contours'] = contours if motion_detected else []

        if motion_detected:
            logger.debug(f"Motion detected, area: {total_area}")

        return result

    def _detect_with_ml(self, frame: np.ndarray) -> Dict:
        """
        Detect birds using ML object detection.

        Args:
            frame: RGB image as numpy array

        Returns:
            Dictionary with ML detection results
        """
        result = {
            'bird_detected': False,
            'confidence': 0.0,
            'bounding_box': None,
            'detections': []
        }

        try:
            # Preprocess image
            input_data = self._preprocess_image(frame)

            # Run inference
            self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
            self.interpreter.invoke()

            # Get results
            boxes = self.interpreter.get_tensor(self.output_details[0]['index'])[0]
            classes = self.interpreter.get_tensor(self.output_details[1]['index'])[0]
            scores = self.interpreter.get_tensor(self.output_details[2]['index'])[0]

            # Process detections
            for i in range(len(scores)):
                if scores[i] >= self.confidence_threshold:
                    class_id = int(classes[i])

                    detection = {
                        'class_id': class_id,
                        'confidence': float(scores[i]),
                        'bounding_box': boxes[i].tolist()
                    }
                    result['detections'].append(detection)

                    # Check if it's a bird
                    if class_id in self.BIRD_CLASS_IDS:
                        result['bird_detected'] = True
                        if scores[i] > result['confidence']:
                            result['confidence'] = float(scores[i])
                            result['bounding_box'] = boxes[i].tolist()

                        logger.info(f"Bird detected with confidence: {scores[i]:.2f}")

        except Exception as e:
            logger.error(f"ML detection error: {e}")

        return result

    def _preprocess_image(self, frame: np.ndarray) -> np.ndarray:
        """
        Preprocess image for the ML model.

        Args:
            frame: RGB image as numpy array

        Returns:
            Preprocessed image tensor
        """
        # Get expected input size from model
        height = self.input_shape[1]
        width = self.input_shape[2]

        # Resize image
        if OPENCV_AVAILABLE:
            resized = cv2.resize(frame, (width, height))
        else:
            # Use PIL as fallback
            from PIL import Image
            img = Image.fromarray(frame)
            img = img.resize((width, height))
            resized = np.array(img)

        # Add batch dimension and convert to correct dtype
        input_data = np.expand_dims(resized, axis=0)

        # Check if model expects float or uint8
        if self.input_details[0]['dtype'] == np.float32:
            input_data = input_data.astype(np.float32) / 255.0
        else:
            input_data = input_data.astype(np.uint8)

        return input_data

    def set_motion_sensitivity(self, threshold: int, min_area: int):
        """
        Adjust motion detection sensitivity.

        Args:
            threshold: Motion threshold (lower = more sensitive)
            min_area: Minimum contour area to trigger detection
        """
        self.motion_threshold = threshold
        self.min_area = min_area
        logger.info(f"Motion sensitivity updated: threshold={threshold}, min_area={min_area}")

    def set_confidence_threshold(self, threshold: float):
        """
        Set ML detection confidence threshold.

        Args:
            threshold: Minimum confidence for detection (0.0 - 1.0)
        """
        self.confidence_threshold = threshold
        logger.info(f"Confidence threshold set to {threshold}")

    def reset_motion_baseline(self):
        """Reset the motion detection baseline frame."""
        self.previous_frame = None
        logger.info("Motion detection baseline reset")
