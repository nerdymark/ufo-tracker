# UFO Tracker - Raspberry Pi Project

A dual-camera system for detecting and tracking unidentified flying objects (UFOs) using Raspberry Pi, with infrared detection and high-quality camera capabilities.

## Features

- **Dual Camera System**: 
  - Infrared-sensitive camera for motion detection
  - High-quality camera for detailed captures
- **Web Interface**: Unified dashboard with multiple viewing modes
  - Live camera streams (MJPEG)
  - Image stacking for long exposure effects
  - Auto-tracking mode with client-side motion detection
  - Image gallery and browser
- **Camera Controls**: Manual camera settings adjustment (exposure, gain, brightness, contrast)
- **Pan-Tilt Mechanism**: Complete Waveshare HRB8825 stepper controller integration with WASD keyboard control
- **Multi-viewer Support**: Concurrent camera access without conflicts
- **System Monitoring**: Real-time status monitoring and system information

## Hardware Requirements

- **Raspberry Pi 5** (Required - this system is optimized for Pi 5 hardware)
- 2x Camera modules:
  - 1x Infrared-sensitive camera (e.g., Pi NoIR Camera)
  - 1x High-quality camera module
- Waveshare stepper motor controller (for pan-tilt mechanism)
- MicroSD card (32GB+ recommended)
- Power supplies:
  - 5V 5A for Raspberry Pi 5
  - **12V power supply for stepper motors** (separate from Pi power)

## Software Requirements

- Raspberry Pi OS (64-bit recommended for Pi 5)
- Python 3.9+ (comes with Pi OS on Pi 5)
- See `requirements.txt` for Python dependencies

## Installation

### Quick Setup (Recommended)

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd ufo-tracker
   ```

2. Run the automated setup script:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

   The setup script will:
   - Install system dependencies and OpenCV requirements
   - Create a Python virtual environment
   - Install Python packages from requirements.txt
   - Enable camera interface (on Raspberry Pi)
   - Set up camera permissions
   - Optionally create a systemd service

### Manual Installation

1. Install system dependencies:
   ```bash
   sudo apt update
   sudo apt install python3-pip python3-venv python3-dev build-essential
   sudo apt install python3-picamera2 libcamera-apps libcamera-dev  # Raspberry Pi only
   ```

2. Create virtual environment and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Enable camera interface (Raspberry Pi only):
   ```bash
   sudo raspi-config
   # Navigate to Interface Options > Camera > Enable
   ```

## Configuration

1. Copy the example configuration:
   ```bash
   cp config/config.example.py config/config.py
   ```

2. Edit `config/config.py` to match your camera setup and preferences.

## Usage

### Starting the Application

1. Activate the virtual environment:
   ```bash
   source venv/bin/activate
   ```

2. Start the UFO tracker application:
   ```bash
   ./run.sh
   ```
   Or manually:
   ```bash
   python app.py
   ```

3. Open a web browser and navigate to:
   ```
   http://your-raspberry-pi-ip:5000
   ```

### Using the Web Interface

The unified dashboard provides several viewing modes:

- **Live Cameras**: Real-time MJPEG streams from both cameras
- **Camera Controls**: Manual adjustment of camera settings (exposure, gain, brightness, contrast)  
- **Auto Tracking**: Client-side motion detection and tracking with integrated WASD pan/tilt control
- **Image Stacking**: Advanced image stacking with multiple blend modes for astrophotography and motion capture
- **Image Browser**: Browse captured images with filtering and management
- **Pan-Tilt Controls**: Live keyboard control using WASD keys with fine movement support
- **System Settings**: Configuration and system monitoring

#### Image Stacking Modes

The UFO Tracker includes sophisticated client-side image stacking capabilities with four distinct blending modes:

**🔢 Default (Average Stacking)**
- Blends all frames equally using weighted averaging
- Each frame contributes `1/N` opacity where N is the number of frames
- Best for: General noise reduction, creating stable composite images
- Result: Smooth, averaged image with reduced noise and background movement

**🌌 Long Exposure Mode**
- Uses "lighten" blend mode - keeps the brightest pixel from each frame
- Simulates traditional long-exposure photography techniques
- Best for: Capturing motion trails, star trails, light streaks
- Result: Preserves bright moving objects while maintaining dark background

**🔥 Juiced Exposure Mode**
- Uses "lighter" blend mode - adds brightness from each frame (30% per frame)
- Creates artistic light painting and accumulation effects
- **Recommended**: Use with fewer frames (3-5) to prevent overexposure
- Best for: Light painting effects, emphasizing bright moving objects
- Result: Bright, accumulated light effects with enhanced luminosity

**♾️ Infinite Exposure Mode**
- True infinite stacking - locks the frame counter and continuously accumulates frames
- Uses Long Exposure technique but never stops adding new frames
- **Automatic**: Disables other modes and locks the stack count slider when enabled
- Best for: Extended observation sessions, capturing rare events over time
- Result: Continuously building composite with unlimited frame accumulation

**Usage Tips:**
- Start with Default mode for general use
- Switch between modes in real-time to see different effects
- Long Exposure works well with 10-20 frames
- Juiced Exposure is most effective with 3-8 frames
- Infinite Exposure runs continuously until manually stopped
- All modes (except Infinite) support 2-100 frame stacking ranges

#### WASD Pan-Tilt Control

The UFO Tracker features intuitive keyboard control for the pan-tilt mechanism:

**🎮 WASD Controls**
- **W**: Tilt camera up
- **S**: Tilt camera down  
- **A**: Pan camera left
- **D**: Pan camera right

**🔧 Control Features**
- **Fine Movement**: Hold `Shift` while pressing WASD for precise control (10% of normal step size)
- **Auto Motor Enable**: Motors automatically enable when WASD control is activated
- **Multi-View Access**: WASD controls available in both Live Cameras and Auto Tracking modes
- **Visual Feedback**: Button shows ON/OFF status with color indication

**⚙️ Advanced Features**
- **Keepalive Mode**: Keep motors powered during long exposures to prevent position drift
- **Home Position**: Return to center position with one click
- **Step Size Control**: Adjustable step size for different movement ranges
- **Safety Limits**: Hardware-enforced movement limits prevent damage

**Usage:**
1. Navigate to Live Cameras or Auto Tracking view
2. Click "⌨️ WASD: OFF" button to enable keyboard control
3. Use W/A/S/D keys to move the camera
4. Hold Shift for fine adjustments
5. Click button again to disable WASD control

### Service Management

If you installed the systemd service:

```bash
# Start service
sudo systemctl start ufo-tracker

