#!/usr/bin/env python3
"""
Test script for camera functionality.
Use this to verify your camera is working correctly.
"""

import sys
import os
import time
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from config_manager import ConfigManager
from camera_module import CameraModule


def main():
    print("=" * 50)
    print("  Bird Feeder Camera Test")
    print("=" * 50)
    print()

    # Default config path
    config_path = '/home/pi/bird_feeder/config/config.yaml'

    # Check for command line argument
    if len(sys.argv) > 1:
        config_path = sys.argv[1]

    print(f"Loading config from: {config_path}")

    # Load configuration
    config = ConfigManager(config_path)

    # Initialize camera
    print("\nInitializing camera...")
    try:
        camera = CameraModule(config)
        print("Camera initialized successfully!")
    except Exception as e:
        print(f"Failed to initialize camera: {e}")
        print("\nTroubleshooting steps:")
        print("  1. Ensure camera is properly connected")
        print("  2. Run 'sudo raspi-config' and enable camera")
        print("  3. Check if camera module is detected: 'vcgencmd get_camera'")
        print("  4. Reboot the Raspberry Pi")
        return

    # Get camera info
    info = camera.get_camera_info()
    print("\nCamera Information:")
    print(f"  Type: {info['type']}")
    print(f"  Resolution: {info['resolution']}")
    print(f"  Framerate: {info['framerate']}")

    # Create test directory
    test_dir = Path('/tmp/bird_feeder_test')
    test_dir.mkdir(exist_ok=True)

    # Test photo capture
    print("\n" + "-" * 50)
    print("Testing photo capture...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    photo_path = test_dir / f"test_photo_{timestamp}.jpg"

    try:
        success = camera.capture_photo(str(photo_path))
        if success and photo_path.exists():
            size = photo_path.stat().st_size / 1024
            print(f"✓ Photo captured successfully!")
            print(f"  Path: {photo_path}")
            print(f"  Size: {size:.1f} KB")
        else:
            print("✗ Failed to capture photo")
    except Exception as e:
        print(f"✗ Error capturing photo: {e}")

    # Test frame capture (for detection)
    print("\n" + "-" * 50)
    print("Testing frame capture for detection...")
    try:
        frame = camera.capture_frame()
        if frame is not None:
            print(f"✓ Frame captured successfully!")
            print(f"  Shape: {frame.shape}")
            print(f"  Data type: {frame.dtype}")
        else:
            print("✗ Failed to capture frame")
    except Exception as e:
        print(f"✗ Error capturing frame: {e}")

    # Test video recording
    print("\n" + "-" * 50)
    print("Testing video recording (5 seconds)...")
    video_path = test_dir / f"test_video_{timestamp}.mp4"

    try:
        success = camera.record_video(str(video_path), duration=5)
        if success and video_path.exists():
            size = video_path.stat().st_size / 1024
            print(f"✓ Video recorded successfully!")
            print(f"  Path: {video_path}")
            print(f"  Size: {size:.1f} KB")
        else:
            print("✗ Failed to record video")
    except Exception as e:
        print(f"✗ Error recording video: {e}")

    # Cleanup
    print("\n" + "-" * 50)
    print("Cleaning up...")
    camera.cleanup()

    print("\n" + "=" * 50)
    print("  Camera Test Complete!")
    print("=" * 50)
    print(f"\nTest files saved to: {test_dir}")
    print("You can view them to verify camera is working correctly.")


if __name__ == '__main__':
    main()
