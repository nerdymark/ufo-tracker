"""
MPU9250 Motion and Compass Sensor Service
Tracks accelerometer, gyroscope, and magnetometer data for UFO tracking system

WIRING INSTRUCTIONS for MPU9250 (GY-9250 module):
=====================================================

The MPU9250 uses I2C communication. Here's the wiring:

Raspberry Pi GPIO -> MPU9250 Module:
- 3.3V (Pin 1)   -> VCC
- GND (Pin 6)     -> GND  
- GPIO 2 (Pin 3)  -> SDA (I2C Data)
- GPIO 3 (Pin 5)  -> SCL (I2C Clock)

Optional connections:
- GPIO 4 (Pin 7)  -> INT (Interrupt pin, optional)
- GPIO 24 (Pin 18) -> FSYNC (Frame sync, optional)

ENABLING I2C:
============
1. Enable I2C interface:
   sudo raspi-config
   -> Interface Options -> I2C -> Enable

2. Verify I2C is working:
   sudo i2cdetect -y 1
   (Should show devices at address 0x68 for MPU9250 and 0x0C for AK8963 magnetometer)

3. Install required Python packages:
   pip install imusensor adafruit-circuitpython-mpu6050 adafruit-blinka

PHYSICAL SETUP:
==============
- Mount MPU9250 securely to UFO tracker base/camera mount
- Ensure X-axis points in camera direction for proper orientation
- Y-axis should point to the right when looking through camera
- Z-axis points up (perpendicular to ground)
- Keep away from motors and magnetic interference sources
- For compass accuracy, perform 3D figure-8 calibration away from metal objects

The MPU9250 operates at 3.3V, so use Pin 1 (3.3V) not Pin 2 (5V).
"""

import logging
import time
import math
import threading
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
import numpy as np

try:
    # Try imusensor library first (best for MPU9250)
    from imusensor.MPU9250 import MPU9250
    from imusensor.filters import kalman
    IMU_LIBRARY = 'imusensor'
    IMU_AVAILABLE = True
except ImportError:
    try:
        # Fallback to direct I2C access
        import smbus2
        IMU_LIBRARY = 'smbus2'
        IMU_AVAILABLE = True
    except ImportError:
        try:
            import smbus
            IMU_LIBRARY = 'smbus'
            IMU_AVAILABLE = True
        except ImportError:
            IMU_AVAILABLE = False
            IMU_LIBRARY = None
            logging.warning("No IMU libraries available. Install with: pip install imusensor")

from config.config import Config

logger = logging.getLogger(__name__)


