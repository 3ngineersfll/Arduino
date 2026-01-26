# Raspberry Pi Bird Feeder Detection System

An intelligent bird feeder monitoring system that uses a Raspberry Pi with a camera to detect birds, identify species, record video/photos, and send notifications to your phone.

## Features

- **Bird Detection**: Uses motion detection + ML-based object detection to identify when birds arrive
- **Species Identification**: Identifies bird species using a trained neural network
- **Photo Capture**: Takes high-resolution photos when birds are detected
- **Video Recording**: Records video clips of bird visits
- **SMS Notifications**: Sends text message alerts via Twilio when birds are detected
- **Push Notifications**: Supports Pushover, Pushbullet, and IFTTT
- **Bird Information**: Includes links to bird databases with species information
- **Auto-start**: Runs as a system service, starts automatically on boot

## Hardware Requirements

### Required
- Raspberry Pi (3B+, 4, or 5 recommended)
- Raspberry Pi Camera Module (v2 or HQ) or USB webcam
- MicroSD card (16GB+ recommended)
- Power supply
- Bird feeder with mounting location for Pi

### Recommended
- Weatherproof enclosure for outdoor use
- Wi-Fi connection for notifications
- IR illuminator for night vision (with NoIR camera)

## Software Requirements

- Raspberry Pi OS (Bullseye or later recommended)
- Python 3.9+
- Camera enabled in raspi-config

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/your-repo/bird-feeder.git
cd bird-feeder/RaspberryPiBirdFeeder
```

### 2. Run the Setup Script

```bash
sudo ./scripts/setup.sh
```

This will:
- Install system dependencies
- Create a Python virtual environment
- Install Python packages
- Download ML models
- Set up the systemd service

### 3. Configure Notifications

Edit the configuration file:

```bash
nano /home/pi/bird_feeder/config/config.yaml
```

At minimum, configure one notification method. For SMS via Twilio:

```yaml
notifications:
  twilio:
    enabled: true
    account_sid: "your_twilio_account_sid"
    auth_token: "your_twilio_auth_token"
    from_number: "+1234567890"
    to_number: "+0987654321"
```

### 4. Test the System

Test camera:
```bash
/home/pi/bird_feeder/venv/bin/python /home/pi/bird_feeder/scripts/test_camera.py
```

Test notifications:
```bash
/home/pi/bird_feeder/venv/bin/python /home/pi/bird_feeder/scripts/test_notifications.py
```

### 5. Start the Service

```bash
sudo systemctl enable bird-feeder
sudo systemctl start bird-feeder
```

Check status:
```bash
sudo systemctl status bird-feeder
```

## Configuration Options

### Camera Settings

```yaml
camera:
  resolution: [1920, 1080]  # Width x Height
  framerate: 30
  rotation: 0               # 0, 90, 180, 270
  horizontal_flip: false
  vertical_flip: false
```

### Detection Settings

```yaml
detection:
  interval_seconds: 0.5     # Time between detection checks
  cooldown_seconds: 30      # Minimum time between alerts
  confidence_threshold: 0.5 # ML detection confidence (0-1)
  motion_threshold: 25      # Motion sensitivity (lower = more sensitive)
  use_ml_detection: true    # Enable ML-based detection
  use_motion_detection: true # Enable motion pre-filter
```

### Notification Services

#### Twilio (SMS/MMS)

1. Sign up at [twilio.com](https://www.twilio.com)
2. Get your Account SID and Auth Token from the dashboard
3. Get a phone number that can send SMS
4. Add configuration to `config.yaml`

```yaml
notifications:
  twilio:
    enabled: true
    account_sid: "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    auth_token: "your_auth_token"
    from_number: "+1234567890"
    to_number: "+0987654321"
```

#### Pushover (Push Notifications)

1. Sign up at [pushover.net](https://pushover.net)
2. Create an application to get an API token
3. Get your user key from the dashboard

```yaml
notifications:
  pushover:
    enabled: true
    app_token: "your_app_token"
    user_key: "your_user_key"
