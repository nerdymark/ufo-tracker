# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

UFO Tracker is a Raspberry Pi-based dual-camera system for detecting and tracking unidentified flying objects. It uses OpenCV for motion detection, Flask for web streaming, and supports both infrared and high-quality cameras with different operational modes.

## Key Commands

### Development
```bash
# Setup (first time only)
./setup.sh

# Run the application
./run.sh
# or directly:
source venv/bin/activate && python app.py

# Install as service (auto-start on boot)
./install_service.sh

# Manual activation of virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Testing
```bash
# Test timelapse functionality
python test_timelapse.py

# Debug camera functionality
python debug_camera.py
```

### Service Management
```bash
# Start service
sudo systemctl start ufo-tracker

# Stop service  
sudo systemctl stop ufo-tracker

# Check service status
sudo systemctl status ufo-tracker

# View logs
sudo journalctl -u ufo-tracker -f
```

## Architecture Overview

### Core Components

**Camera System** (`camera/`)
- Dual-camera architecture with streaming objects for multi-viewer support
- `IRCamera` class handles infrared detection camera (motion detection focus)
- `HQCamera` class handles high-quality camera (detailed capture focus)  
- `CameraManager` orchestrates both cameras and handles initialization/cleanup
- Streaming objects allow concurrent access without camera conflicts

**Detection System** (`detection/`)
- `MotionDetector` performs real-time motion detection on IR camera feed
- `ObjectTracker` tracks detected objects across frames
- `ImageProcessor` handles advanced processing (stacking, alignment, enhancement)
- Detection results saved to `detections/` directory with timestamps

**Web Interface** (`app.py`, `templates/`, `static/`)
- Flask application serves multiple dashboard views
- MJPEG streaming for live camera feeds
- Frame endpoints for camera control with immediate feedback
- Advanced processing views (stacking, alignment)
- RESTful API endpoints for camera control and status

### Streaming Architecture

The system uses two distinct streaming modes:
1. **MJPEG streams** (`/ir_feed`, `/hq_feed`) - Continuous video for live viewing
2. **Frame endpoints** (`/ir_frame`, `/hq_frame`) - Single frames for camera controls

This dual approach eliminates mode confusion and provides optimal performance for each use case.

### Configuration

Configuration is centralized in `config/config.py` (copied from `config.example.py`):
- Camera indices and settings (resolution, framerate)
- Motion detection parameters (sensitivity, ROI)
- Web server settings (host, port, debug mode)
- File paths and storage settings

### Hardware Integration

- **Pan-Tilt Mechanism**: Placeholder in `hardware/pan_tilt.py` for future Waveshare stepper controller
- **Camera Access**: Requires user in `video` group (`sudo usermod -a -G video $USER`)
- **System Package**: `picamera2` installed via apt (not pip) for proper hardware access

## Important Considerations

1. **Raspberry Pi Specific**: This project is designed for Raspberry Pi with camera modules. Some features may not work on other platforms.

2. **Camera Permissions**: User must be in the `video` group for camera access. Logout/login required after group change.

3. **System Dependencies**: 
   - `python3-picamera2` must be installed via apt, not pip
   - `libcamera-dev` required for camera interface
   - OpenCV can be installed via pip or system packages

4. **Service Configuration**: The systemd service runs the app automatically on boot if configured during setup.

5. **Detection Storage**: Motion detection captures are saved to `detections/` directory with timestamps for later analysis.

6. **Multi-viewer Support**: The streaming object architecture allows multiple clients to view the same camera feed simultaneously without conflicts.

7. **Performance Optimization**: 
   - MJPEG streaming provides efficient browser-native video
   - Frame caching reduces load for multiple viewers
   - Configurable resolution and framerate for performance tuning

## File Structure Notes

- `app.py`: Main Flask application with route definitions
- `camera/`: Camera abstraction layer with streaming support
- `detection/`: Motion detection and object tracking algorithms
- `hardware/`: Hardware interface code (pan-tilt placeholder)
- `templates/`: HTML templates including unified dashboard
- `static/`: CSS and JavaScript for web interface
- `config/`: Configuration files (copy example to create config.py)
- `detections/`: Directory for saved detection images
- `logs/`: Application logs directory