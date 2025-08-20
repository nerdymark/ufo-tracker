import math
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class TrajectoryProjector:
    def __init__(self, fov_horizontal: float = 35.0, fov_vertical: float = 26.0, mpu9250_sensor=None, camera_type: str = 'ir'):
        # Set realistic FOV values based on camera type
        if camera_type == 'hq':
            self.fov_horizontal = 45.0  # HQ camera with zoom lens
            self.fov_vertical = 34.0   # 4:3 aspect ratio
        else:
            self.fov_horizontal = 35.0  # IR camera wider FOV
            self.fov_vertical = 26.0   # 4:3 aspect ratio
            
        self.camera_type = camera_type
        self.camera_heading = 0.0
        self.camera_tilt_x = 0.0
        self.camera_tilt_y = 0.0
        self.mpu9250_sensor = mpu9250_sensor
        self.use_sensor_data = True
        
    def set_camera_orientation(self, heading: float, tilt_x: float = 0.0, tilt_y: float = 0.0):
        self.camera_heading = heading
        self.camera_tilt_x = tilt_x
        self.camera_tilt_y = tilt_y
    
    def get_current_orientation(self) -> Tuple[float, float, float]:
        """Get current camera orientation from MPU9250 sensor or manual settings"""
        if self.use_sensor_data and self.mpu9250_sensor and self.mpu9250_sensor.is_running():
            try:
                sensor_data = self.mpu9250_sensor.get_current_data()
                compass_data = sensor_data.get('compass', {})
                orientation = sensor_data.get('orientation', {})
                
                # Use true heading for accurate projection
                heading = compass_data.get('true_heading', self.camera_heading)
                tilt_x = orientation.get('roll', self.camera_tilt_x)
                tilt_y = orientation.get('pitch', self.camera_tilt_y)
                
                return heading, tilt_x, tilt_y
            except Exception as e:
                logger.warning(f"Error reading MPU9250 orientation: {e}")
        
        # Fallback to manual settings
        return self.camera_heading, self.camera_tilt_x, self.camera_tilt_y
    
    def enable_sensor_data(self, enabled: bool = True):
        """Enable or disable automatic orientation from MPU9250 sensor"""
        self.use_sensor_data = enabled
        logger.info(f"MPU9250 sensor data {'enabled' if enabled else 'disabled'} for trajectory projection")
    
    def set_fov(self, horizontal: float, vertical: float):
        self.fov_horizontal = horizontal
        self.fov_vertical = vertical
    
    def is_in_view(self, azimuth: float, elevation: float) -> bool:
        # Get current orientation from sensor or manual settings
        heading, tilt_x, tilt_y = self.get_current_orientation()
        
        # Calculate relative azimuth considering compass heading
        relative_azimuth = self.normalize_angle(azimuth - heading)
        
        if abs(relative_azimuth) > self.fov_horizontal / 2:
            return False
        
        # Apply pitch compensation for camera tilt
        # Positive pitch = camera tilted up, so objects appear higher
        # Negative pitch = camera tilted down, so objects appear lower
        adjusted_elevation = elevation + tilt_y
        
        if abs(adjusted_elevation) > self.fov_vertical / 2:
            return False
        
        return True
    
    def project_to_screen(self, azimuth: float, elevation: float, 
                         screen_width: int = 1920, screen_height: int = 1080) -> Optional[Tuple[float, float]]:
        if not self.is_in_view(azimuth, elevation):
            return None
        
        # Get current orientation from sensor or manual settings
        heading, tilt_x, tilt_y = self.get_current_orientation()
        
        # Calculate relative azimuth considering compass heading
        relative_azimuth = self.normalize_angle(azimuth - heading)
        
        # Apply pitch compensation for camera tilt
        adjusted_elevation = elevation + tilt_y
        
        # Project to screen coordinates with camera-specific FOV scaling
        x = (relative_azimuth / (self.fov_horizontal / 2) + 1) * screen_width / 2
        y = screen_height / 2 - (adjusted_elevation / (self.fov_vertical / 2)) * screen_height / 2
        
        # Clamp to screen bounds
        x = max(0, min(screen_width, x))
        y = max(0, min(screen_height, y))
        
        return (x, y)
    
    def project_trajectory(self, positions: List[Dict], 
                          screen_width: int = 1920, 
                          screen_height: int = 1080) -> List[Dict]:
        projected = []
        
        for pos in positions:
            screen_pos = self.project_to_screen(
                pos['azimuth'], 
                pos['elevation'],
                screen_width,
                screen_height
            )
            
            if screen_pos:
                projected.append({
                    'x': screen_pos[0],
                    'y': screen_pos[1],
                    'time': pos.get('time'),
                    'name': pos.get('name'),
                    'type': pos.get('type', 'satellite'),
                    'metadata': pos.get('metadata', {})
                })
        
        return projected
    
    def calculate_satellite_trajectory(self, satellite_data: Dict, 
                                     duration_minutes: int = 10,
                                     step_seconds: int = 30) -> List[Dict]:
        trajectory = []
        current_time = datetime.utcnow()
        
        for i in range(0, duration_minutes * 60, step_seconds):
            future_time = current_time + timedelta(seconds=i)
            
            predicted_az = satellite_data['azimuth']
            predicted_el = satellite_data['elevation']
            
            if 'velocity' in satellite_data:
                velocity_deg_per_sec = satellite_data['velocity'] / 111000
                predicted_az += velocity_deg_per_sec * i
                predicted_az = self.normalize_angle(predicted_az)
            
            trajectory.append({
                'azimuth': predicted_az,
                'elevation': predicted_el,
                'time': future_time.isoformat(),
                'name': satellite_data.get('name'),
                'type': 'satellite',
                'metadata': {
                    'norad_id': satellite_data.get('norad_id'),
                    'distance': satellite_data.get('distance')
                }
            })
        
        return trajectory
    
    def calculate_aircraft_trajectory(self, aircraft_data: Dict,
                                    duration_minutes: int = 5,
                                    step_seconds: int = 10) -> List[Dict]:
        trajectory = []
        current_time = datetime.utcnow()
        
        heading = aircraft_data.get('heading', 0)
        speed_knots = aircraft_data.get('speed', 0)
        altitude_ft = aircraft_data.get('altitude', 0)
        lat = aircraft_data.get('latitude', 0)
        lon = aircraft_data.get('longitude', 0)
        
        speed_mps = speed_knots * 0.514444
        
        for i in range(0, duration_minutes * 60, step_seconds):
            future_time = current_time + timedelta(seconds=i)
            
            distance_m = speed_mps * i
            distance_deg = distance_m / 111000
            
            future_lat = lat + distance_deg * math.cos(math.radians(heading))
            future_lon = lon + distance_deg * math.sin(math.radians(heading))
            
            azimuth, elevation = self.calculate_azimuth_elevation(
                future_lat, future_lon, altitude_ft * 0.3048
            )
            
            trajectory.append({
                'azimuth': azimuth,
                'elevation': elevation,
                'time': future_time.isoformat(),
                'name': aircraft_data.get('callsign', 'Unknown'),
                'type': 'aircraft',
                'metadata': {
                    'icao': aircraft_data.get('icao'),
                    'altitude': altitude_ft,
                    'speed': speed_knots
                }
            })
        
        return trajectory
    
    def calculate_azimuth_elevation(self, target_lat: float, target_lon: float, 
                                   target_alt_m: float,
                                   observer_lat: float = 0.0,
                                   observer_lon: float = 0.0,
                                   observer_alt_m: float = 0.0) -> Tuple[float, float]:
        lat1 = math.radians(observer_lat)
        lat2 = math.radians(target_lat)
        lon1 = math.radians(observer_lon)
        lon2 = math.radians(target_lon)
        
        dlon = lon2 - lon1
        
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        azimuth = math.degrees(math.atan2(y, x))
        azimuth = (azimuth + 360) % 360
        
        R = 6371000
        a = (math.sin((lat2 - lat1) / 2) ** 2 + 
             math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c
        
        height_diff = target_alt_m - observer_alt_m
        elevation = math.degrees(math.atan2(height_diff, distance))
        
        return azimuth, elevation
    
    @staticmethod
    def normalize_angle(angle: float) -> float:
        while angle > 180:
            angle -= 360
        while angle < -180:
            angle += 360
        return angle

# Create default instances for each camera type
trajectory_projector_ir = TrajectoryProjector(camera_type='ir')
trajectory_projector_hq = TrajectoryProjector(camera_type='hq')

# Default to IR camera for backward compatibility
trajectory_projector = trajectory_projector_ir