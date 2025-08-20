# Camera Flip and MPU9250 Orientation Changes

This document summarizes the changes made to accommodate the upside-down camera mounting and correct MPU9250 orientation for the UFO Tracker system.

**Recent Updates**: Added complete pan-tilt control with WASD keyboard integration. Removed orphaned test templates for cleaner codebase.

## Camera Changes

### Physical Mounting
- Cameras are now mounted **upside down** in the printed case
- Applied **180-degree rotation** using Picamera2's native transform

### Modified Files
1. **`camera/ir_camera.py`**
   - Added `transform=Transform(hflip=1, vflip=1)` to video configuration
   - Added transform to still capture configuration
   - Fixed import to include `from libcamera import Transform`
   
2. **`camera/hq_camera.py`**
   - Added `transform=Transform(hflip=1, vflip=1)` to video configuration  
   - Added transform to still capture configuration
   - Fixed import to include `from libcamera import Transform`

### Benefits
- Native hardware rotation (no CPU overhead)
- Applied at driver level for both streaming and still capture
- Consistent orientation across all camera operations

## MPU9250 Orientation Changes

### Physical Setup
- **Cameras point UPWARD** to the sky (not horizontal)
- **MPU9250 mounted flat** with the camera sensors
- **X-axis**: Camera "Up" direction (forward/back tilt)
- **Y-axis**: Camera "Right" direction (left/right tilt)  
- **Z-axis**: Sky direction (same as cameras)

### Modified Calculations in `services/mpu9250_sensor.py`

#### 1. Baseline Acceleration
```python
# OLD: Expected horizontal mounting
self.baseline_accel = {'x': -9.81, 'y': 0.0, 'z': 0.0}

# NEW: Expected upward-pointing mounting  
self.baseline_accel = {'x': 0.0, 'y': 0.0, 'z': -9.81}
```

#### 2. Orientation Calculations
- **Pitch**: Rotation around Y-axis (forward/back tilt from vertical)
- **Roll**: Rotation around X-axis (left/right tilt from vertical)
- **Yaw**: Rotation around Z-axis (compass heading)

Updated formulas for upward-pointing orientation:
```python
# Pitch: forward/back tilt from vertical
pitch = math.degrees(math.atan2(accel['x'], 
                               math.sqrt(accel['y']**2 + accel['z']**2)))

# Roll: left/right tilt from vertical  
roll = math.degrees(math.atan2(accel['y'], accel['z']))
```

#### 3. Tilt Calculation
- **Level position**: Cameras pointing straight up (Z≈-9.81, X≈0, Y≈0)
- **Tilt angle**: Deviation from pure Z-axis (sky direction)

#### 4. Compass Heading
- Updated tilt compensation for upward-pointing orientation
- Maintained true north calculation with magnetic declination

#### 5. Motion Detection
- Updated to detect deviations from upward-pointing baseline
- Checks both total acceleration and directional vector changes

#### 6. Calibration
- Modified accelerometer calibration for upward orientation
- Z-axis should read approximately -9.81 when level (pointing up)

## Configuration Changes

### Updated `config/config.py`
- Changed from MPU-6050 to MPU9250 settings
- Added compass-specific configurations
- Updated I2C addresses for both MPU9250 (0x68) and AK8963 magnetometer (0x0C)

### Updated `requirements.txt`
- Added `imusensor>=1.0.7` for MPU9250 support
- Maintained backward compatibility with existing I2C libraries

## Documentation Updates

### `MPU9250_SETUP.md`
- Added specific mounting instructions for UFO Tracker
- Explained the upward-pointing orientation
- Updated calibration procedures for new setup
- Added troubleshooting for orientation-specific issues

## Testing

All modified files pass syntax checking:
- ✅ `services/mpu9250_sensor.py` 
- ✅ `camera/ir_camera.py`
- ✅ `camera/hq_camera.py`

## Impact on Flight/Satellite Tracking

- **Improved accuracy** with real compass heading
- **Automatic orientation updates** from MPU9250
- **Tilt-compensated compass** for accurate projections
- **Enhanced trajectory overlays** with live sensor data

## What Users Need to Do

1. **Hardware**: Mount cameras upside down in case (already done)
2. **Hardware**: Install MPU9250 sensor flat with cameras  
3. **Software**: Update UFO Tracker code with these changes
4. **Calibration**: Perform accelerometer and magnetometer calibration
5. **Configuration**: Set magnetic declination for your location

The system now correctly handles the upside-down camera mounting and provides accurate compass heading for enhanced UFO tracking capabilities.