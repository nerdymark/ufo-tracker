# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

UFO Tracker is a Raspberry Pi-based dual-camera system for detecting and tracking unidentified flying objects. It uses OpenCV for motion detection, Flask for web streaming, and supports both infrared and high-quality cameras with different operational modes. The system now includes complete pan-tilt control with WASD keyboard integration.

## Key Commands

### Development
```bash
# Setup (first time only)
./setup.sh

# Run the application
./run.sh
# or directly:
source venv/bin/activate && python app.py

# The system now uses multiple services:
# - api_service.py (main API, port 5000) - includes pan-tilt endpoints
# - camera_service.py (camera streams, port 5001)
# - frame_service.py (frame capture, port 5002)
# - satellite_service.py (satellite tracking, port 5003)

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

# Restart service (preferred method)
sudo systemctl restart ufo-tracker

# Check service status
sudo systemctl status ufo-tracker

# View logs
sudo journalctl -u ufo-tracker -f
```

### Important: Service Management Rules
- **ALWAYS use systemctl commands** instead of pkill
- **NEVER run the app directly** - it should run as a service
- Use `sudo systemctl restart ufo-tracker` to restart after changes

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

## Service Architecture

The system now uses a microservice architecture with separate services:

- `api_service.py`: Main API service (port 5000) - includes new pan-tilt endpoints
- `camera_service.py`: Camera streaming service (port 5001)
- `frame_service.py`: Frame capture service (port 5002)  
- `satellite_service.py`: Satellite tracking service (port 5003)
- `timelapse_service.py`: Timelapse functionality service

### New Pan-Tilt API Endpoints

**WASD Control Endpoints** (api_service.py, port 5000):
- `GET /api/pantilt/status` - Get pan-tilt status and position
- `POST /api/pantilt/move_relative` - Move relative to current position (for WASD control)
  - Parameters: `pan_steps`, `tilt_steps`, `fine_step` (boolean)
  - `fine_step: true` reduces movement to 10% for precise control
- `POST /api/pantilt/enable_motors` - Enable stepper motors (auto-called when WASD starts)
- `POST /api/pantilt/disable_motors` - Disable stepper motors  
- `POST /api/pantilt/start_keepalive` - Keep motors powered during long exposures
- `POST /api/pantilt/stop_keepalive` - Stop keepalive pulses
- `POST /api/pantilt/home` - Home mechanism to center position

**WASD Integration**:
- JavaScript in `static/js/pantilt-controls.js` handles WASD key binding
- W/A/S/D keys control tilt up/pan left/tilt down/pan right
- Shift+WASD enables fine movement (10% of normal step size)
- Available in Live Cameras and Auto Tracking dashboard modes
- Toggle button: "⌨️ WASD: OFF" becomes "⌨️ WASD: ON" when active

## File Structure Notes

- `api_service.py`: Main API service with pan-tilt endpoints
- `app.py`: Legacy main Flask application (still used for some routes)
- `camera/`: Camera abstraction layer with streaming support
- `detection/`: Motion detection and object tracking algorithms
- `hardware/`: Hardware interface code (complete pan-tilt implementation)
- `services/`: Service layer code (ADSB, compass, sensors)
- `templates/`: HTML templates including unified dashboard
- `static/js/pantilt-controls.js`: WASD keyboard control implementation
- `static/`: CSS and JavaScript for web interface
- `config/`: Configuration files (copy example to create config.py)
- `detections/`: Directory for saved detection images
- `logs/`: Application logs directory