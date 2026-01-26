#!/usr/bin/env python3
"""
Camera Module for Raspberry Pi Bird Feeder
Handles camera initialization, photo capture, and video recording.
Supports both PiCamera2 (newer) and legacy PiCamera.
"""

import os
import time
import logging
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import camera libraries
PICAMERA2_AVAILABLE = False
PICAMERA_AVAILABLE = False
OPENCV_AVAILABLE = False

try:
    from picamera2 import Picamera2
    from picamera2.encoders import H264Encoder, Quality
    from picamera2.outputs import FfmpegOutput
    PICAMERA2_AVAILABLE = True
    logger.info("PiCamera2 library available")
except ImportError:
    logger.warning("PiCamera2 not available")

try:
    from picamera import PiCamera
    PICAMERA_AVAILABLE = True
    logger.info("Legacy PiCamera library available")
except ImportError:
    logger.warning("Legacy PiCamera not available")

try:
    import cv2
    OPENCV_AVAILABLE = True
    logger.info("OpenCV available")
except ImportError:
    logger.warning("OpenCV not available")


class CameraModule:
    """Camera module for capturing photos and videos."""

    def __init__(self, config):
        """Initialize camera module."""
        self.config = config
        self.camera = None
        self.camera_type = None

        # Camera settings from config
        self.resolution = tuple(config.get('camera.resolution', [1920, 1080]))
        self.framerate = config.get('camera.framerate', 30)
        self.rotation = config.get('camera.rotation', 0)
        self.hflip = config.get('camera.horizontal_flip', False)
        self.vflip = config.get('camera.vertical_flip', False)

        # Initialize camera
        self._initialize_camera()

    def _initialize_camera(self):
        """Initialize the camera based on available libraries."""
        if PICAMERA2_AVAILABLE:
            self._init_picamera2()
        elif PICAMERA_AVAILABLE:
            self._init_legacy_picamera()
        elif OPENCV_AVAILABLE:
            self._init_opencv_camera()
        else:
            raise RuntimeError("No camera library available. Install picamera2, picamera, or opencv-python")

    def _init_picamera2(self):
        """Initialize PiCamera2 (recommended for newer Raspberry Pi OS)."""
        logger.info("Initializing PiCamera2...")

        self.camera = Picamera2()
        self.camera_type = 'picamera2'

        # Configure for still capture and video
        config = self.camera.create_still_configuration(
            main={"size": self.resolution, "format": "RGB888"},
            lores={"size": (640, 480), "format": "RGB888"},
            display="lores"
        )

        self.camera.configure(config)

        # Apply transformations
        if self.hflip or self.vflip:
            from libcamera import Transform
            transform = Transform(hflip=self.hflip, vflip=self.vflip)
            self.camera.set_controls({"Transform": transform})

        self.camera.start()

        # Allow camera to warm up
        time.sleep(2)
        logger.info("PiCamera2 initialized successfully")

    def _init_legacy_picamera(self):
        """Initialize legacy PiCamera."""
        logger.info("Initializing legacy PiCamera...")

        self.camera = PiCamera()
        self.camera_type = 'picamera'

        self.camera.resolution = self.resolution
        self.camera.framerate = self.framerate
        self.camera.rotation = self.rotation
        self.camera.hflip = self.hflip
        self.camera.vflip = self.vflip

        # Allow camera to warm up
        time.sleep(2)
        logger.info("Legacy PiCamera initialized successfully")

    def _init_opencv_camera(self):
        """Initialize OpenCV camera (fallback/USB cameras)."""
        logger.info("Initializing OpenCV camera...")

        camera_index = self.config.get('camera.device_index', 0)
        self.camera = cv2.VideoCapture(camera_index)
        self.camera_type = 'opencv'

        if not self.camera.isOpened():
            raise RuntimeError(f"Failed to open camera at index {camera_index}")

        # Set resolution
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
        self.camera.set(cv2.CAP_PROP_FPS, self.framerate)

        logger.info("OpenCV camera initialized successfully")

    def capture_frame(self) -> Optional[np.ndarray]:
        """Capture a single frame for detection."""
        try:
            if self.camera_type == 'picamera2':
                frame = self.camera.capture_array("lores")
                return frame

            elif self.camera_type == 'picamera':
                # Capture to numpy array
                output = np.empty((self.resolution[1], self.resolution[0], 3), dtype=np.uint8)
                self.camera.capture(output, 'rgb')
                return output

            elif self.camera_type == 'opencv':
                ret, frame = self.camera.read()
                if ret:
                    # Convert BGR to RGB
                    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                return None

        except Exception as e:
            logger.error(f"Error capturing frame: {e}")
            return None

    def capture_photo(self, filepath: str) -> bool:
        """Capture a high-resolution photo."""
        try:
            # Ensure directory exists
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)

            if self.camera_type == 'picamera2':
                # Capture full resolution image
                self.camera.capture_file(filepath)
                logger.info(f"Photo captured (PiCamera2): {filepath}")
                return True

            elif self.camera_type == 'picamera':
                self.camera.capture(filepath)
                logger.info(f"Photo captured (PiCamera): {filepath}")
                return True

            elif self.camera_type == 'opencv':
                ret, frame = self.camera.read()
                if ret:
                    cv2.imwrite(filepath, frame)
                    logger.info(f"Photo captured (OpenCV): {filepath}")
                    return True
                return False

        except Exception as e:
            logger.error(f"Error capturing photo: {e}")
            return False

    def record_video(self, filepath: str, duration: int = 10) -> bool:
        """Record video for specified duration."""
        try:
            # Ensure directory exists
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)

            if self.camera_type == 'picamera2':
                return self._record_video_picamera2(filepath, duration)

            elif self.camera_type == 'picamera':
                return self._record_video_legacy(filepath, duration)

            elif self.camera_type == 'opencv':
                return self._record_video_opencv(filepath, duration)

        except Exception as e:
            logger.error(f"Error recording video: {e}")
            return False

    def _record_video_picamera2(self, filepath: str, duration: int) -> bool:
        """Record video using PiCamera2."""
        try:
            encoder = H264Encoder()
            output = FfmpegOutput(filepath)

            self.camera.start_recording(encoder, output)
            time.sleep(duration)
            self.camera.stop_recording()

            logger.info(f"Video recorded (PiCamera2): {filepath}")
            return True
        except Exception as e:
            logger.error(f"PiCamera2 recording error: {e}")
            return False

    def _record_video_legacy(self, filepath: str, duration: int) -> bool:
        """Record video using legacy PiCamera."""
        try:
            # Record to H264 first
            h264_path = filepath.replace('.mp4', '.h264')
            self.camera.start_recording(h264_path)
            time.sleep(duration)
            self.camera.stop_recording()

            # Convert to MP4 using ffmpeg
            os.system(f'ffmpeg -y -i {h264_path} -c:v copy {filepath} 2>/dev/null')
            os.remove(h264_path)

            logger.info(f"Video recorded (PiCamera): {filepath}")
            return True
        except Exception as e:
            logger.error(f"Legacy PiCamera recording error: {e}")
            return False

    def _record_video_opencv(self, filepath: str, duration: int) -> bool:
        """Record video using OpenCV."""
        try:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(
                filepath,
                fourcc,
                self.framerate,
                (int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH)),
                 int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT)))
            )

            start_time = time.time()
            while time.time() - start_time < duration:
                ret, frame = self.camera.read()
                if ret:
                    out.write(frame)

            out.release()
            logger.info(f"Video recorded (OpenCV): {filepath}")
            return True
        except Exception as e:
            logger.error(f"OpenCV recording error: {e}")
            return False

    def start_preview(self):
        """Start camera preview (if supported)."""
        try:
            if self.camera_type == 'picamera2':
                self.camera.start_preview()
            elif self.camera_type == 'picamera':
                self.camera.start_preview()
            logger.info("Camera preview started")
        except Exception as e:
            logger.warning(f"Could not start preview: {e}")

    def stop_preview(self):
        """Stop camera preview."""
        try:
            if self.camera_type == 'picamera2':
                self.camera.stop_preview()
            elif self.camera_type == 'picamera':
                self.camera.stop_preview()
            logger.info("Camera preview stopped")
        except Exception as e:
            logger.warning(f"Could not stop preview: {e}")

    def cleanup(self):
        """Clean up camera resources."""
        try:
            if self.camera_type == 'picamera2':
                self.camera.stop()
                self.camera.close()
            elif self.camera_type == 'picamera':
                self.camera.close()
            elif self.camera_type == 'opencv':
                self.camera.release()

            logger.info("Camera resources cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up camera: {e}")

    def get_camera_info(self) -> dict:
        """Get camera information."""
        return {
            'type': self.camera_type,
            'resolution': self.resolution,
            'framerate': self.framerate,
            'rotation': self.rotation,
            'hflip': self.hflip,
            'vflip': self.vflip
        }
