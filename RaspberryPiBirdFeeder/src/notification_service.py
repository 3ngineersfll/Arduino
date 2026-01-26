#!/usr/bin/env python3
"""
Notification Service Module
Handles sending notifications via SMS (Twilio), push notifications (Pushover/Pushbullet),
and email when birds are detected.
"""

import logging
import base64
import json
from pathlib import Path
from typing import Dict, Optional
import urllib.request
import urllib.parse

logger = logging.getLogger(__name__)

# Try importing notification libraries
TWILIO_AVAILABLE = False
PUSHOVER_AVAILABLE = False
REQUESTS_AVAILABLE = False

try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
    logger.info("Twilio library available")
except ImportError:
    logger.warning("Twilio not available - SMS notifications will use HTTP API")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    logger.warning("Requests library not available")


class NotificationService:
    """Service for sending notifications about bird detections."""

    def __init__(self, config):
        """Initialize the notification service."""
        self.config = config

        # Twilio configuration
        self.twilio_enabled = config.get('notifications.twilio.enabled', False)
        self.twilio_account_sid = config.get('notifications.twilio.account_sid', '')
        self.twilio_auth_token = config.get('notifications.twilio.auth_token', '')
        self.twilio_from_number = config.get('notifications.twilio.from_number', '')
        self.twilio_to_number = config.get('notifications.twilio.to_number', '')

        # Pushover configuration
        self.pushover_enabled = config.get('notifications.pushover.enabled', False)
        self.pushover_token = config.get('notifications.pushover.app_token', '')
        self.pushover_user = config.get('notifications.pushover.user_key', '')

        # Pushbullet configuration
        self.pushbullet_enabled = config.get('notifications.pushbullet.enabled', False)
        self.pushbullet_token = config.get('notifications.pushbullet.access_token', '')

        # IFTTT configuration
        self.ifttt_enabled = config.get('notifications.ifttt.enabled', False)
        self.ifttt_key = config.get('notifications.ifttt.webhook_key', '')
        self.ifttt_event = config.get('notifications.ifttt.event_name', 'bird_detected')

        # Email configuration
        self.email_enabled = config.get('notifications.email.enabled', False)
        self.smtp_server = config.get('notifications.email.smtp_server', '')
        self.smtp_port = config.get('notifications.email.smtp_port', 587)
        self.email_user = config.get('notifications.email.username', '')
        self.email_password = config.get('notifications.email.password', '')
        self.email_to = config.get('notifications.email.to_address', '')

        # Initialize Twilio client if available
        self.twilio_client = None
        if self.twilio_enabled and TWILIO_AVAILABLE:
            try:
                self.twilio_client = TwilioClient(
                    self.twilio_account_sid,
                    self.twilio_auth_token
                )
                logger.info("Twilio client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Twilio: {e}")

        logger.info("Notification service initialized")

    def send_sms(self, message: str) -> bool:
        """
        Send an SMS message.

        Args:
            message: The message to send

        Returns:
            True if successful, False otherwise
        """
        if not self.twilio_enabled:
            logger.warning("SMS notifications disabled")
            return False

        if self.twilio_client:
            return self._send_sms_twilio(message)
        else:
            return self._send_sms_http(message)

    def _send_sms_twilio(self, message: str) -> bool:
        """Send SMS using Twilio Python library."""
        try:
            response = self.twilio_client.messages.create(
                body=message,
                from_=self.twilio_from_number,
                to=self.twilio_to_number
            )
            logger.info(f"SMS sent successfully. SID: {response.sid}")
            return True
        except Exception as e:
            logger.error(f"Failed to send SMS via Twilio: {e}")
            return False

    def _send_sms_http(self, message: str) -> bool:
        """Send SMS using Twilio HTTP API directly."""
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_account_sid}/Messages.json"

            data = urllib.parse.urlencode({
                'Body': message,
                'From': self.twilio_from_number,
                'To': self.twilio_to_number
            }).encode()

            # Create request with authentication
            credentials = base64.b64encode(
                f"{self.twilio_account_sid}:{self.twilio_auth_token}".encode()
            ).decode()

            request = urllib.request.Request(url, data=data)
            request.add_header('Authorization', f'Basic {credentials}')
            request.add_header('Content-Type', 'application/x-www-form-urlencoded')

            response = urllib.request.urlopen(request, timeout=30)
            result = json.loads(response.read().decode())

            logger.info(f"SMS sent successfully. SID: {result.get('sid')}")
            return True

        except Exception as e:
            logger.error(f"Failed to send SMS via HTTP: {e}")
            return False

    def send_mms(self, message: str, image_path: str) -> bool:
        """
        Send an MMS message with an image.

        Args:
            message: The message to send
            image_path: Path to the image file

        Returns:
            True if successful, False otherwise
        """
        if not self.twilio_enabled:
            logger.warning("MMS notifications disabled")
            return False

        # For MMS, the image needs to be accessible via URL
        # Options: Upload to cloud storage, use local web server
        # For simplicity, we'll send just SMS with image info
        logger.info(f"MMS requested with image: {image_path}")

        # If you have a public URL for the image:
        image_url = self.config.get('notifications.image_base_url', '')
        if image_url:
            try:
                filename = Path(image_path).name
                media_url = f"{image_url}/{filename}"

                if self.twilio_client:
                    response = self.twilio_client.messages.create(
                        body=message,
                        from_=self.twilio_from_number,
                        to=self.twilio_to_number,
                        media_url=[media_url]
                    )
                    logger.info(f"MMS sent successfully. SID: {response.sid}")
                    return True
            except Exception as e:
                logger.error(f"Failed to send MMS: {e}")

        # Fallback to SMS only
        return self.send_sms(message)

    def send_push_notification(self, title: str, body: str, data: Dict = None) -> bool:
        """
        Send a push notification.

        Args:
            title: Notification title
            body: Notification body
            data: Additional data to include

        Returns:
            True if any notification was sent successfully
        """
        success = False

        if self.pushover_enabled:
            success = self._send_pushover(title, body, data) or success

        if self.pushbullet_enabled:
            success = self._send_pushbullet(title, body, data) or success

        if self.ifttt_enabled:
            success = self._send_ifttt(title, body, data) or success

        return success

    def _send_pushover(self, title: str, body: str, data: Dict = None) -> bool:
        """Send notification via Pushover."""
        try:
            url = "https://api.pushover.net/1/messages.json"

            params = {
                'token': self.pushover_token,
                'user': self.pushover_user,
                'title': title,
                'message': body,
                'priority': 0
            }

            # Add URL if available
            if data and data.get('allaboutbirds_url'):
                params['url'] = data['allaboutbirds_url']
                params['url_title'] = 'Learn about this bird'

            post_data = urllib.parse.urlencode(params).encode()
            request = urllib.request.Request(url, data=post_data)

            response = urllib.request.urlopen(request, timeout=30)
            result = json.loads(response.read().decode())

            if result.get('status') == 1:
                logger.info("Pushover notification sent successfully")
                return True
            else:
                logger.error(f"Pushover error: {result}")
                return False

        except Exception as e:
            logger.error(f"Failed to send Pushover notification: {e}")
            return False

    def _send_pushbullet(self, title: str, body: str, data: Dict = None) -> bool:
        """Send notification via Pushbullet."""
        try:
            url = "https://api.pushbullet.com/v2/pushes"

            # Add link if available
            if data and data.get('allaboutbirds_url'):
                push_type = 'link'
                params = {
                    'type': push_type,
                    'title': title,
                    'body': body,
                    'url': data['allaboutbirds_url']
                }
            else:
                push_type = 'note'
                params = {
                    'type': push_type,
                    'title': title,
                    'body': body
                }

            post_data = json.dumps(params).encode()
            request = urllib.request.Request(url, data=post_data)
            request.add_header('Access-Token', self.pushbullet_token)
            request.add_header('Content-Type', 'application/json')

            response = urllib.request.urlopen(request, timeout=30)

            logger.info("Pushbullet notification sent successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to send Pushbullet notification: {e}")
            return False

    def _send_ifttt(self, title: str, body: str, data: Dict = None) -> bool:
        """Send notification via IFTTT webhook."""
        try:
            url = f"https://maker.ifttt.com/trigger/{self.ifttt_event}/with/key/{self.ifttt_key}"

            params = {
                'value1': title,
                'value2': body,
                'value3': data.get('allaboutbirds_url', '') if data else ''
            }

            post_data = json.dumps(params).encode()
            request = urllib.request.Request(url, data=post_data)
            request.add_header('Content-Type', 'application/json')

            response = urllib.request.urlopen(request, timeout=30)

            logger.info("IFTTT webhook triggered successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to trigger IFTTT webhook: {e}")
            return False

    def send_email(self, subject: str, body: str, image_path: str = None) -> bool:
        """
        Send an email notification.

        Args:
            subject: Email subject
            body: Email body
            image_path: Optional path to image attachment

        Returns:
            True if successful, False otherwise
        """
        if not self.email_enabled:
            logger.warning("Email notifications disabled")
            return False

        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from email.mime.base import MIMEBase
            from email import encoders

            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email_user
            msg['To'] = self.email_to
            msg['Subject'] = subject

            # Add body
            msg.attach(MIMEText(body, 'plain'))

            # Add image attachment if provided
            if image_path and Path(image_path).exists():
                with open(image_path, 'rb') as f:
                    img_data = f.read()

                attachment = MIMEBase('image', 'jpeg')
                attachment.set_payload(img_data)
                encoders.encode_base64(attachment)
                attachment.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{Path(image_path).name}"'
                )
                msg.attach(attachment)

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_user, self.email_password)
                server.send_message(msg)

            logger.info("Email notification sent successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def test_notifications(self) -> Dict[str, bool]:
        """
        Test all configured notification methods.

        Returns:
            Dictionary with test results for each method
        """
        results = {}

        test_message = "Test notification from Bird Feeder System"

        if self.twilio_enabled:
            results['sms'] = self.send_sms(f"[TEST] {test_message}")

        if self.pushover_enabled:
            results['pushover'] = self._send_pushover(
                "Test",
                test_message,
                {'allaboutbirds_url': 'https://www.allaboutbirds.org'}
            )

        if self.pushbullet_enabled:
            results['pushbullet'] = self._send_pushbullet(
                "Test",
                test_message,
                {'allaboutbirds_url': 'https://www.allaboutbirds.org'}
            )

        if self.ifttt_enabled:
            results['ifttt'] = self._send_ifttt("Test", test_message)

        if self.email_enabled:
            results['email'] = self.send_email(
                "Test - Bird Feeder System",
                test_message
            )

        logger.info(f"Notification test results: {results}")
        return results

    def get_enabled_services(self) -> list:
        """Get list of enabled notification services."""
        services = []
        if self.twilio_enabled:
            services.append('twilio_sms')
        if self.pushover_enabled:
            services.append('pushover')
        if self.pushbullet_enabled:
            services.append('pushbullet')
        if self.ifttt_enabled:
            services.append('ifttt')
        if self.email_enabled:
            services.append('email')
        return services
