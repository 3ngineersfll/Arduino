#!/usr/bin/env python3
"""
Configuration Manager Module
Handles loading, saving, and managing configuration for the bird feeder system.
"""

import os
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Try importing YAML library
YAML_AVAILABLE = False
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    logger.warning("PyYAML not available, using JSON for config")

import json


class ConfigManager:
    """Manages configuration for the bird feeder system."""

    DEFAULT_CONFIG = {
        # Camera settings
        'camera': {
            'resolution': [1920, 1080],
            'framerate': 30,
            'rotation': 0,
            'horizontal_flip': False,
            'vertical_flip': False,
            'enable_preview': False,
            'device_index': 0  # For USB cameras
        },

        # Detection settings
        'detection': {
            'interval_seconds': 0.5,
            'cooldown_seconds': 30,
            'use_ml_detection': True,
            'use_motion_detection': True,
            'confidence_threshold': 0.5,
            'motion_threshold': 25,
            'min_motion_area': 500,
            'model_path': '/home/pi/bird_feeder/models/detect.tflite'
        },

        # Bird identification settings
        'identification': {
            'model_path': '/home/pi/bird_feeder/models/bird_classifier.tflite',
            'labels_path': '/home/pi/bird_feeder/models/bird_labels.txt',
            'model_download_url': ''
        },

        # Video recording settings
        'video': {
            'duration_seconds': 10,
            'format': 'mp4',
            'quality': 'high'
        },

        # Storage settings
        'storage': {
            'capture_path': '/home/pi/bird_feeder/data/captures',
            'video_path': '/home/pi/bird_feeder/data/videos',
            'max_storage_gb': 10,
            'auto_cleanup': True,
            'retention_days': 30
        },

        # Notification settings
        'notifications': {
            'send_photo': True,
            'enable_push': False,
            'image_base_url': '',

            # Twilio SMS configuration
            'twilio': {
                'enabled': False,
                'account_sid': '',
                'auth_token': '',
                'from_number': '',
                'to_number': ''
            },

            # Pushover configuration
            'pushover': {
                'enabled': False,
                'app_token': '',
                'user_key': ''
            },

            # Pushbullet configuration
            'pushbullet': {
                'enabled': False,
                'access_token': ''
            },

            # IFTTT configuration
            'ifttt': {
                'enabled': False,
                'webhook_key': '',
                'event_name': 'bird_detected'
            },

            # Email configuration
            'email': {
                'enabled': False,
                'smtp_server': 'smtp.gmail.com',
                'smtp_port': 587,
                'username': '',
                'password': '',
                'to_address': ''
            }
        },

        # Web interface settings
        'web': {
            'enabled': False,
            'port': 8080,
            'host': '0.0.0.0'
        },

        # Logging settings
        'logging': {
            'level': 'INFO',
            'file': '/home/pi/bird_feeder/logs/bird_feeder.log',
            'max_size_mb': 10,
            'backup_count': 5
        }
    }

    def __init__(self, config_path: str = None):
        """
        Initialize configuration manager.

        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        self.config = self.DEFAULT_CONFIG.copy()

        # Deep copy default config
        self.config = self._deep_copy(self.DEFAULT_CONFIG)

        # Load configuration from file if provided
        if config_path:
            self.load(config_path)

        # Also check environment variables
        self._load_env_overrides()

    def _deep_copy(self, obj: Any) -> Any:
        """Create a deep copy of nested dict/list structure."""
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(item) for item in obj]
        else:
            return obj

    def load(self, config_path: str) -> bool:
        """
        Load configuration from file.

        Args:
            config_path: Path to configuration file

        Returns:
            True if loaded successfully
        """
        path = Path(config_path)

        if not path.exists():
            logger.warning(f"Config file not found: {config_path}")
            logger.info("Using default configuration")
            return False

        try:
            with open(path, 'r') as f:
                if path.suffix in ['.yaml', '.yml'] and YAML_AVAILABLE:
                    loaded_config = yaml.safe_load(f)
                else:
                    loaded_config = json.load(f)

            # Merge with defaults
            self._merge_config(self.config, loaded_config)
            logger.info(f"Configuration loaded from {config_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return False

    def save(self, config_path: str = None) -> bool:
        """
        Save configuration to file.

        Args:
            config_path: Path to save configuration (uses original path if not provided)

        Returns:
            True if saved successfully
        """
        path = Path(config_path or self.config_path)

        if not path:
            logger.error("No config path specified")
            return False

        try:
            # Ensure directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, 'w') as f:
                if path.suffix in ['.yaml', '.yml'] and YAML_AVAILABLE:
                    yaml.dump(self.config, f, default_flow_style=False)
                else:
                    json.dump(self.config, f, indent=2)

            logger.info(f"Configuration saved to {path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

    def _merge_config(self, base: dict, override: dict):
        """
        Recursively merge override config into base config.

        Args:
            base: Base configuration dictionary
            override: Override configuration dictionary
        """
        if override is None:
            return

        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def _load_env_overrides(self):
        """Load configuration overrides from environment variables."""
        # Map environment variables to config paths
        env_mapping = {
            'BIRD_FEEDER_TWILIO_SID': 'notifications.twilio.account_sid',
            'BIRD_FEEDER_TWILIO_TOKEN': 'notifications.twilio.auth_token',
            'BIRD_FEEDER_TWILIO_FROM': 'notifications.twilio.from_number',
            'BIRD_FEEDER_TWILIO_TO': 'notifications.twilio.to_number',
            'BIRD_FEEDER_PUSHOVER_TOKEN': 'notifications.pushover.app_token',
            'BIRD_FEEDER_PUSHOVER_USER': 'notifications.pushover.user_key',
            'BIRD_FEEDER_PUSHBULLET_TOKEN': 'notifications.pushbullet.access_token',
            'BIRD_FEEDER_IFTTT_KEY': 'notifications.ifttt.webhook_key',
            'BIRD_FEEDER_EMAIL_USER': 'notifications.email.username',
            'BIRD_FEEDER_EMAIL_PASS': 'notifications.email.password',
            'BIRD_FEEDER_EMAIL_TO': 'notifications.email.to_address',
        }

        for env_var, config_path in env_mapping.items():
            value = os.environ.get(env_var)
            if value:
                self.set(config_path, value)
                logger.debug(f"Config override from env: {config_path}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.

        Args:
            key: Configuration key (e.g., 'camera.resolution')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self.config

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any) -> bool:
        """
        Set a configuration value using dot notation.

        Args:
            key: Configuration key (e.g., 'camera.resolution')
            value: Value to set

        Returns:
            True if successful
        """
        keys = key.split('.')
        config = self.config

        try:
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]

            config[keys[-1]] = value
            return True
        except (KeyError, TypeError) as e:
            logger.error(f"Failed to set config {key}: {e}")
            return False

    def get_section(self, section: str) -> Dict:
        """
        Get an entire configuration section.

        Args:
            section: Section name (e.g., 'camera', 'notifications')

        Returns:
            Configuration section as dictionary
        """
        return self.config.get(section, {})

    def validate(self) -> Dict[str, list]:
        """
        Validate the configuration.

        Returns:
            Dictionary with 'errors' and 'warnings' lists
        """
        errors = []
        warnings = []

        # Check required directories exist or can be created
        for path_key in ['storage.capture_path', 'storage.video_path']:
            path = self.get(path_key)
            if path:
                try:
                    Path(path).mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    errors.append(f"Cannot create directory {path}: {e}")

        # Check notification configuration
        twilio = self.get_section('notifications').get('twilio', {})
        if twilio.get('enabled'):
            required_fields = ['account_sid', 'auth_token', 'from_number', 'to_number']
            for field in required_fields:
                if not twilio.get(field):
                    errors.append(f"Twilio enabled but missing: {field}")

        # Check detection configuration
        if self.get('detection.use_ml_detection'):
            model_path = self.get('detection.model_path')
            if model_path and not Path(model_path).exists():
                warnings.append(f"Detection model not found: {model_path}")

        # Validate camera settings
        resolution = self.get('camera.resolution', [])
        if len(resolution) != 2:
            errors.append("Camera resolution must be [width, height]")

        return {'errors': errors, 'warnings': warnings}

    def create_default_config(self, path: str):
        """
        Create a default configuration file.

        Args:
            path: Path to create the config file
        """
        config_path = Path(path)
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, 'w') as f:
            if config_path.suffix in ['.yaml', '.yml'] and YAML_AVAILABLE:
                yaml.dump(self.DEFAULT_CONFIG, f, default_flow_style=False)
            else:
                json.dump(self.DEFAULT_CONFIG, f, indent=2)

        logger.info(f"Default configuration created at {path}")

    def __repr__(self) -> str:
        return f"ConfigManager(path={self.config_path})"
