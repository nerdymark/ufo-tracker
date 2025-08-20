import json
import os
import threading
import time
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class CompassService:
    def __init__(self, mpu9250_sensor=None):
        self.heading = 0.0
        self.tilt_x = 0.0
        self.tilt_y = 0.0
        self.magnetic_declination = 0.0
        self.calibrated = False
        self.calibration_offset = 0.0
        self.lock = threading.Lock()
        self.config_file = 'config/compass_calibration.json'
        self.mpu9250_sensor = mpu9250_sensor
        self.load_calibration()
        
    def load_calibration(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.calibration_offset = data.get('offset', 0.0)
                    self.magnetic_declination = data.get('declination', 0.0)
                    self.calibrated = data.get('calibrated', False)
                    logger.info(f"Loaded compass calibration: offset={self.calibration_offset}, declination={self.magnetic_declination}")
        except Exception as e:
            logger.error(f"Error loading compass calibration: {e}")
    
    def save_calibration(self):
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump({
                    'offset': self.calibration_offset,
                    'declination': self.magnetic_declination,
                    'calibrated': self.calibrated,
                    'timestamp': time.time()
                }, f, indent=2)
            logger.info("Saved compass calibration")
        except Exception as e:
            logger.error(f"Error saving compass calibration: {e}")
    
    def set_north_reference(self, current_heading: float):
        with self.lock:
            self.calibration_offset = -current_heading
            self.calibrated = True
            self.save_calibration()
            logger.info(f"Set north reference: current_heading={current_heading}, offset={self.calibration_offset}")
    
    def update_heading(self, raw_heading: float, tilt_x: float = 0.0, tilt_y: float = 0.0):
        with self.lock:
            self.heading = (raw_heading + self.calibration_offset + self.magnetic_declination) % 360
            self.tilt_x = tilt_x
            self.tilt_y = tilt_y
    
    def get_true_heading(self) -> float:
        with self.lock:
            return self.heading
    
    def get_orientation_data(self) -> Dict[str, Any]:
        with self.lock:
            # If MPU9250 sensor is available, get real-time data
            if self.mpu9250_sensor and self.mpu9250_sensor.is_running():
                try:
                    sensor_data = self.mpu9250_sensor.get_current_data()
                    compass_data = sensor_data.get('compass', {})
                    orientation = sensor_data.get('orientation', {})
                    
                    return {
                        'heading': compass_data.get('heading', self.heading),
                        'true_heading': compass_data.get('true_heading', self.heading),
                        'tilt_x': orientation.get('roll', self.tilt_x),
                        'tilt_y': orientation.get('pitch', self.tilt_y),
                        'yaw': orientation.get('yaw', 0.0),
                        'calibrated': compass_data.get('calibrated', self.calibrated),
                        'magnetic_declination': compass_data.get('magnetic_declination', self.magnetic_declination),
                        'sensor_available': True
                    }
                except Exception as e:
                    logger.warning(f"Error reading MPU9250 data: {e}")
            
            # Fallback to stored values
            return {
                'heading': self.heading,
                'true_heading': self.heading + self.magnetic_declination,
                'tilt_x': self.tilt_x,
                'tilt_y': self.tilt_y,
                'yaw': 0.0,
                'calibrated': self.calibrated,
                'magnetic_declination': self.magnetic_declination,
                'sensor_available': False
            }
    
    def set_magnetic_declination(self, declination: float):
        with self.lock:
            self.magnetic_declination = declination
            self.save_calibration()

compass_service = CompassService()