class MPU9250Sensor:
    """MPU9250 motion and compass sensor for UFO detection system"""
    
    def __init__(self):
        """Initialize MPU9250 sensor"""
        self.config = Config.MOTION_SENSOR
        self.enabled = self.config['enabled'] and IMU_AVAILABLE
        
        # Sensor hardware
        self.mpu = None
        self.kalman_filter = None
        
        # Current readings
        self.current_data = {
            'acceleration': {'x': 0.0, 'y': 0.0, 'z': 0.0},
            'gyroscope': {'x': 0.0, 'y': 0.0, 'z': 0.0},
            'magnetometer': {'x': 0.0, 'y': 0.0, 'z': 0.0},
            'temperature': 0.0,
            'orientation': {'pitch': 0.0, 'roll': 0.0, 'yaw': 0.0},
            'compass': {
                'heading': 0.0,
                'true_heading': 0.0,
                'magnetic_declination': 0.0,
                'calibrated': False
            },
            'motion_detected': False,
            'vibration_level': 0.0,
            'tilt_angle': 0.0,
            'timestamp': None,
            'calibrated': False
        }
        
        # Calibration data
        self.calibration = {
            'accel_offset': {'x': 0.0, 'y': 0.0, 'z': 0.0},
            'gyro_offset': {'x': 0.0, 'y': 0.0, 'z': 0.0},
            'mag_offset': {'x': 0.0, 'y': 0.0, 'z': 0.0},
            'mag_scale': {'x': 1.0, 'y': 1.0, 'z': 1.0},
            'mag_soft_iron': np.eye(3),  # 3x3 identity matrix for soft iron correction
            'compass_declination': 0.0,  # Magnetic declination for true north
            'compass_offset': 0.0        # Manual compass calibration offset
        }
        
        # Motion detection
        # IMPORTANT: Cameras point upward, so sensor is vertical with Z pointing to sky
        # In this orientation, gravity should be primarily on Z-axis (downward, so negative Z)
        self.baseline_accel = {'x': 0.0, 'y': 0.0, 'z': -9.81}  # Expected gravity on Z-axis when pointing up
        self.motion_threshold = self.config['motion_threshold']
        self.vibration_threshold = self.config['vibration_threshold']
        
        # Threading
        self._running = False
        self._update_thread = None
        self._lock = threading.Lock()
        self.last_update = None
        
        # History for motion detection and filtering
        self.sensor_history = []
        self.max_history = 50
        
        # Calibration file path
        self.calibration_file = 'config/mpu9250_calibration.json'
        
        logger.info("MPU9250 Sensor initialized")
    
    def load_calibration(self) -> bool:
        """Load calibration data from file"""
        try:
            if os.path.exists(self.calibration_file):
                with open(self.calibration_file, 'r') as f:
                    cal_data = json.load(f)
                    
                    # Load offsets
                    if 'accel_offset' in cal_data:
                        self.calibration['accel_offset'] = cal_data['accel_offset']
                    if 'gyro_offset' in cal_data:
                        self.calibration['gyro_offset'] = cal_data['gyro_offset']
                    if 'mag_offset' in cal_data:
                        self.calibration['mag_offset'] = cal_data['mag_offset']
                    if 'mag_scale' in cal_data:
                        self.calibration['mag_scale'] = cal_data['mag_scale']
                    if 'compass_declination' in cal_data:
                        self.calibration['compass_declination'] = cal_data['compass_declination']
                    if 'compass_offset' in cal_data:
                        self.calibration['compass_offset'] = cal_data['compass_offset']
                    
                    # Load soft iron correction matrix
                    if 'mag_soft_iron' in cal_data:
                        self.calibration['mag_soft_iron'] = np.array(cal_data['mag_soft_iron'])
                    
                    self.current_data['calibrated'] = True
                    self.current_data['compass']['calibrated'] = True
                    logger.info("Loaded MPU9250 calibration data")
                    return True
        except Exception as e:
            logger.error(f"Error loading calibration: {e}")
        
        return False
    
    def save_calibration(self) -> bool:
        """Save calibration data to file"""
        try:
            os.makedirs(os.path.dirname(self.calibration_file), exist_ok=True)
            
            cal_data = {
                'accel_offset': self.calibration['accel_offset'],
                'gyro_offset': self.calibration['gyro_offset'],
                'mag_offset': self.calibration['mag_offset'],
                'mag_scale': self.calibration['mag_scale'],
                'mag_soft_iron': self.calibration['mag_soft_iron'].tolist(),
                'compass_declination': self.calibration['compass_declination'],
                'compass_offset': self.calibration['compass_offset'],
                'timestamp': datetime.now().isoformat()
            }
            
            with open(self.calibration_file, 'w') as f:
                json.dump(cal_data, f, indent=2)
            
            logger.info("Saved MPU9250 calibration data")
            return True
            
        except Exception as e:
            logger.error(f"Error saving calibration: {e}")
            return False
    
    def initialize_hardware(self) -> bool:
        """Initialize MPU9250 hardware"""
        if not self.enabled:
            logger.info("MPU9250 sensor disabled in configuration")
            return False
            
        if not IMU_AVAILABLE:
            logger.error("IMU libraries not available for MPU9250")
            return False
        
        try:
            if IMU_LIBRARY == 'imusensor':
                # Initialize using imusensor library
                self.mpu = MPU9250.MPU9250(0x68, 1)  # I2C address 0x68, bus 1
                self.mpu.begin()
                
                # Configure sensor ranges
                self.mpu.configureGyroFSR(500)      # ±500 degrees/sec
                self.mpu.configureAccelFSR(4)       # ±4g
                self.mpu.configureMagFSR("16b")     # 16-bit magnetometer
                
                # Initialize Kalman filter for sensor fusion
                self.kalman_filter = kalman.Kalman()
                
                logger.info("MPU9250 hardware initialized successfully using imusensor library")
                
            elif IMU_LIBRARY in ['smbus2', 'smbus']:
                # Initialize using direct I2C access
                if IMU_LIBRARY == 'smbus2':
                    import smbus2 as smbus_lib
                else:
                    import smbus as smbus_lib
                
                self.mpu = smbus_lib.SMBus(1)  # I2C bus 1
                
                # Wake up MPU9250
                self.mpu.write_byte_data(0x68, 0x6B, 0x00)
                time.sleep(0.1)
                
                # Configure accelerometer (±4g)
                self.mpu.write_byte_data(0x68, 0x1C, 0x08)
                
                # Configure gyroscope (±500°/s)
                self.mpu.write_byte_data(0x68, 0x1B, 0x08)
                
                # Enable magnetometer access
                self.mpu.write_byte_data(0x68, 0x37, 0x02)
                
                logger.info(f"MPU9250 hardware initialized successfully using {IMU_LIBRARY} library")
            
            # Load existing calibration
            self.load_calibration()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize MPU9250: {e}")
            logger.error("Check wiring and I2C configuration")
            return False
    
    def calibrate_accelerometer_gyroscope(self, samples: int = 1000) -> bool:
        """Calibrate accelerometer and gyroscope"""
        if not self.mpu:
            return False
        
        logger.info(f"Calibrating accelerometer and gyroscope with {samples} samples...")
        logger.info("Keep sensor stationary and level during calibration")
        
        try:
            if IMU_LIBRARY == 'imusensor':
                # Use built-in calibration
                self.mpu.calibrateAccelGyroFast()
                logger.info("Accelerometer and gyroscope calibration complete")
                return True
                
            else:
                # Manual calibration for direct I2C access
                accel_sum = {'x': 0.0, 'y': 0.0, 'z': 0.0}
                gyro_sum = {'x': 0.0, 'y': 0.0, 'z': 0.0}
                
                for i in range(samples):
                    accel_x, accel_y, accel_z = self._read_accel_raw()
                    gyro_x, gyro_y, gyro_z = self._read_gyro_raw()
                    
                    accel_sum['x'] += accel_x
                    accel_sum['y'] += accel_y
                    accel_sum['z'] += accel_z
                    
                    gyro_sum['x'] += gyro_x
                    gyro_sum['y'] += gyro_y
                    gyro_sum['z'] += gyro_z
                    
                    time.sleep(0.01)
                
                # Calculate offsets
                # IMPORTANT: For upward-pointing cameras, when level (pointing to sky):
                # X=0, Y=0, Z=-9.81 (gravity points down, opposite to sky direction)
                self.calibration['accel_offset']['x'] = accel_sum['x'] / samples
                self.calibration['accel_offset']['y'] = accel_sum['y'] / samples
                self.calibration['accel_offset']['z'] = (accel_sum['z'] / samples) + 9.81  # Remove gravity (add because Z should read -9.81)
                
                self.calibration['gyro_offset']['x'] = gyro_sum['x'] / samples
                self.calibration['gyro_offset']['y'] = gyro_sum['y'] / samples
                self.calibration['gyro_offset']['z'] = gyro_sum['z'] / samples
                
                logger.info("Manual accelerometer and gyroscope calibration complete")
                return True
            
        except Exception as e:
            logger.error(f"Accelerometer/gyroscope calibration failed: {e}")
            return False
    
    def calibrate_magnetometer(self, duration: int = 60) -> bool:
        """Calibrate magnetometer with 3D figure-8 motion"""
        if not self.mpu:
            return False
        
        logger.info(f"Starting magnetometer calibration for {duration} seconds...")
        logger.info("Rotate sensor in 3D figure-8 patterns to capture all orientations")
        
        mag_readings = []
        start_time = time.time()
        
        try:
            while time.time() - start_time < duration:
                if IMU_LIBRARY == 'imusensor':
                    self.mpu.readSensor()
                    mag_x = self.mpu.MagX
                    mag_y = self.mpu.MagY
                    mag_z = self.mpu.MagZ
                else:
                    mag_x, mag_y, mag_z = self._read_mag_raw()
                
                mag_readings.append([mag_x, mag_y, mag_z])
                time.sleep(0.1)  # 10Hz sampling
            
            if len(mag_readings) < 100:
                logger.error("Insufficient magnetometer readings for calibration")
                return False
            
            # Calculate hard iron offsets (center of ellipsoid)
            mag_array = np.array(mag_readings)
            mag_min = np.min(mag_array, axis=0)
            mag_max = np.max(mag_array, axis=0)
            
            # Hard iron correction (offset)
            self.calibration['mag_offset']['x'] = (mag_max[0] + mag_min[0]) / 2
            self.calibration['mag_offset']['y'] = (mag_max[1] + mag_min[1]) / 2
            self.calibration['mag_offset']['z'] = (mag_max[2] + mag_min[2]) / 2
            
            # Soft iron correction (scaling)
            mag_range = mag_max - mag_min
            avg_range = np.mean(mag_range)
            
            self.calibration['mag_scale']['x'] = avg_range / mag_range[0]
            self.calibration['mag_scale']['y'] = avg_range / mag_range[1]
            self.calibration['mag_scale']['z'] = avg_range / mag_range[2]
            
            # Simple soft iron matrix (for more advanced calibration, use ellipsoid fitting)
            self.calibration['mag_soft_iron'] = np.diag([
                self.calibration['mag_scale']['x'],
                self.calibration['mag_scale']['y'],
                self.calibration['mag_scale']['z']
            ])
            
            self.current_data['compass']['calibrated'] = True
            logger.info("Magnetometer calibration complete")
            self.save_calibration()
            return True
            
        except Exception as e:
            logger.error(f"Magnetometer calibration failed: {e}")
            return False
    
    def set_magnetic_declination(self, declination: float):
        """Set magnetic declination for true north calculation"""
        self.calibration['compass_declination'] = declination
        self.current_data['compass']['magnetic_declination'] = declination
        self.save_calibration()
        logger.info(f"Magnetic declination set to {declination}°")
    
    def set_compass_north_reference(self, current_heading: float = None):
        """Set current heading as north reference (manual compass calibration)

        Args:
            current_heading: If None, uses current sensor reading
        """
        if current_heading is None:
            # Use current compass heading
            current_heading = self.current_data['compass']['heading']

        self.calibration['compass_offset'] = -current_heading
        self.save_calibration()
        logger.info(f"Compass north reference set: current={current_heading}°, offset={self.calibration['compass_offset']}°")

    def is_level(self, tolerance_degrees: float = 5.0) -> Tuple[bool, float]:
        """Check if the device is level (pointing upward within tolerance)

        Args:
            tolerance_degrees: Maximum allowed tilt from vertical (degrees)

        Returns:
            Tuple of (is_level: bool, tilt_angle: float)
        """
        accel = self.current_data['acceleration']

        # Calculate total acceleration magnitude
        total_accel = math.sqrt(accel['x']**2 + accel['y']**2 + accel['z']**2)

        if total_accel < 0.1:  # Avoid division by zero
            return False, 0.0

        # For upward-pointing setup, when level (pointing to sky):
        # X≈0, Y≈0, Z≈-9.81 (gravity points down, opposite to sky direction)
        # Tilt angle is the angle between current orientation and pure Z-axis
        z_component = abs(accel['z'])
        tilt_angle = math.degrees(math.acos(min(1.0, z_component / total_accel)))

        is_level = tilt_angle <= tolerance_degrees

        return is_level, tilt_angle

    def calibrate_level_and_north(self, samples: int = 100, tolerance_degrees: float = 5.0) -> Dict:
        """Quick calibration: Level the device pointing north, then calibrate

        This is the simplified auto-calibration method:
        1. Check if device is level (upward-pointing within tolerance)
        2. Take multiple magnetometer readings
        3. Set the average as north reference (0°)
        4. Apply hard iron correction if needed

        Args:
            samples: Number of magnetometer samples to average
            tolerance_degrees: Maximum allowed tilt from vertical

        Returns:
            Dict with calibration results
        """
        if not self.mpu:
            return {
                'success': False,
                'error': 'Sensor not initialized'
            }

        logger.info("Starting level-and-north calibration...")

        try:
            # Step 1: Check if device is level
            is_level, tilt_angle = self.is_level(tolerance_degrees)

            if not is_level:
                return {
                    'success': False,
                    'error': f'Device not level (tilt={tilt_angle:.1f}°, max={tolerance_degrees}°). Please level the device pointing upward.',
                    'tilt_angle': tilt_angle,
                    'tolerance': tolerance_degrees
                }

            logger.info(f"Device is level (tilt={tilt_angle:.1f}°)")

            # Step 2: Collect magnetometer readings
            mag_readings = []
            heading_readings = []

            for i in range(samples):
                # Read current sensor data
                self.read_sensor_data()

                # Get raw magnetometer data
                mag = self.current_data['magnetometer'].copy()
                heading = self.current_data['compass']['heading']

                mag_readings.append([mag['x'], mag['y'], mag['z']])
                heading_readings.append(heading)

                time.sleep(0.05)  # 20Hz sampling for calibration

            if len(mag_readings) < 10:
                return {
                    'success': False,
                    'error': 'Insufficient magnetometer readings'
                }

            # Step 3: Calculate average heading
            # Handle wraparound at 0/360 degrees
            avg_heading = self._circular_mean(heading_readings)

            logger.info(f"Average heading from {samples} samples: {avg_heading:.1f}°")

            # Step 4: Set this as north reference (0°)
            self.set_compass_north_reference(avg_heading)

            # Step 5: Update calibration status
            self.current_data['compass']['calibrated'] = True
            self.save_calibration()

            logger.info("Level-and-north calibration complete!")

            return {
                'success': True,
                'tilt_angle': tilt_angle,
                'original_heading': avg_heading,
                'compass_offset': self.calibration['compass_offset'],
                'samples': samples,
                'message': f'Calibration complete! Device was level ({tilt_angle:.1f}° tilt). North set to {avg_heading:.1f}°'
            }

        except Exception as e:
            logger.error(f"Level-and-north calibration failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _circular_mean(self, angles: List[float]) -> float:
        """Calculate mean of circular data (angles in degrees)

        Handles wraparound at 0/360 degrees correctly
        """
        if not angles:
            return 0.0

        # Convert to radians and calculate mean of sin and cos components
        angles_rad = [math.radians(a) for a in angles]
        sin_sum = sum(math.sin(a) for a in angles_rad)
        cos_sum = sum(math.cos(a) for a in angles_rad)

        # Calculate mean angle
        mean_rad = math.atan2(sin_sum / len(angles), cos_sum / len(angles))
        mean_deg = math.degrees(mean_rad)

        # Normalize to 0-360
        if mean_deg < 0:
            mean_deg += 360

        return mean_deg
    
    def read_sensor_data(self) -> Dict:
        """Read current sensor data from MPU9250"""
        if not IMU_AVAILABLE or not self.mpu:
            return self.current_data
        
        try:
            if IMU_LIBRARY == 'imusensor':
                # Read using imusensor library
                self.mpu.readSensor()
                
                # Get accelerometer data (m/s²)
                accel_x = self.mpu.AccelX
                accel_y = self.mpu.AccelY
                accel_z = self.mpu.AccelZ
                
                # Get gyroscope data (rad/s -> deg/s)
                gyro_x = math.degrees(self.mpu.GyroX)
                gyro_y = math.degrees(self.mpu.GyroY)
                gyro_z = math.degrees(self.mpu.GyroZ)
                
                # Get magnetometer data (µT)
                mag_x = self.mpu.MagX
                mag_y = self.mpu.MagY
                mag_z = self.mpu.MagZ
                
                # Temperature (°C)
                temperature = self.mpu.Temperature
                
            else:
                # Read using direct I2C access
                accel_x, accel_y, accel_z = self._read_accel_raw()
                gyro_x, gyro_y, gyro_z = self._read_gyro_raw()
                mag_x, mag_y, mag_z = self._read_mag_raw()
                temperature = self._read_temperature_raw()
            
            # Apply calibration to magnetometer
            mag_x_cal = (mag_x - self.calibration['mag_offset']['x']) * self.calibration['mag_scale']['x']
            mag_y_cal = (mag_y - self.calibration['mag_offset']['y']) * self.calibration['mag_scale']['y']
            mag_z_cal = (mag_z - self.calibration['mag_offset']['z']) * self.calibration['mag_scale']['z']
            
            # Update current data
            with self._lock:
                self.current_data['acceleration'] = {
                    'x': round(accel_x, 3),
                    'y': round(accel_y, 3),
                    'z': round(accel_z, 3)
                }
                
                self.current_data['gyroscope'] = {
                    'x': round(gyro_x, 3),
                    'y': round(gyro_y, 3),
                    'z': round(gyro_z, 3)
                }
                
                self.current_data['magnetometer'] = {
                    'x': round(mag_x_cal, 3),
                    'y': round(mag_y_cal, 3),
                    'z': round(mag_z_cal, 3)
                }
                
                self.current_data['temperature'] = round(temperature, 1)
                self.current_data['timestamp'] = datetime.now().isoformat()
                
                # Calculate derived values
                self._calculate_orientation()
                self._calculate_compass_heading()
                self._detect_motion()
                self._calculate_vibration()
                self._calculate_tilt()
                
                # Update history
                self._update_history()
            
            return self.current_data.copy()
            
        except Exception as e:
            logger.error(f"Error reading MPU9250 sensor data: {e}")
            return self.current_data
    
    def _calculate_orientation(self):
        """Calculate pitch, roll, and yaw from accelerometer, gyroscope, and magnetometer
        
        For upward-pointing camera setup:
        - X axis: Camera "Up" direction (forward/back tilt affects this)
        - Y axis: Camera "Right" direction (left/right tilt affects this)  
        - Z axis: Sky direction (rotation around this axis is yaw/heading)
        - Normal position: Cameras pointing straight up (Z=+sky, minimal X,Y acceleration)
        """
        accel = self.current_data['acceleration']
        gyro = self.current_data['gyroscope']
        mag = self.current_data['magnetometer']
        
        # For upward-pointing orientation:
        # - Pitch: rotation around Y-axis (camera tilting forward/back) 
        # - Roll: rotation around X-axis (camera tilting left/right)
        # - Yaw: rotation around Z-axis (camera rotating clockwise/counterclockwise)
        
        # Calculate pitch (forward/back tilt from vertical)
        # When pointing straight up: X≈0, Y≈0, Z≈-9.81 (gravity pulls down)
        pitch = math.degrees(math.atan2(accel['x'], 
                                       math.sqrt(accel['y']**2 + accel['z']**2)))
        
        # Calculate roll (left/right tilt from vertical)
        roll = math.degrees(math.atan2(accel['y'], accel['z']))
        
        # Calculate yaw from magnetometer (with tilt compensation)
        # Compensate magnetometer readings for the current tilt
        pitch_rad = math.radians(pitch)
        roll_rad = math.radians(roll)
        
        # Tilt-compensated magnetometer values
        mag_x_comp = mag['x'] * math.cos(pitch_rad) + \
                     mag['z'] * math.sin(pitch_rad)
        mag_y_comp = mag['x'] * math.sin(roll_rad) * math.sin(pitch_rad) + \
                     mag['y'] * math.cos(roll_rad) - \
                     mag['z'] * math.sin(roll_rad) * math.cos(pitch_rad)
        
        # Calculate yaw (heading) - rotation around Z axis
        yaw = math.degrees(math.atan2(-mag_y_comp, mag_x_comp))
        if yaw < 0:
            yaw += 360
        
        self.current_data['orientation'] = {
            'pitch': round(pitch, 1),
            'roll': round(roll, 1),
            'yaw': round(yaw, 1)
        }
    
    def _calculate_compass_heading(self):
        """Calculate compass heading from magnetometer with tilt compensation
        
        For upward-pointing camera setup where Z points to sky.
        """
        mag = self.current_data['magnetometer']
        accel = self.current_data['acceleration']
        
        # Tilt-compensated compass calculation for upward-pointing orientation
        # Calculate current tilt angles
        pitch = math.atan2(accel['x'], math.sqrt(accel['y']**2 + accel['z']**2))
        roll = math.atan2(accel['y'], accel['z'])
        
        # Apply tilt compensation to magnetometer readings
        mag_x_comp = mag['x'] * math.cos(pitch) + mag['z'] * math.sin(pitch)
        mag_y_comp = mag['x'] * math.sin(roll) * math.sin(pitch) + \
                     mag['y'] * math.cos(roll) - \
                     mag['z'] * math.sin(roll) * math.cos(pitch)
        
        # Calculate heading (0-360°) - rotation around Z axis (sky direction)
        heading = math.degrees(math.atan2(-mag_y_comp, mag_x_comp))
        if heading < 0:
            heading += 360
        
        # Apply compass offset (manual calibration)
        heading = (heading + self.calibration['compass_offset']) % 360
        
        # Calculate true heading (add magnetic declination)
        true_heading = (heading + self.calibration['compass_declination']) % 360
        
        self.current_data['compass'] = {
            'heading': round(heading, 1),
            'true_heading': round(true_heading, 1),
            'magnetic_declination': self.calibration['compass_declination'],
            'calibrated': self.current_data['compass']['calibrated']
        }
    
    def _detect_motion(self):
        """Detect motion based on acceleration changes
        
        For upward-pointing orientation, motion is detected by deviation from 
        the baseline where Z≈-9.81 (gravity down) and X,Y≈0.
        """
        accel = self.current_data['acceleration']
        
        # Calculate total acceleration magnitude
        total_accel = math.sqrt(accel['x']**2 + accel['y']**2 + accel['z']**2)
        
        # Compare to baseline (gravity ~9.81 m/s²)
        accel_deviation = abs(total_accel - 9.81)
        
        # Also check deviation from expected baseline orientation (upward-pointing)
        x_deviation = abs(accel['x'] - self.baseline_accel['x'])  # Should be ~0
        y_deviation = abs(accel['y'] - self.baseline_accel['y'])  # Should be ~0  
        z_deviation = abs(accel['z'] - self.baseline_accel['z'])  # Should be ~-9.81
        vector_deviation = math.sqrt(x_deviation**2 + y_deviation**2 + z_deviation**2)
        
        # Motion detected if either total acceleration or directional deviation exceeds threshold
        self.current_data['motion_detected'] = (accel_deviation > self.motion_threshold or 
                                               vector_deviation > self.motion_threshold)
    
    def _calculate_vibration(self):
        """Calculate vibration level from gyroscope data"""
        gyro = self.current_data['gyroscope']
        
        # Calculate total angular velocity
        total_gyro = math.sqrt(gyro['x']**2 + gyro['y']**2 + gyro['z']**2)
        
        self.current_data['vibration_level'] = round(total_gyro, 2)
    
    def _calculate_tilt(self):
        """Calculate tilt angle from vertical (upward-pointing position)
        
        For upward-pointing cameras, the "level" position is when Z points to sky
        and X,Y are minimal. Tilt is how much the system deviates from pointing straight up.
        """
        accel = self.current_data['acceleration']
        
        # Calculate total acceleration magnitude
        total_accel = math.sqrt(accel['x']**2 + accel['y']**2 + accel['z']**2)
        
        if total_accel > 0:
            # For upward-pointing setup, calculate deviation from Z-axis (sky direction)
            # When pointing straight up: Z≈-9.81 (gravity down), X≈0, Y≈0
            # Tilt angle is the angle between current orientation and pure Z-axis
            z_component = abs(accel['z'])
            tilt = math.degrees(math.acos(min(1.0, z_component / total_accel)))
        else:
            tilt = 0.0
        
        self.current_data['tilt_angle'] = round(tilt, 1)
    
    def _update_history(self):
        """Update sensor history for trend analysis"""
        current_time = time.time()
        
        history_entry = {
            'timestamp': current_time,
            'acceleration': self.current_data['acceleration'].copy(),
            'gyroscope': self.current_data['gyroscope'].copy(),
            'magnetometer': self.current_data['magnetometer'].copy(),
            'compass_heading': self.current_data['compass']['heading']
        }
        
        self.sensor_history.append(history_entry)
        
        # Trim history to max size
        if len(self.sensor_history) > self.max_history:
            self.sensor_history.pop(0)
    
    def get_compass_data(self) -> Dict:
        """Get compass-specific data"""
        with self._lock:
            return {
                'heading': self.current_data['compass']['heading'],
                'true_heading': self.current_data['compass']['true_heading'],
                'magnetic_declination': self.current_data['compass']['magnetic_declination'],
                'calibrated': self.current_data['compass']['calibrated'],
                'timestamp': self.current_data['timestamp']
            }
    
    def start(self) -> bool:
        """Start MPU9250 sensor monitoring"""
        if not self.enabled:
            logger.info("MPU9250 sensor disabled in configuration")
            return False
        
        with self._lock:
            if self._running:
                logger.info("MPU9250 sensor already running")
                return True
            
            # Initialize hardware
            if not self.initialize_hardware():
                return False
            
            try:
                self._running = True
                self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
                self._update_thread.start()
                
                logger.info("MPU9250 sensor started")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start MPU9250 sensor: {e}")
                self._running = False
                return False
    
    def stop(self):
        """Stop MPU9250 sensor monitoring"""
        with self._lock:
            if not self._running:
                return
            
            self._running = False
            
            if self._update_thread and self._update_thread.is_alive():
                self._update_thread.join(timeout=2.0)
            
            logger.info("MPU9250 sensor stopped")
    
    def _update_loop(self):
        """Main update loop for sensor readings"""
        logger.info("MPU9250 sensor update loop started")
        
        while self._running:
            try:
                # Read sensor data
                self.read_sensor_data()
                self.last_update = datetime.now()
                
                # Wait for next update
                time.sleep(1.0 / self.config['sample_rate'])
                
            except Exception as e:
                logger.error(f"Error in MPU9250 sensor update loop: {e}")
                time.sleep(1.0)  # Wait longer on errors
        
        logger.info("MPU9250 sensor update loop ended")
    
    def get_current_data(self) -> Dict:
        """Get current sensor data"""
        with self._lock:
            return self.current_data.copy()
    
    def get_status(self) -> Dict:
        """Get MPU9250 sensor status"""
        with self._lock:
            return {
                'running': self._running,
                'enabled': self.enabled,
                'hardware_available': IMU_AVAILABLE,
                'library': IMU_LIBRARY,
                'last_update': self.last_update.isoformat() if self.last_update else None,
                'calibrated': self.current_data['calibrated'],
                'compass_calibrated': self.current_data['compass']['calibrated'],
                'sample_rate': self.config['sample_rate'],
                'motion_threshold': self.motion_threshold,
                'vibration_threshold': self.vibration_threshold,
                'current_temperature': self.current_data['temperature'],
                'i2c_addresses': ['0x68', '0x0C']  # MPU9250 and AK8963
            }
    
    def is_running(self) -> bool:
        """Check if MPU9250 sensor is running"""
        return self._running
    
    def get_motion_summary(self) -> Dict:
        """Get summary of recent motion activity"""
        if not self.sensor_history:
            return {
                'avg_acceleration': 0.0,
                'max_acceleration': 0.0,
                'avg_vibration': 0.0,
                'max_vibration': 0.0,
                'motion_events': 0,
                'stability_score': 100.0
            }
        
        # Calculate averages and maximums from recent readings
        recent_entries = self.sensor_history[-10:]  # Last 10 readings
        
        # Extract acceleration magnitudes
        recent_accels = []
        recent_gyros = []
        
        for entry in recent_entries:
            accel = entry['acceleration']
            gyro = entry['gyroscope']
            
            accel_mag = math.sqrt(accel['x']**2 + accel['y']**2 + accel['z']**2)
            gyro_mag = math.sqrt(gyro['x']**2 + gyro['y']**2 + gyro['z']**2)
            
            recent_accels.append(accel_mag)
            recent_gyros.append(gyro_mag)
        
        if not recent_accels:
            return {
                'avg_acceleration': 0.0,
                'max_acceleration': 0.0,
                'avg_vibration': 0.0,
                'max_vibration': 0.0,
                'motion_events': 0,
                'stability_score': 100.0
            }
        
        avg_accel = sum(recent_accels) / len(recent_accels)
        max_accel = max(recent_accels)
        avg_gyro = sum(recent_gyros) / len(recent_gyros)
        max_gyro = max(recent_gyros)
        
        # Count motion events (acceleration spikes)
        motion_events = sum(1 for a in recent_accels if abs(a - 9.81) > self.motion_threshold)
        
        # Calculate stability score (100 = perfectly stable)
        if len(recent_accels) > 1:
            accel_variance = sum((a - avg_accel)**2 for a in recent_accels) / len(recent_accels)
            stability_score = max(0, 100 - (accel_variance * 10))
        else:
            stability_score = 100.0
        
        return {
            'avg_acceleration': round(avg_accel, 2),
            'max_acceleration': round(max_accel, 2),
            'avg_vibration': round(avg_gyro, 2),
            'max_vibration': round(max_gyro, 2),
            'motion_events': motion_events,
            'stability_score': round(stability_score, 1)
        }
    
    # Raw data reading methods for direct I2C access
    def _read_raw_data(self, addr: int, register: int) -> int:
        """Read raw 16-bit data from register"""
        if not self.mpu:
            return 0
        
        # Read high and low bytes
        high = self.mpu.read_byte_data(addr, register)
        low = self.mpu.read_byte_data(addr, register + 1)
        
        # Combine bytes and convert to signed 16-bit
        value = (high << 8) | low
        if value >= 0x8000:
            value = -((65535 - value) + 1)
        
        return value
    
    def _read_accel_raw(self) -> Tuple[float, float, float]:
        """Read raw accelerometer data"""
        accel_x_raw = self._read_raw_data(0x68, 0x3B)
        accel_y_raw = self._read_raw_data(0x68, 0x3D)
        accel_z_raw = self._read_raw_data(0x68, 0x3F)
        
        # Convert to m/s² (±4g range)
        accel_scale = 4.0 * 9.81 / 32768.0
        return (accel_x_raw * accel_scale,
                accel_y_raw * accel_scale,
                accel_z_raw * accel_scale)
    
    def _read_gyro_raw(self) -> Tuple[float, float, float]:
        """Read raw gyroscope data"""
        gyro_x_raw = self._read_raw_data(0x68, 0x43)
        gyro_y_raw = self._read_raw_data(0x68, 0x45)
        gyro_z_raw = self._read_raw_data(0x68, 0x47)
        
        # Convert to degrees/second (±500°/s range)
        gyro_scale = 500.0 / 32768.0
        return (gyro_x_raw * gyro_scale,
                gyro_y_raw * gyro_scale,
                gyro_z_raw * gyro_scale)
    
    def _read_mag_raw(self) -> Tuple[float, float, float]:
        """Read raw magnetometer data"""
        # Enable single measurement mode for AK8963
        self.mpu.write_byte_data(0x0C, 0x0A, 0x01)
        time.sleep(0.01)
        
        # Read magnetometer data
        mag_x_raw = self._read_raw_data(0x0C, 0x03)
        mag_y_raw = self._read_raw_data(0x0C, 0x05)
        mag_z_raw = self._read_raw_data(0x0C, 0x07)
        
        # Convert to µT (16-bit mode)
        mag_scale = 4912.0 / 32760.0  # µT per LSB
        return (mag_x_raw * mag_scale,
                mag_y_raw * mag_scale,
                mag_z_raw * mag_scale)
    
    def _read_temperature_raw(self) -> float:
        """Read raw temperature data"""
        temp_raw = self._read_raw_data(0x68, 0x41)
        return (temp_raw / 333.87) + 21.0  # MPU9250 temperature formula