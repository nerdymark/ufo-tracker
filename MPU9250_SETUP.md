# MPU9250 Setup Guide for UFO Tracker

This guide explains how to set up and use the MPU9250 9-axis motion sensor with compass functionality in the UFO Tracker system.

**Note**: This system now includes complete pan-tilt control with WASD keyboard integration. The motion sensor works alongside the pan-tilt mechanism for enhanced tracking capabilities.

## Hardware Requirements

- MPU9250 sensor module (GY-9250 breakout board)
- Raspberry Pi with I2C enabled
- 4 jumper wires for connections

## Wiring Diagram

Connect the MPU9250 to your Raspberry Pi as follows:

```
MPU9250 Module    ->    Raspberry Pi GPIO
VCC               ->    3.3V (Pin 1)
GND               ->    GND (Pin 6)
SDA               ->    GPIO 2 (Pin 3)
SCL               ->    GPIO 3 (Pin 5)
```

**Important:** Use 3.3V, NOT 5V. The MPU9250 operates at 3.3V.

## Physical Mounting

**IMPORTANT: UFO Tracker Specific Orientation**
- Mount MPU9250 securely to UFO tracker base, **flat with the camera sensors**
- **Cameras point UPWARD to the sky** (mounted upside down in the case)
- **X-axis arrow points to camera "Up" direction** (toward the camera's top edge)
- **Y-axis arrow points to camera "Right" direction** (toward the camera's right edge)
- **Z-axis points to sky** (same direction as the cameras point)
- Keep away from motors and magnetic interference sources
- For compass accuracy, perform 3D figure-8 calibration away from metal objects

**Orientation Summary:**
- Normal operating position: Cameras pointing straight up to sky
- X,Y axes are in the world horizontal plane  
- Z-axis is vertical (sky direction)
- This is different from typical horizontal sensor mounting

## Software Setup

### 1. Enable I2C

```bash
sudo raspi-config
# Navigate to: Interface Options -> I2C -> Enable
sudo reboot
```

### 2. Verify I2C Detection

```bash
sudo i2cdetect -y 1
```

You should see devices at addresses:
- `0x68` - MPU9250 accelerometer/gyroscope
- `0x0C` - AK8963 magnetometer (compass)

### 3. Install Dependencies

```bash
# Navigate to UFO Tracker directory
cd /home/mark/ufo-tracker

# Install required Python packages
pip install imusensor numpy

# Or install all requirements
pip install -r requirements.txt
```

### 4. Update Configuration

Edit `config/config.py` to ensure MPU9250 is enabled:

```python
MOTION_SENSOR = {
    'enabled': True,  # Enable MPU9250 sensor
    # ... other settings
}
```

## Using the MPU9250 System

### Starting the Service

The MPU9250 sensor automatically starts when you run the UFO Tracker application:

```bash
# Start UFO Tracker
sudo systemctl start ufo-tracker

# Or run directly
python app.py
```

### Calibration

The system requires two types of calibration:

#### 1. Accelerometer/Gyroscope Calibration

- Place the device on a flat, stable surface
- Access the web interface
- Navigate to sensor controls
- Click "Calibrate Accelerometer"
- Keep device stationary during calibration

#### 2. Magnetometer (Compass) Calibration

- Access the web interface
- Navigate to compass controls
- Click "Calibrate Magnetometer"
- For 60 seconds, rotate the device in 3D figure-8 patterns
- Cover all orientations (pitch, roll, yaw)
- Stay away from metal objects and magnetic interference

### Setting Magnetic Declination

For accurate true north readings:

1. Find your magnetic declination at: https://www.magnetic-declination.com/
2. In the web interface, use "Set Magnetic Declination"
3. Enter your location's declination value

### API Endpoints

The system provides REST API endpoints:

- `GET /api/sensor/data` - Get all sensor readings
- `GET /api/sensor/compass` - Get compass-specific data
- `GET /api/sensor/status` - Get sensor status
- `POST /api/sensor/calibrate/accelerometer` - Calibrate accelerometer/gyroscope
- `POST /api/sensor/calibrate/magnetometer` - Calibrate magnetometer
- `POST /api/sensor/compass/set_declination` - Set magnetic declination
- `POST /api/sensor/compass/set_north` - Set current heading as north reference

### JavaScript Integration

The system includes JavaScript files for web interface integration:

- `mpu9250-sensor.js` - Sensor data display and controls
- `compass-trajectory.js` - Compass integration with flight/satellite tracking

## Features

### Real-time Data

- 3-axis accelerometer readings (m/s²)
- 3-axis gyroscope readings (°/s)
- 3-axis magnetometer readings (µT)
- Temperature readings (°C)
- Calculated orientation (pitch, roll, yaw)
- Tilt-compensated compass heading
- True heading with magnetic declination correction

### Motion Detection

- Motion detection based on acceleration changes
- Vibration level monitoring
- Tilt angle calculation
- Stability scoring

### Flight Tracking Integration

- Automatic compass heading for trajectory projection
- Real-time orientation updates for satellite tracking
- Tilt compensation for accurate projections

## Troubleshooting

### I2C Issues

```bash
# Check I2C is enabled
sudo raspi-config

# Check device detection
sudo i2cdetect -y 1

# Check I2C permissions
sudo usermod -a -G i2c $USER
# Logout and login again
```

### Sensor Not Detected

1. Check wiring connections
2. Verify power supply (3.3V, not 5V)
3. Test with different I2C address: `sudo i2cdetect -y 0`
4. Check for conflicts with other I2C devices

### Calibration Issues

1. **Magnetometer calibration fails:**
   - Move away from metal objects
   - Ensure full 3D rotation during calibration
   - Try longer calibration duration (90-120 seconds)

2. **Compass readings inaccurate:**
   - Recalibrate magnetometer
   - Set correct magnetic declination for your location
   - Check for magnetic interference

### JavaScript Errors

1. Check browser console for errors
2. Verify API endpoints are responding
3. Ensure sensor service is running

## Advanced Configuration

### Sensor Ranges

Configure in `config/config.py`:

```python
'range_settings': {
    'accelerometer': '±4g',     # ±2g, ±4g, ±8g, ±16g
    'gyroscope': '±500°/s',     # ±250°/s, ±500°/s, ±1000°/s, ±2000°/s
    'magnetometer': '±4800µT',  # Fixed range for AK8963
}
```

### Sample Rate

```python
'sample_rate': 50,  # Samples per second (Hz)
```

### Motion Detection Thresholds

```python
'motion_threshold': 2.0,      # Motion detection (m/s²)
'vibration_threshold': 10.0,  # Vibration alert (°/s)
```

## Benefits Over MPU-6050

- **Real compass functionality** with magnetometer
- **True heading calculation** with magnetic declination
- **Tilt-compensated compass** for accurate readings
- **9-axis motion tracking** (vs 6-axis)
- **Better trajectory projection** for flight/satellite tracking
- **Automatic orientation** for camera systems

## Usage in UFO Tracking

1. **Automatic Compass Heading:** Camera orientation updates automatically
2. **Flight Tracking:** Accurate projections based on real compass bearing
3. **Satellite Tracking:** True north reference for overhead passes
4. **Motion Detection:** Enhanced stability monitoring
5. **Trajectory Overlay:** Real-time compass updates for overlays

The MPU9250 system significantly improves the accuracy of the UFO Tracker's flight and satellite tracking capabilities by providing real compass heading and orientation data.