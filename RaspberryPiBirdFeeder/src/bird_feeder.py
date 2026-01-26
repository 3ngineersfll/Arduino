#!/usr/bin/env python3
"""
Raspberry Pi Bird Feeder Detection System
Main application that monitors bird feeder, detects birds, identifies species,
records video/photos, and sends notifications via SMS.
"""

import os
import sys
import time
import logging
import threading
import signal
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from camera_module import CameraModule
from bird_detector import BirdDetector
from bird_identifier import BirdIdentifier
from notification_service import NotificationService
from config_manager import ConfigManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/pi/bird_feeder/logs/bird_feeder.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BirdFeederSystem:
    """Main bird feeder monitoring system."""

    def __init__(self, config_path: str = None):
        """Initialize the bird feeder system."""
        self.config = ConfigManager(config_path)
        self.running = False
        self.detection_lock = threading.Lock()
        self.last_detection_time = 0
        self.cooldown_period = self.config.get('detection.cooldown_seconds', 30)

        # Initialize components
        logger.info("Initializing Bird Feeder System...")

        self.camera = CameraModule(self.config)
        self.detector = BirdDetector(self.config)
        self.identifier = BirdIdentifier(self.config)
        self.notifier = NotificationService(self.config)

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("Bird Feeder System initialized successfully")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()

    def start(self):
        """Start the bird feeder monitoring system."""
        logger.info("Starting Bird Feeder Monitoring System...")
        self.running = True

        # Start camera preview/stream if enabled
        if self.config.get('camera.enable_preview', False):
            self.camera.start_preview()

        # Main detection loop
        self._detection_loop()

    def stop(self):
        """Stop the bird feeder system."""
        logger.info("Stopping Bird Feeder System...")
        self.running = False
        self.camera.cleanup()
        logger.info("Bird Feeder System stopped")

    def _detection_loop(self):
        """Main loop for bird detection."""
        logger.info("Detection loop started")

        while self.running:
            try:
                # Capture frame for detection
                frame = self.camera.capture_frame()

                if frame is None:
                    logger.warning("Failed to capture frame")
                    time.sleep(0.5)
                    continue

                # Check for bird detection
                detection_result = self.detector.detect(frame)

                if detection_result['bird_detected']:
                    self._handle_bird_detection(frame, detection_result)

                # Control loop speed
                time.sleep(self.config.get('detection.interval_seconds', 0.5))

            except Exception as e:
                logger.error(f"Error in detection loop: {e}")
                time.sleep(1)

    def _handle_bird_detection(self, frame, detection_result):
        """Handle a bird detection event."""
        current_time = time.time()

        # Check cooldown to prevent spam
        with self.detection_lock:
            if current_time - self.last_detection_time < self.cooldown_period:
                logger.debug("Detection cooldown active, skipping...")
                return
            self.last_detection_time = current_time

        logger.info("Bird detected! Processing...")

        # Generate timestamp for file naming
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create capture directory for this detection
        capture_dir = Path(self.config.get('storage.capture_path', 'data/captures'))
        capture_dir.mkdir(parents=True, exist_ok=True)

        # Capture high-resolution photo
        photo_path = capture_dir / f"bird_{timestamp}.jpg"
        self.camera.capture_photo(str(photo_path))
        logger.info(f"Photo captured: {photo_path}")

        # Start video recording in background
        video_path = Path(self.config.get('storage.video_path', 'data/videos')) / f"bird_{timestamp}.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)

        video_thread = threading.Thread(
            target=self._record_video,
            args=(str(video_path),)
        )
        video_thread.start()

        # Identify bird species
        identification = self.identifier.identify(str(photo_path))

        # Prepare notification data
        bird_info = {
            'timestamp': timestamp,
            'species': identification.get('species', 'Unknown Bird'),
            'confidence': identification.get('confidence', 0),
            'scientific_name': identification.get('scientific_name', 'Unknown'),
            'photo_path': str(photo_path),
            'video_path': str(video_path),
            'detection_confidence': detection_result.get('confidence', 0),
            'bounding_box': detection_result.get('bounding_box', None),
            'wiki_url': identification.get('wiki_url', ''),
            'allaboutbirds_url': identification.get('allaboutbirds_url', '')
        }

        # Send notification
        self._send_notification(bird_info)

        # Wait for video recording to complete
        video_thread.join(timeout=self.config.get('video.duration_seconds', 10) + 5)

        logger.info(f"Bird detection processing complete: {bird_info['species']}")

    def _record_video(self, video_path: str):
        """Record video of the bird."""
        duration = self.config.get('video.duration_seconds', 10)
        logger.info(f"Recording {duration}s video to {video_path}")

        try:
            self.camera.record_video(video_path, duration)
            logger.info(f"Video recording complete: {video_path}")
        except Exception as e:
            logger.error(f"Error recording video: {e}")

    def _send_notification(self, bird_info: dict):
        """Send notification about bird detection."""
        try:
            # Compose message
            species = bird_info['species']
            confidence = bird_info['confidence'] * 100
            timestamp = bird_info['timestamp']

            message = (
                f"🐦 Bird Alert!\n"
                f"Species: {species}\n"
                f"Confidence: {confidence:.1f}%\n"
                f"Time: {timestamp}\n"
            )

            # Add bird info URL if available
            if bird_info.get('allaboutbirds_url'):
                message += f"\nLearn more: {bird_info['allaboutbirds_url']}"
            elif bird_info.get('wiki_url'):
                message += f"\nLearn more: {bird_info['wiki_url']}"

            # Send SMS notification
            self.notifier.send_sms(message)

            # Send photo via MMS if enabled
            if self.config.get('notifications.send_photo', True):
                self.notifier.send_mms(
                    f"Bird photo: {species}",
                    bird_info['photo_path']
                )

            # Optional: Send push notification
            if self.config.get('notifications.enable_push', False):
                self.notifier.send_push_notification(
                    title="Bird Detected!",
                    body=f"{species} spotted at your feeder",
                    data=bird_info
                )

            logger.info(f"Notifications sent for {species}")

        except Exception as e:
            logger.error(f"Error sending notification: {e}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Raspberry Pi Bird Feeder Detection System')
    parser.add_argument(
        '-c', '--config',
        default='/home/pi/bird_feeder/config/config.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create and start the system
    system = BirdFeederSystem(config_path=args.config)

    try:
        system.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        system.stop()


if __name__ == '__main__':
    main()
