#!/bin/bash
# UFO Tracker - Installation Script for Systemd Service

set -e

echo "🛸 UFO Tracker - Service Installation Script"
echo "============================================="

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "❌ This script should NOT be run as root"
   echo "   Run it as the regular user (mark) instead"
   exit 1
fi

# Get the current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/ufo-tracker.service"
SYSTEMD_DIR="/etc/systemd/system"

echo "📍 UFO Tracker directory: $SCRIPT_DIR"
echo "📋 Service file: $SERVICE_FILE"

# Check if service file exists
if [ ! -f "$SERVICE_FILE" ]; then
    echo "❌ Service file not found: $SERVICE_FILE"
    exit 1
fi

# Check if user is in video group
if ! groups | grep -q video; then
    echo "⚠️  Adding user to video group for camera access..."
    sudo usermod -a -G video $USER
    echo "✅ User added to video group (logout/login required for full effect)"
fi

# Install the service file
echo "📦 Installing systemd service..."
sudo cp "$SERVICE_FILE" "$SYSTEMD_DIR/"
sudo chown root:root "$SYSTEMD_DIR/ufo-tracker.service"
sudo chmod 644 "$SYSTEMD_DIR/ufo-tracker.service"

# Reload systemd
echo "🔄 Reloading systemd..."
sudo systemctl daemon-reload

# Enable the service
echo "✅ Enabling UFO Tracker service..."
sudo systemctl enable ufo-tracker.service

# Show service status
echo ""
echo "📊 Service Status:"
sudo systemctl status ufo-tracker.service --no-pager || true

echo ""
echo "🎯 Installation Complete!"
echo ""
echo "Available commands:"
echo "  Start service:    sudo systemctl start ufo-tracker"
echo "  Stop service:     sudo systemctl stop ufo-tracker"
echo "  Restart service:  sudo systemctl restart ufo-tracker"
echo "  Service status:   sudo systemctl status ufo-tracker"
echo "  View logs:        sudo journalctl -u ufo-tracker -f"
echo "  Disable startup:  sudo systemctl disable ufo-tracker"
echo ""
echo "The service will start automatically on next boot."
echo "To start it now, run: sudo systemctl start ufo-tracker"