# Stop service  
sudo systemctl stop ufo-tracker

# Check status
sudo systemctl status ufo-tracker

# View logs
sudo journalctl -u ufo-tracker -f
```

## Project Structure

```
ufo-tracker/
├── app.py                    # Main Flask application
├── api_service.py            # API service with pan-tilt endpoints
├── camera_service.py         # Camera streaming service
├── frame_service.py          # Frame capture service
├── satellite_service.py     # Satellite tracking service
├── timelapse_service.py      # Timelapse functionality
├── setup.sh                  # Automated setup script
├── run.sh                    # Application startup script
├── restart-ufo-services.sh   # Service restart script
├── requirements.txt          # Python dependencies
├── README.md                 # This file
├── CLAUDE.md                 # Development guidance for Claude Code
├── MPU9250_SETUP.md         # Motion sensor setup guide
├── CAMERA_FLIP_CHANGES.md   # Camera orientation changes
├── config/
│   ├── __init__.py
│   ├── config.py             # Configuration settings (created from example)
│   ├── config.example.py     # Example configuration template
│   ├── compass_calibration.json # Compass calibration data
│   └── mpu9250_calibration.json # Motion sensor calibration
├── camera/
│   ├── __init__.py
│   ├── camera_manager.py     # Camera initialization and management
│   ├── ir_camera.py          # Infrared camera handler
│   ├── hq_camera.py          # High-quality camera handler
│   ├── streaming.py          # Video streaming objects for multi-viewer support
│   └── auto_tuner.py         # Auto-tuning for camera settings
├── detection/
│   ├── __init__.py
│   ├── motion_detector.py    # Motion detection algorithms
│   ├── object_tracker.py     # Object tracking logic  
│   ├── auto_tracker.py       # Auto-tracking functionality
│   └── image_processor.py    # Image processing and stacking
├── hardware/
│   ├── __init__.py
│   └── pan_tilt.py          # Complete pan-tilt mechanism implementation
├── services/
│   ├── __init__.py
│   ├── adsb_service.py       # ADSB flight tracking
│   ├── adsb_tracker.py       # ADSB data processing
│   ├── compass_service.py    # Compass functionality
│   ├── color_generator.py    # Color utilities
│   ├── mpu9250_sensor.py     # Motion sensor interface
│   └── trajectory_projector.py # Trajectory calculations
├── templates/
│   ├── unified_dashboard.html # Main web interface
│   ├── index.html            # Alternative interface
│   ├── viewer.html           # Camera viewer page
│   ├── frame_viewer.html     # Frame viewer
│   └── error.html            # Error page template
├── static/
│   ├── css/
│   │   └── style.css         # Web interface styling
│   └── js/                   # Modular JavaScript files
│       ├── core.js           # Core functionality
│       ├── navigation.js     # Navigation controls
│       ├── camera-feeds.js   # Camera feed handling
│       ├── camera-controls.js# Camera settings controls
│       ├── pantilt-controls.js# Pan-tilt WASD controls
│       ├── tracking.js       # Motion tracking
│       ├── feature-tracking.js# Feature-based tracking
│       ├── trajectory-overlay.js# Trajectory visualization
│       ├── compass-trajectory.js# Compass trajectory
│       ├── motion-detection.js# Motion detection
│       ├── gallery.js        # Image gallery
│       ├── stacking-optimized.js# Optimized image stacking
│       ├── stacking.js       # Image stacking
│       ├── unified-music-engine.js# Audio system
│       ├── mood-music.js     # Background music
│       ├── adsb-tracker.js   # ADSB flight tracking
│       ├── mpu9250-sensor.js # Motion sensor interface
│       ├── viewer.js         # Viewer functionality
│       └── utils.js          # Utility functions
├── cache/                    # Cache directory
├── detections/               # Detection images storage
└── logs/                     # Application logs
    └── .gitkeep              
