#!/bin/bash
#
# Bird Feeder Detection System - Setup Script
# Run this script on your Raspberry Pi to install and configure the system
#
# Usage: sudo ./setup.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Installation directory
INSTALL_DIR="/home/pi/bird_feeder"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Bird Feeder Detection System Setup   ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run this script as root (sudo ./setup.sh)${NC}"
    exit 1
fi

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo -e "${YELLOW}Warning: This doesn't appear to be a Raspberry Pi${NC}"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    MODEL=$(cat /proc/device-tree/model)
    echo -e "${GREEN}Detected: $MODEL${NC}"
fi

echo ""
echo -e "${YELLOW}Step 1: Updating system packages...${NC}"
apt-get update
apt-get upgrade -y

echo ""
echo -e "${YELLOW}Step 2: Installing system dependencies...${NC}"
apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    python3-picamera2 \
    libcamera-apps \
    ffmpeg \
    libatlas-base-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libopenblas-dev \
    libhdf5-dev \
    libhdf5-serial-dev \
    libhdf5-103

echo ""
echo -e "${YELLOW}Step 3: Creating installation directory...${NC}"
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/src"
mkdir -p "$INSTALL_DIR/config"
mkdir -p "$INSTALL_DIR/models"
mkdir -p "$INSTALL_DIR/data/captures"
mkdir -p "$INSTALL_DIR/data/videos"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/scripts"

echo ""
echo -e "${YELLOW}Step 4: Copying project files...${NC}"
cp -r "$PROJECT_DIR/src/"* "$INSTALL_DIR/src/"
cp "$PROJECT_DIR/config/config.yaml.example" "$INSTALL_DIR/config/"
cp "$PROJECT_DIR/requirements.txt" "$INSTALL_DIR/"
cp "$PROJECT_DIR/scripts/"* "$INSTALL_DIR/scripts/" 2>/dev/null || true

# Create config from example if it doesn't exist
if [ ! -f "$INSTALL_DIR/config/config.yaml" ]; then
    cp "$INSTALL_DIR/config/config.yaml.example" "$INSTALL_DIR/config/config.yaml"
    echo -e "${GREEN}Created config.yaml from example${NC}"
fi

echo ""
echo -e "${YELLOW}Step 5: Creating Python virtual environment...${NC}"
python3 -m venv "$INSTALL_DIR/venv"

echo ""
echo -e "${YELLOW}Step 6: Installing Python dependencies...${NC}"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install wheel
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

echo ""
echo -e "${YELLOW}Step 7: Downloading ML models...${NC}"
# Download EfficientDet-Lite model for object detection
MODEL_URL="https://storage.googleapis.com/tfhub-lite-models/tensorflow/lite-model/efficientdet/lite0/detection/metadata/1.tflite"
if [ ! -f "$INSTALL_DIR/models/detect.tflite" ]; then
    echo "Downloading object detection model..."
    wget -q -O "$INSTALL_DIR/models/detect.tflite" "$MODEL_URL" || {
        echo -e "${YELLOW}Could not download model. It will be downloaded on first run.${NC}"
    }
fi

echo ""
echo -e "${YELLOW}Step 8: Setting permissions...${NC}"
chown -R pi:pi "$INSTALL_DIR"
chmod +x "$INSTALL_DIR/src/bird_feeder.py"
chmod +x "$INSTALL_DIR/scripts/"*.sh 2>/dev/null || true

echo ""
echo -e "${YELLOW}Step 9: Enabling camera...${NC}"
# Check if camera is enabled in config.txt
if ! grep -q "start_x=1" /boot/config.txt 2>/dev/null; then
    if ! grep -q "camera_auto_detect=1" /boot/config.txt 2>/dev/null; then
        echo -e "${YELLOW}Camera may need to be enabled. Run 'sudo raspi-config' and enable camera.${NC}"
    fi
fi

echo ""
echo -e "${YELLOW}Step 10: Installing systemd service...${NC}"
cp "$INSTALL_DIR/scripts/bird-feeder.service" /etc/systemd/system/
systemctl daemon-reload

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Installation Complete!               ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Next steps:"
echo -e "  1. Edit the configuration file:"
echo -e "     ${YELLOW}nano $INSTALL_DIR/config/config.yaml${NC}"
echo ""
echo -e "  2. Configure your notification service (Twilio, Pushover, etc.)"
echo ""
echo -e "  3. Test the system:"
echo -e "     ${YELLOW}$INSTALL_DIR/venv/bin/python $INSTALL_DIR/src/bird_feeder.py -c $INSTALL_DIR/config/config.yaml${NC}"
echo ""
echo -e "  4. Enable auto-start on boot:"
echo -e "     ${YELLOW}sudo systemctl enable bird-feeder${NC}"
echo -e "     ${YELLOW}sudo systemctl start bird-feeder${NC}"
echo ""
echo -e "  5. Check service status:"
echo -e "     ${YELLOW}sudo systemctl status bird-feeder${NC}"
echo ""
echo -e "  6. View logs:"
echo -e "     ${YELLOW}tail -f $INSTALL_DIR/logs/bird_feeder.log${NC}"
echo ""
echo -e "${GREEN}Enjoy watching your bird visitors!${NC}"
