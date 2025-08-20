"""
MPU-6050 Motion Sensor Service
Tracks accelerometer, gyroscope, and compass data for UFO tracking system

WIRING INSTRUCTIONS for MPU-6050 (GY-521 module):
=====================================================

The MPU-6050 uses I2C communication (NOT SPI as mentioned). Here's the wiring:

Raspberry Pi GPIO -> MPU-6050 Module:
- 3.3V (Pin 1)   -> VCC
- GND (Pin 6)     -> GND  
- GPIO 2 (Pin 3)  -> SDA (I2C Data)
- GPIO 3 (Pin 5)  -> SCL (I2C Clock)

Optional connections:
- GPIO 4 (Pin 7)  -> INT (Interrupt pin, optional)
- 3.3V           -> XDA (if using external magnetometer)
- 3.3V           -> XCL (if using external magnetometer)

ENABLING I2C:
============
1. Enable I2C interface:
   sudo raspi-config
   -> Interface Options -> I2C -> Enable

2. Verify I2C is working:
   sudo i2cdetect -y 1
   (Should show device at address 0x68)

3. Install required Python packages:
   pip install adafruit-circuitpython-mpu6050 adafruit-blinka

PHYSICAL SETUP:
==============
- Mount MPU-6050 securely to UFO tracker base/camera mount
- Ensure X-axis points in camera direction for proper orientation
- Y-axis should point to the right when looking through camera
- Z-axis points up (perpendicular to ground)
- Keep away from motors and magnetic interference

GPIO Pin Reference (Raspberry Pi 4):
===================================
Pin 1:  3.3V     Pin 2:  5V
Pin 3:  GPIO 2   Pin 4:  5V
Pin 5:  GPIO 3   Pin 6:  GND
Pin 7:  GPIO 4   Pin 8:  GPIO 14
Pin 9:  GND      Pin 10: GPIO 15
...etc

The MPU-6050 operates at 3.3V, so use Pin 1 (3.3V) not Pin 2 (5V).
"""

import logging
import time
import math
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import json

try:
    # Try Adafruit CircuitPython library first
    import board
    import adafruit_mpu6050
    I2C_AVAILABLE = True
    I2C_LIBRARY = 'adafruit'
except ImportError:
    try:
        # Fallback to alternative MPU-6050 library
        import smbus2
        I2C_AVAILABLE = True
        I2C_LIBRARY = 'smbus2'
    except ImportError:
        try:
            # Fallback to basic smbus
            import smbus
            I2C_AVAILABLE = True
            I2C_LIBRARY = 'smbus'
        except ImportError:
            I2C_AVAILABLE = False
            I2C_LIBRARY = None
            logging.warning("No I2C libraries available. Install with: pip install adafruit-circuitpython-mpu6050 adafruit-blinka OR pip install mpu6050-raspberrypi smbus2")

from config.config import Config

logger = logging.getLogger(__name__)


