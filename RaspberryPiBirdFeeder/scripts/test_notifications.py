#!/usr/bin/env python3
"""
Test script for notification services.
Use this to verify your notification configuration is working.
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from config_manager import ConfigManager
from notification_service import NotificationService


def main():
    print("=" * 50)
    print("  Bird Feeder Notification Test")
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

    # Validate configuration
    validation = config.validate()
    if validation['errors']:
        print("\nConfiguration errors:")
        for error in validation['errors']:
            print(f"  - {error}")
        print("\nPlease fix these errors before testing.")
        return

    if validation['warnings']:
        print("\nConfiguration warnings:")
        for warning in validation['warnings']:
            print(f"  - {warning}")

    # Initialize notification service
    print("\nInitializing notification service...")
    notifier = NotificationService(config)

    # Show enabled services
    enabled = notifier.get_enabled_services()
    print(f"\nEnabled notification services: {', '.join(enabled) if enabled else 'None'}")

    if not enabled:
        print("\nNo notification services are enabled!")
        print("Please edit your config.yaml and enable at least one service.")
        return

    # Run tests
    print("\n" + "-" * 50)
    print("Running notification tests...")
    print("-" * 50)

    results = notifier.test_notifications()

    # Display results
    print("\n" + "=" * 50)
    print("  Test Results")
    print("=" * 50)

    for service, success in results.items():
        status = "✓ Success" if success else "✗ Failed"
        print(f"  {service}: {status}")

    print()

    if all(results.values()):
        print("All tests passed! Your notifications are configured correctly.")
    else:
        print("Some tests failed. Please check your configuration and try again.")


if __name__ == '__main__':
    main()
