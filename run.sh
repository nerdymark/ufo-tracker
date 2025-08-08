#!/bin/bash

# UFO Tracker Run Script
# Quick script to start the UFO Tracker application

set -e

echo "🛸 Starting UFO Tracker..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found"
    echo "Please run setup.sh first"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if configuration exists
if [ ! -f "config/config.py" ]; then
    echo "❌ Configuration file not found"
    echo "Please copy config/config.example.py to config/config.py"
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Check camera permissions
if ! groups | grep -q video; then
    echo "⚠️  Warning: User not in video group"
    echo "Camera access may be limited"
    echo "Run: sudo usermod -a -G video $USER"
    echo "Then logout and login again"
fi

# Start both services
echo "🚀 Launching UFO Tracker services..."
echo "Dashboard will be available at: http://$(hostname -I | awk '{print $1}'):5000"
echo "Camera streams available at: http://$(hostname -I | awk '{print $1}'):5001"
echo "Press Ctrl+C to stop"
echo ""

# Start camera service in background
echo "📷 Starting camera service on port 5001..."
python camera_service.py &
CAMERA_PID=$!

# Give camera service time to start
sleep 2

# Start API service in foreground
echo "🌐 Starting API service on port 5000..."
python api_service.py &
API_PID=$!

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping UFO Tracker services..."
    kill $CAMERA_PID 2>/dev/null || true
    kill $API_PID 2>/dev/null || true
    exit 0
}

# Set trap to cleanup on Ctrl+C
trap cleanup INT TERM

# Wait for services
wait