```

## API Endpoints

### Web Interface
- `/` - Main unified dashboard
- `/viewer` - Camera viewer interface  
- `/ir_feed` - Infrared camera MJPEG stream
- `/hq_feed` - High-quality camera MJPEG stream
- `/ir_frame` - Single IR camera frame
- `/hq_frame` - Single HQ camera frame

### Camera Controls
- `/api/camera_settings/<camera_type>` - Get/set camera settings
- `/api/camera_auto_tune/<camera_type>` - Auto-tune camera settings
- `/api/capture/<camera_type>` - Capture single image

### Pan-Tilt Controls
- `/api/pantilt/status` - Get pan-tilt controller status and position
- `/api/pantilt/move_relative` - Move relative to current position (WASD control)
- `/api/pantilt/enable_motors` - Enable stepper motors (turn on holding torque)
- `/api/pantilt/disable_motors` - Disable stepper motors (save power)
- `/api/pantilt/start_keepalive` - Start keepalive pulses for long exposures
- `/api/pantilt/stop_keepalive` - Stop keepalive pulses
- `/api/pantilt/home` - Home mechanism to center position
- `/api/pan_tilt` - Legacy pan-tilt status and movement commands
- `/api/pan_tilt/motors` - Legacy motor enable/disable
- `/api/pan_tilt/keepalive` - Legacy keepalive enable/disable

### System Status
- `/api/system_status` - Overall system and component status
- `/api/test` - Simple API test endpoint

## Compatibility Note

⚠️ **This system is specifically designed for Raspberry Pi 5**

The UFO Tracker system requires:
- Raspberry Pi 5's improved CPU performance for real-time motion detection
- Enhanced camera interfaces available on Pi 5
- Optimized for Pi 5's memory and processing capabilities
- Separate 12V power supply for stepper motors (do not power motors from Pi)

While some components may work on Pi 4, full functionality and performance are only guaranteed on Raspberry Pi 5.

**Power Supply Warning**: Never connect the 12V stepper motor power directly to the Raspberry Pi. The stepper motors require their own 12V power supply connected to the motor controller board.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test on Raspberry Pi 5 hardware
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Troubleshooting

### Common Issues

**Camera Not Working**
- Ensure cameras are properly connected to CSI ports
- Enable camera interface: `sudo raspi-config` → Interface Options → Camera → Enable
- Check user is in video group: `groups $USER` (should include "video")
- Test camera access: `libcamera-hello` (if available)

**Application Won't Start**  
- Activate virtual environment: `source venv/bin/activate`
- Check Python version: `python3 --version` (requires 3.9+)
- Install missing dependencies: `pip install -r requirements.txt`
- Check logs in `logs/` directory

**Performance Issues**
- Reduce camera resolution in `config/config.py`
- Close browser tabs/viewers when not needed

**Stepper Motors Not Working**
- Verify 12V power supply is connected to motor controller (not Pi)
- Check motor controller is properly connected to Pi GPIO pins
- Ensure motors are enabled in the web interface
- Verify wiring connections between motors and controller
- Check 12V power supply is providing adequate current
- Monitor system resources: `htop` or `/api/system_status`
- Consider using the headless OpenCV version

**Network Access Issues** 
- Check firewall: `sudo ufw status`
- Verify Pi network connection: `hostname -I`
- Try accessing locally: `curl http://localhost:5000/api/test`

### Development

For development with Claude Code, see `CLAUDE.md` for detailed setup instructions and architectural notes.

## Recent Updates

### Pan-Tilt Control Implementation ✅
- Complete Waveshare HRB8825 stepper controller integration
- WASD keyboard control with fine movement support
- New API endpoints for comprehensive motor control
- Auto motor enable/disable and keepalive functionality
- Multi-view integration (Live Cameras and Auto Tracking modes)

### Template Cleanup ✅
- Removed orphaned test templates (stacked_test.html, test_stream.html)
- Streamlined template structure for better maintainability

## Current Limitations

- **Motion detection**: Currently disabled for performance (auto-tracking uses client-side detection)
- **Timelapse features**: Disabled for performance optimization
- **Image stacking**: Basic implementation - may need performance tuning for large images