class MotionSensor:
    """MPU-6050 motion sensor tracker for UFO detection system"""
    
    def __init__(self):
        """Initialize motion sensor"""
        self.config = Config.MOTION_SENSOR
        self.enabled = self.config['enabled'] and I2C_AVAILABLE
        
        # Sensor hardware
        self.mpu = None
        self.i2c = None
        
        # Orientation transformation matrix for software rotation
        # This rotates the sensor axes so X points down when mounted normally
        # Original: X=forward, Y=right, Z=up
        # Target: X=down, Y=right, Z=forward
        self.rotation_matrix = {
            'accel': {
                'x': {'from': 'z', 'sign': -1},  # New X (down) = -Old Z
                'y': {'from': 'y', 'sign': 1},   # New Y (right) = Old Y
                'z': {'from': 'x', 'sign': 1}    # New Z (forward) = Old X
            },
            'gyro': {
                'x': {'from': 'z', 'sign': -1},  # New X rotation = -Old Z rotation
                'y': {'from': 'y', 'sign': 1},   # New Y rotation = Old Y rotation
                'z': {'from': 'x', 'sign': 1}    # New Z rotation = Old X rotation
            }
        }
        
        # Current readings
        self.current_data = {
            'acceleration': {'x': 0.0, 'y': 0.0, 'z': 0.0},
            'gyroscope': {'x': 0.0, 'y': 0.0, 'z': 0.0},
            'temperature': 0.0,
            'orientation': {'pitch': 0.0, 'roll': 0.0, 'yaw': 0.0},
            'motion_detected': False,
            'vibration_level': 0.0,
            'tilt_angle': 0.0,
            'compass_heading': 0.0,
            'timestamp': None,
            'calibrated': False
        }
        
        # Calibration data (in raw sensor coordinates, before rotation)
        self.calibration = {
            'accel_offset': {'x': 0.0, 'y': 0.0, 'z': 0.0},
            'gyro_offset': {'x': 0.0, 'y': 0.0, 'z': 0.0},
            'mag_offset': {'x': 0.0, 'y': 0.0, 'z': 0.0},
            'mag_scale': {'x': 1.0, 'y': 1.0, 'z': 1.0}
        }
        
        # Motion detection (after rotation, X points down)
        self.baseline_accel = {'x': -9.81, 'y': 0.0, 'z': 0.0}  # Expected gravity on X axis
        self.motion_threshold = self.config['motion_threshold']
        self.vibration_threshold = self.config['vibration_threshold']
        
        # Threading
        self._running = False
        self._update_thread = None
        self._lock = threading.Lock()
        self.last_update = None
        
        # History for motion detection
        self.accel_history = []
        self.gyro_history = []
        self.max_history = 50  # Keep last 50 readings
        
        logger.info("Motion Sensor initialized")
    
    def initialize_hardware(self) -> bool:
        """Initialize MPU-6050 hardware"""
        if not self.enabled:
            logger.info("Motion sensor disabled in configuration")
            return False
            
        if not I2C_AVAILABLE:
            logger.error("I2C libraries not available for MPU-6050")
            return False
        
        try:
            if I2C_LIBRARY == 'adafruit':
                # Initialize I2C bus using Adafruit library
                self.i2c = board.I2C()
                
                # Initialize MPU-6050
                self.mpu = adafruit_mpu6050.MPU6050(self.i2c)
                
                # Configure sensor settings
                self.mpu.accelerometer_range = adafruit_mpu6050.Range.RANGE_4_G
                self.mpu.gyro_range = adafruit_mpu6050.GyroRange.RANGE_500_DPS
                self.mpu.filter_bandwidth = adafruit_mpu6050.Bandwidth.BAND_21_HZ
                
                logger.info("MPU-6050 hardware initialized successfully using Adafruit library")
                
            elif I2C_LIBRARY in ['smbus2', 'smbus']:
                # Initialize using smbus library with manual register access
                if I2C_LIBRARY == 'smbus2':
                    import smbus2 as smbus_lib
                else:
                    import smbus as smbus_lib
                
                self.i2c = smbus_lib.SMBus(1)  # I2C bus 1 on Raspberry Pi
                self.mpu = None  # We'll access registers directly
                
                # Wake up the MPU-6050 (it starts in sleep mode)
                self.i2c.write_byte_data(0x68, 0x6B, 0)
                
                logger.info(f"MPU-6050 hardware initialized successfully using {I2C_LIBRARY} library")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize MPU-6050: {e}")
            logger.error("Check wiring and I2C configuration")
            return False
    
    def calibrate_sensor(self, samples: int = 100) -> bool:
        """Calibrate sensor by taking baseline readings
        Note: Calibration is done in raw sensor coordinates before rotation
        """
        if not self.mpu and I2C_LIBRARY == 'adafruit':
            return False
        
        logger.info(f"Calibrating MPU-6050 with {samples} samples...")
        logger.info("Keep sensor stationary and level during calibration")
        
        try:
            accel_sum = {'x': 0.0, 'y': 0.0, 'z': 0.0}
            gyro_sum = {'x': 0.0, 'y': 0.0, 'z': 0.0}
            
            for i in range(samples):
                # Read raw sensor data
                if I2C_LIBRARY == 'adafruit' and self.mpu:
                    accel_x, accel_y, accel_z = self.mpu.acceleration
                    gyro_x, gyro_y, gyro_z = self.mpu.gyro
                elif I2C_LIBRARY in ['smbus2', 'smbus']:
                    accel_x, accel_y, accel_z = self._read_accel_data()
                    gyro_x, gyro_y, gyro_z = self._read_gyro_data()
                else:
                    return False
                
                accel_sum['x'] += accel_x
                accel_sum['y'] += accel_y
                accel_sum['z'] += accel_z
                
                gyro_sum['x'] += gyro_x
                gyro_sum['y'] += gyro_y
                gyro_sum['z'] += gyro_z
                
                time.sleep(0.01)  # 10ms between readings
            
            # Calculate offsets in raw sensor coordinates
            # When level, raw sensor should read: X=0, Y=0, Z=9.81 (gravity up)
            self.calibration['accel_offset']['x'] = accel_sum['x'] / samples
            self.calibration['accel_offset']['y'] = accel_sum['y'] / samples
            self.calibration['accel_offset']['z'] = (accel_sum['z'] / samples) - 9.81  # Remove gravity
            
            self.calibration['gyro_offset']['x'] = gyro_sum['x'] / samples
            self.calibration['gyro_offset']['y'] = gyro_sum['y'] / samples
            self.calibration['gyro_offset']['z'] = gyro_sum['z'] / samples
            
            self.current_data['calibrated'] = True
            logger.info("MPU-6050 calibration complete")
            return True
            
        except Exception as e:
            logger.error(f"Calibration failed: {e}")
            return False
    
    def _apply_rotation(self, raw_data: Dict, data_type: str) -> Dict:
        """Apply rotation transformation to sensor data"""
        rotated = {}
        for new_axis, transform in self.rotation_matrix[data_type].items():
            from_axis = transform['from']
            sign = transform['sign']
            rotated[new_axis] = raw_data[from_axis] * sign
        return rotated
    
    def read_sensor_data(self) -> Dict:
        """Read current sensor data"""
        if not I2C_AVAILABLE:
            return self.current_data
        
        try:
            if I2C_LIBRARY == 'adafruit' and self.mpu:
                # Read raw data using Adafruit library
                accel_x, accel_y, accel_z = self.mpu.acceleration
                gyro_x, gyro_y, gyro_z = self.mpu.gyro
                temperature = self.mpu.temperature
                
            elif I2C_LIBRARY in ['smbus2', 'smbus']:
                # Read raw data using direct register access
                accel_x, accel_y, accel_z = self._read_accel_data()
                gyro_x, gyro_y, gyro_z = self._read_gyro_data()
                temperature = self._read_temperature()
                
            else:
                return self.current_data
            
            # Store raw values before calibration
            raw_accel = {'x': accel_x, 'y': accel_y, 'z': accel_z}
            raw_gyro = {'x': gyro_x, 'y': gyro_y, 'z': gyro_z}
            
            # Apply calibration offsets to raw data
            raw_accel['x'] -= self.calibration['accel_offset']['x']
            raw_accel['y'] -= self.calibration['accel_offset']['y']
            raw_accel['z'] -= self.calibration['accel_offset']['z']
            
            raw_gyro['x'] -= self.calibration['gyro_offset']['x']
            raw_gyro['y'] -= self.calibration['gyro_offset']['y']
            raw_gyro['z'] -= self.calibration['gyro_offset']['z']
            
            # Apply rotation transformation
            rotated_accel = self._apply_rotation(raw_accel, 'accel')
            rotated_gyro = self._apply_rotation(raw_gyro, 'gyro')
            
            # Extract transformed values
            accel_x = rotated_accel['x']
            accel_y = rotated_accel['y']
            accel_z = rotated_accel['z']
            
            gyro_x = rotated_gyro['x']
            gyro_y = rotated_gyro['y']
            gyro_z = rotated_gyro['z']
            
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
                
                self.current_data['temperature'] = round(temperature, 1)
                self.current_data['timestamp'] = datetime.now().isoformat()
                
                # Calculate derived values
                self._calculate_orientation()
                self._detect_motion()
                self._calculate_vibration()
                self._calculate_tilt()
                
                # Update history
                self._update_history()
            
            return self.current_data.copy()
            
        except Exception as e:
            logger.error(f"Error reading sensor data: {e}")
            return self.current_data
    
    def _calculate_orientation(self):
        """Calculate pitch, roll, and yaw from accelerometer and gyroscope
        Note: With rotated axes (X=down, Y=right, Z=forward):
        - Pitch: rotation around Y axis (nose up/down)
        - Roll: rotation around Z axis (tilt left/right)
        - Yaw: rotation around X axis (turn left/right)
        """
        accel = self.current_data['acceleration']
        
        # With X pointing down (gravity direction when level):
        # Pitch is the angle from horizontal in the forward/back direction
        pitch = math.degrees(math.atan2(accel['z'], 
                                       math.sqrt(accel['x']**2 + accel['y']**2)))
        
        # Roll is the angle from vertical in the left/right direction  
        roll = math.degrees(math.atan2(accel['y'], -accel['x']))
        
        # Yaw requires magnetometer or integration - placeholder for now
        yaw = 0.0  # Would need magnetometer for true heading
        
        self.current_data['orientation'] = {
            'pitch': round(pitch, 1),
            'roll': round(roll, 1),
            'yaw': round(yaw, 1)
        }
    
    def _detect_motion(self):
        """Detect motion based on acceleration changes
        With rotated axes, gravity is on negative X axis when stationary
        """
        accel = self.current_data['acceleration']
        
        # Calculate total acceleration magnitude
        total_accel = math.sqrt(accel['x']**2 + accel['y']**2 + accel['z']**2)
        
        # Compare to baseline (gravity ~9.81 m/s²)
        accel_deviation = abs(total_accel - 9.81)
        
        # Also check deviation from expected gravity vector
        x_deviation = abs(accel['x'] - self.baseline_accel['x'])
        y_deviation = abs(accel['y'] - self.baseline_accel['y'])
        z_deviation = abs(accel['z'] - self.baseline_accel['z'])
        vector_deviation = math.sqrt(x_deviation**2 + y_deviation**2 + z_deviation**2)
        
        # Motion detected if either deviation exceeds threshold
        self.current_data['motion_detected'] = (accel_deviation > self.motion_threshold or 
                                               vector_deviation > self.motion_threshold)
    
    def _calculate_vibration(self):
        """Calculate vibration level from gyroscope data"""
        gyro = self.current_data['gyroscope']
        
        # Calculate total angular velocity
        total_gyro = math.sqrt(gyro['x']**2 + gyro['y']**2 + gyro['z']**2)
        
        self.current_data['vibration_level'] = round(total_gyro, 2)
    
    def _calculate_tilt(self):
        """Calculate tilt angle from vertical
        With rotated axes, X points down, so we check deviation from X-axis
        """
        accel = self.current_data['acceleration']
        
        # Calculate angle from vertical (X-axis now points down)
        # When level, X should read ~-9.81 m/s² (gravity)
        total_accel = math.sqrt(accel['x']**2 + accel['y']**2 + accel['z']**2)
        if total_accel > 0:
            # Angle from downward direction (X-axis)
            tilt = math.degrees(math.acos(abs(accel['x']) / total_accel))
        else:
            tilt = 0.0
        
        self.current_data['tilt_angle'] = round(tilt, 1)
    
    def _update_history(self):
        """Update motion history for trend analysis"""
        current_time = time.time()
        accel = self.current_data['acceleration']
        gyro = self.current_data['gyroscope']
        
        # Add current readings to history
        self.accel_history.append({
            'timestamp': current_time,
            'x': accel['x'],
            'y': accel['y'],
            'z': accel['z']
        })
        
        self.gyro_history.append({
            'timestamp': current_time,
            'x': gyro['x'],
            'y': gyro['y'],
            'z': gyro['z']
        })
        
        # Trim history to max size
        if len(self.accel_history) > self.max_history:
            self.accel_history.pop(0)
        if len(self.gyro_history) > self.max_history:
            self.gyro_history.pop(0)
    
    def get_motion_summary(self) -> Dict:
        """Get summary of recent motion activity"""
        if not self.accel_history:
            return {
                'avg_acceleration': 0.0,
                'max_acceleration': 0.0,
                'avg_vibration': 0.0,
                'max_vibration': 0.0,
                'motion_events': 0,
                'stability_score': 100.0
            }
        
        # Calculate averages and maximums
        recent_accels = [math.sqrt(h['x']**2 + h['y']**2 + h['z']**2) for h in self.accel_history[-10:]]
        recent_gyros = [math.sqrt(h['x']**2 + h['y']**2 + h['z']**2) for h in self.gyro_history[-10:]]
        
        avg_accel = sum(recent_accels) / len(recent_accels)
        max_accel = max(recent_accels)
        avg_gyro = sum(recent_gyros) / len(recent_gyros)
        max_gyro = max(recent_gyros)
        
        # Count motion events (acceleration spikes)
        motion_events = sum(1 for a in recent_accels if abs(a - 9.81) > self.motion_threshold)
        
        # Calculate stability score (100 = perfectly stable)
        accel_variance = sum((a - avg_accel)**2 for a in recent_accels) / len(recent_accels)
        stability_score = max(0, 100 - (accel_variance * 10))
        
        return {
            'avg_acceleration': round(avg_accel, 2),
            'max_acceleration': round(max_accel, 2),
            'avg_vibration': round(avg_gyro, 2),
            'max_vibration': round(max_gyro, 2),
            'motion_events': motion_events,
            'stability_score': round(stability_score, 1)
        }
    
    def start(self) -> bool:
        """Start motion sensor monitoring"""
        if not self.enabled:
            logger.info("Motion sensor disabled in configuration")
            return False
        
        with self._lock:
            if self._running:
                logger.info("Motion sensor already running")
                return True
            
            # Initialize hardware
            if not self.initialize_hardware():
                return False
            
            # Calibrate sensor
            if not self.calibrate_sensor():
                logger.warning("Sensor calibration failed, continuing with default calibration")
            
            try:
                self._running = True
                self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
                self._update_thread.start()
                
                logger.info("Motion sensor started")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start motion sensor: {e}")
                self._running = False
                return False
    
    def stop(self):
        """Stop motion sensor monitoring"""
        with self._lock:
            if not self._running:
                return
            
            self._running = False
            
            if self._update_thread and self._update_thread.is_alive():
                self._update_thread.join(timeout=2.0)
            
            logger.info("Motion sensor stopped")
    
    def _update_loop(self):
        """Main update loop for sensor readings"""
        logger.info("Motion sensor update loop started")
        
        while self._running:
            try:
                # Read sensor data
                self.read_sensor_data()
                self.last_update = datetime.now()
                
                # Wait for next update
                time.sleep(1.0 / self.config['sample_rate'])
                
            except Exception as e:
                logger.error(f"Error in motion sensor update loop: {e}")
                time.sleep(1.0)  # Wait longer on errors
        
        logger.info("Motion sensor update loop ended")
    
    def get_current_data(self) -> Dict:
        """Get current sensor data"""
        with self._lock:
            return self.current_data.copy()
    
    def get_status(self) -> Dict:
        """Get motion sensor status"""
        with self._lock:
            return {
                'running': self._running,
                'enabled': self.enabled,
                'hardware_available': I2C_AVAILABLE,
                'last_update': self.last_update.isoformat() if self.last_update else None,
                'calibrated': self.current_data['calibrated'],
                'sample_rate': self.config['sample_rate'],
                'motion_threshold': self.motion_threshold,
                'vibration_threshold': self.vibration_threshold,
                'current_temperature': self.current_data['temperature'],
                'i2c_address': '0x68'
            }
    
    def is_running(self) -> bool:
        """Check if motion sensor is running"""
        return self._running
    
    def recalibrate(self) -> bool:
        """Recalibrate sensor"""
        if I2C_AVAILABLE:
            return self.calibrate_sensor()
        return False
    
    def _read_raw_data(self, addr: int) -> int:
        """Read raw 16-bit data from MPU-6050 register"""
        if not self.i2c:
            return 0
        
        # Read high and low bytes
        high = self.i2c.read_byte_data(0x68, addr)
        low = self.i2c.read_byte_data(0x68, addr + 1)
        
        # Combine bytes and convert to signed 16-bit
        value = (high << 8) | low
        if value >= 0x8000:
            value = -((65535 - value) + 1)
        
        return value
    
    def _read_accel_data(self) -> Tuple[float, float, float]:
        """Read accelerometer data using direct register access"""
        # Accelerometer registers (ACCEL_XOUT_H/L, ACCEL_YOUT_H/L, ACCEL_ZOUT_H/L)
        accel_x_raw = self._read_raw_data(0x3B)
        accel_y_raw = self._read_raw_data(0x3D)
        accel_z_raw = self._read_raw_data(0x3F)
        
        # Convert to m/s² (±4g range, 16-bit resolution)
        accel_scale = 4.0 * 9.81 / 32768.0  # ±4g in m/s²
        accel_x = accel_x_raw * accel_scale
        accel_y = accel_y_raw * accel_scale
        accel_z = accel_z_raw * accel_scale
        
        return accel_x, accel_y, accel_z
    
    def _read_gyro_data(self) -> Tuple[float, float, float]:
        """Read gyroscope data using direct register access"""
        # Gyroscope registers (GYRO_XOUT_H/L, GYRO_YOUT_H/L, GYRO_ZOUT_H/L)
        gyro_x_raw = self._read_raw_data(0x43)
        gyro_y_raw = self._read_raw_data(0x45)
        gyro_z_raw = self._read_raw_data(0x47)
        
        # Convert to degrees/second (±500°/s range, 16-bit resolution)
        gyro_scale = 500.0 / 32768.0  # ±500°/s
        gyro_x = gyro_x_raw * gyro_scale
        gyro_y = gyro_y_raw * gyro_scale
        gyro_z = gyro_z_raw * gyro_scale
        
        return gyro_x, gyro_y, gyro_z
    
    def _read_temperature(self) -> float:
        """Read temperature data using direct register access"""
        # Temperature registers (TEMP_OUT_H/L)
        temp_raw = self._read_raw_data(0x41)
        
        # Convert to Celsius
        temperature = (temp_raw / 340.0) + 36.53
        
        return temperature