```

#### Pushbullet

1. Sign up at [pushbullet.com](https://www.pushbullet.com)
2. Go to Settings > Access Tokens
3. Create an access token

```yaml
notifications:
  pushbullet:
    enabled: true
    access_token: "your_access_token"
```

#### IFTTT Webhooks

1. Sign up at [ifttt.com](https://ifttt.com)
2. Create an applet with Webhooks trigger
3. Get your webhook key from the Webhooks service settings

```yaml
notifications:
  ifttt:
    enabled: true
    webhook_key: "your_webhook_key"
    event_name: "bird_detected"
```

### Environment Variables

Sensitive configuration can also be set via environment variables:

```bash
export BIRD_FEEDER_TWILIO_SID="your_sid"
export BIRD_FEEDER_TWILIO_TOKEN="your_token"
export BIRD_FEEDER_TWILIO_FROM="+1234567890"
export BIRD_FEEDER_TWILIO_TO="+0987654321"
```

## Project Structure

```
RaspberryPiBirdFeeder/
├── src/
│   ├── bird_feeder.py       # Main application
│   ├── camera_module.py     # Camera handling
│   ├── bird_detector.py     # Motion + ML detection
│   ├── bird_identifier.py   # Species identification
│   ├── notification_service.py  # SMS/Push notifications
│   └── config_manager.py    # Configuration handling
├── config/
│   └── config.yaml.example  # Example configuration
├── scripts/
│   ├── setup.sh             # Installation script
│   ├── bird-feeder.service  # systemd service file
│   ├── test_camera.py       # Camera test utility
│   └── test_notifications.py # Notification test utility
├── models/                  # ML models (auto-downloaded)
├── data/
│   ├── captures/           # Captured photos
│   └── videos/             # Recorded videos
├── requirements.txt
└── README.md
```

## How It Works

1. **Motion Detection**: The system continuously monitors camera frames for motion using frame differencing
2. **Object Detection**: When motion is detected, an ML model (EfficientDet-Lite) checks if the motion is a bird
3. **Photo/Video Capture**: Upon bird detection, a high-resolution photo and video clip are captured
4. **Species Identification**: The bird classifier model identifies the species from the photo
5. **Notification**: An SMS/push notification is sent with:
   - Species name and confidence
   - Timestamp
   - Link to bird information (AllAboutBirds.org)

## Supported Bird Species

The default classifier recognizes common North American feeder birds including:

- American Robin
- Northern Cardinal
- Blue Jay
- House Sparrow
- American Goldfinch
- Black-capped Chickadee
- House Finch
- Mourning Dove
- Ruby-throated Hummingbird
- Downy Woodpecker
- And many more...

## Troubleshooting

### Camera Not Working

```bash
# Check if camera is detected
vcgencmd get_camera

# Enable camera in raspi-config
sudo raspi-config
# Navigate to: Interface Options > Camera > Enable

# Reboot after enabling
sudo reboot
```

### Service Won't Start

```bash
# Check service status
sudo systemctl status bird-feeder

# View detailed logs
journalctl -u bird-feeder -f

# Check application logs
tail -f /home/pi/bird_feeder/logs/bird_feeder.log
```

### Notifications Not Sending

```bash
# Run notification test
/home/pi/bird_feeder/venv/bin/python /home/pi/bird_feeder/scripts/test_notifications.py

# Check API credentials
# Verify phone numbers include country code (+1 for US)
# Check Twilio dashboard for error logs
```

### Too Many False Detections

Adjust sensitivity in `config.yaml`:

```yaml
detection:
  motion_threshold: 30        # Increase to reduce sensitivity
  min_motion_area: 1000       # Increase minimum area
  confidence_threshold: 0.7   # Increase ML confidence requirement
  cooldown_seconds: 60        # Increase time between alerts
```

### Not Detecting Birds

```yaml
detection:
  motion_threshold: 20        # Decrease for more sensitivity
  min_motion_area: 300        # Decrease minimum area
  confidence_threshold: 0.4   # Lower ML confidence threshold
```

## License

MIT License - See LICENSE file for details.

## Acknowledgments

- TensorFlow Lite for efficient ML inference on Raspberry Pi
- AllAboutBirds.org for bird species information
- Twilio for SMS notification services
