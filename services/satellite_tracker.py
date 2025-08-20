"""
Satellite Overhead Tracker Service
Tracks satellites and space stations currently overhead using TLE data from CelesTrak
"""

import requests
import numpy as np
import time
import math
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Dict, Optional
import threading

from sgp4.api import Satrec
from sgp4.earth_gravity import wgs84
from math import degrees, radians, sin, cos, sqrt, atan2, asin

from config.config import Config

logger = logging.getLogger(__name__)


class SatelliteTracker:
    """Satellite tracker that fetches TLE data and tracks overhead satellites"""
    
    def __init__(self):
        """Initialize satellite tracker"""
        self.config = Config.SATELLITE
        self.observer_lat = self.config['observer_location']['latitude']
        self.observer_lon = self.config['observer_location']['longitude'] 
        self.observer_alt_km = self.config['observer_location']['altitude_km']
        self.min_elevation = self.config['min_elevation']
        
        self.satellites = {}
        self.current_satellites = {}
        self.last_update = None
        self.last_tle_fetch = None
        self._running = False
        self._update_thread = None
        self._lock = threading.Lock()
        
        logger.info("Satellite Tracker initialized")
    
    def fetch_tle_data(self, tle_url: str = None) -> List[Dict]:
        """
        Fetch TLE data from CelesTrak.
        
        Args:
            tle_url: URL to fetch TLE data from
            
        Returns:
            List of satellite dictionaries with name and TLE data
        """
        if tle_url is None:
            tle_url = self.config['tle_url']
            
        try:
            timeout = Config.NETWORK['connection_timeout']
            response = requests.get(tle_url, timeout=timeout)
            response.raise_for_status()
            
            lines = response.text.strip().split('\n')
            satellites = []
            
            # Parse TLE format (groups of 3 lines: name, line1, line2)
            for i in range(0, len(lines), 3):
                if i + 2 < len(lines):
                    name = lines[i].strip()
                    line1 = lines[i + 1].strip()
                    line2 = lines[i + 2].strip()
                    
                    if line1.startswith('1 ') and line2.startswith('2 '):
                        satellites.append({
                            'name': name,
                            'line1': line1,
                            'line2': line2
                        })
            
            logger.info(f"Fetched {len(satellites)} satellites from CelesTrak")
            return satellites
            
        except Exception as e:
            logger.error(f"Error fetching TLE data: {e}")
            return []
    
    def load_satellites(self, limit: int = None):
        """
        Load satellite data and create SGP4 satellite objects.
        
        Args:
            limit: Maximum number of satellites to load (for performance)
        """
        if limit is None:
            limit = self.config['max_satellites']
            
        logger.info(f"Starting to load satellites with limit: {limit}")
        tle_data = self.fetch_tle_data()
        logger.info(f"Processing TLE data for {min(len(tle_data), limit)} satellites out of {len(tle_data)} total")
        
        satellites = {}
        count = 0
        errors = 0
        
        # Process only up to the limit
        for i, sat_data in enumerate(tle_data[:limit]):
            try:
                # Create SGP4 satellite object
                satellite = Satrec.twoline2rv(sat_data['line1'], sat_data['line2'])
                satellites[sat_data['name']] = satellite
                count += 1
                
                # Log progress every 100 satellites
                if (i + 1) % 100 == 0:
                    logger.info(f"Processed {i + 1}/{min(len(tle_data), limit)} satellites...")
                    
            except Exception as e:
                errors += 1
                logger.debug(f"Error parsing satellite {sat_data['name']}: {e}")
        
        logger.info(f"Finished processing satellites: {count} loaded successfully, {errors} errors")
        
        with self._lock:
            self.satellites = satellites
            self.last_tle_fetch = datetime.now()
        
        logger.info(f"Loaded {count} satellites successfully into memory")
    
    def calculate_look_angles(self, sat_pos_teme: Tuple[float, float, float], 
                            obs_time: datetime) -> Tuple[float, float, float]:
        """
        Calculate azimuth, elevation, and range from observer to satellite.
        
        Args:
            sat_pos_teme: Satellite position in TEME coordinates (km)
            obs_time: Observation time
            
        Returns:
            Tuple of (azimuth_deg, elevation_deg, range_km)
        """
        # Convert observer location to ECEF coordinates
        lat_rad = radians(self.observer_lat)
        lon_rad = radians(self.observer_lon)
        
        # Earth radius in km
        earth_radius = 6378.137
        
        # Observer position in ECEF
        cos_lat = cos(lat_rad)
        sin_lat = sin(lat_rad)
        cos_lon = cos(lon_rad)
        sin_lon = sin(lon_rad)
        
        obs_x = (earth_radius + self.observer_alt_km) * cos_lat * cos_lon
        obs_y = (earth_radius + self.observer_alt_km) * cos_lat * sin_lon
        obs_z = (earth_radius + self.observer_alt_km) * sin_lat
        
        # Vector from observer to satellite
        dx = sat_pos_teme[0] - obs_x
        dy = sat_pos_teme[1] - obs_y
        dz = sat_pos_teme[2] - obs_z
        
        # Range
        range_km = sqrt(dx*dx + dy*dy + dz*dz)
        
        # Convert to topocentric coordinates
        # South, East, Up coordinate system
        south = -cos_lon * cos_lat * dx - sin_lon * cos_lat * dy + sin_lat * dz
        east = -sin_lon * dx + cos_lon * dy
        up = sin_lon * sin_lat * dx + cos_lon * sin_lat * dy + cos_lat * dz
        
        # Calculate azimuth and elevation
        azimuth_rad = atan2(east, south)
        azimuth_deg = degrees(azimuth_rad)
        if azimuth_deg < 0:
            azimuth_deg += 360
        
        elevation_rad = asin(up / range_km)
        elevation_deg = degrees(elevation_rad)
        
        return azimuth_deg, elevation_deg, range_km
    
    def get_satellite_category(self, sat_name: str) -> str:
        """Categorize satellite by name patterns"""
        name_upper = sat_name.upper()
        
        if 'ISS' in name_upper:
            return 'Space Station'
        elif any(keyword in name_upper for keyword in ['TIANHE', 'TIANGONG', 'CSS']):
            return 'Space Station'
        elif any(keyword in name_upper for keyword in ['STARLINK', 'ONEWEB', 'IRIDIUM']):
            return 'Communications'
        elif any(keyword in name_upper for keyword in ['LANDSAT', 'SENTINEL', 'SPOT']):
            return 'Earth Observation'
        elif any(keyword in name_upper for keyword in ['GPS', 'GLONASS', 'GALILEO', 'BEIDOU']):
            return 'Navigation'
        elif any(keyword in name_upper for keyword in ['WEATHER', 'GOES', 'NOAA']):
            return 'Weather'
        elif any(keyword in name_upper for keyword in ['HUBBLE', 'KEPLER', 'TESS']):
            return 'Science'
        else:
            return 'Other'
    
    def calculate_orbital_velocity(self, altitude_km: float) -> float:
        """Calculate approximate orbital velocity in km/s"""
        earth_radius = 6378.137  # km
        mu = 398600.4418  # Earth's gravitational parameter (km³/s²)
        
        orbital_radius = earth_radius + altitude_km
        velocity = sqrt(mu / orbital_radius)  # km/s
        
        return velocity
    
    def get_overhead_satellites(self, obs_time: Optional[datetime] = None) -> List[Dict]:
        """
        Get satellites currently above the minimum elevation.
        
        Args:
            obs_time: Observation time (uses current time if None)
            
        Returns:
            List of dictionaries with satellite info and position data
        """
        with self._lock:
            if not self.satellites:
                logger.debug("No satellites loaded")
                return []
        
        if obs_time is None:
            obs_time = datetime.now(timezone.utc)
        
        # Convert to Julian date for SGP4
        jd = obs_time.timestamp() / 86400.0 + 2440587.5
        fr = 0.0
        
        overhead_satellites = []
        
        with self._lock:
            satellites_copy = self.satellites.copy()
        
        for name, satellite in satellites_copy.items():
            try:
                # Propagate satellite position
                error, pos_teme, vel_teme = satellite.sgp4(jd, fr)
                
                if error == 0:  # No error in propagation
                    # Calculate look angles
                    azimuth, elevation, range_km = self.calculate_look_angles(pos_teme, obs_time)
                    
                    # Check if above minimum elevation
                    if elevation >= self.min_elevation:
                        # Calculate altitude above Earth
                        earth_radius = 6378.137
                        sat_position_magnitude = sqrt(pos_teme[0]**2 + pos_teme[1]**2 + pos_teme[2]**2)
                        altitude_km = sat_position_magnitude - earth_radius
                        
                        # Calculate velocity
                        velocity_kmh = self.calculate_orbital_velocity(altitude_km) * 3600  # Convert to km/h
                        
                        overhead_satellites.append({
                            'name': name,
                            'azimuth': round(azimuth, 1),
                            'elevation': round(elevation, 1),
                            'range_km': round(range_km, 1),
                            'altitude_km': round(altitude_km, 1),
                            'velocity_kmh': round(velocity_kmh, 1),
                            'category': self.get_satellite_category(name),
                            'position_teme': pos_teme,
                            'velocity_teme': vel_teme,
                            'last_seen': obs_time.isoformat()
                        })
                        
            except Exception as e:
                logger.debug(f"Error processing satellite {name}: {e}")
                continue
        
        # Sort by elevation (highest first)
        overhead_satellites.sort(key=lambda x: x['elevation'], reverse=True)
        
        # Limit number of satellites
        max_count = self.config['display_settings']['max_display_count']
        return overhead_satellites[:max_count]
    
    def start(self):
        """Start satellite tracking"""
        if not self.config['enabled']:
            logger.info("Satellite tracking disabled in configuration")
            return False
        
        with self._lock:
            if self._running:
                logger.info("Satellite tracker already running")
                return True
            
            try:
                logger.info("Starting satellite tracker initialization")
                
                # Load satellite data
                logger.info("Loading satellite data...")
                self.load_satellites()
                logger.info("Satellite data loaded, starting update thread")
                
                self._running = True
                self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
                self._update_thread.start()
                
                logger.info("Satellite tracker started successfully")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start satellite tracker: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                self._running = False
                return False
    
    def stop(self):
        """Stop satellite tracking"""
        with self._lock:
            if not self._running:
                return
            
            self._running = False
            
            if self._update_thread and self._update_thread.is_alive():
                self._update_thread.join(timeout=2.0)
            
            logger.info("Satellite tracker stopped")
    
    def _update_loop(self):
        """Main update loop for fetching satellite positions"""
        logger.info("Satellite update loop started")
        logger.info(f"Update interval: {self.config['update_interval']} seconds")
        logger.info(f"Currently tracking {len(self.satellites)} satellites")
        
        while self._running:
            try:
                # Check if we need to refresh TLE data
                if (self.last_tle_fetch is None or 
                    datetime.now() - self.last_tle_fetch > timedelta(hours=self.config['tle_refresh_hours'])):
                    logger.info("Refreshing TLE data")
                    self.load_satellites()
                
                # Get current overhead satellites
                logger.debug("Calculating overhead satellites...")
                overhead_satellites = self.get_overhead_satellites()
                
                with self._lock:
                    self.current_satellites = {
                        sat['name']: sat for sat in overhead_satellites
                    }
                    self.last_update = datetime.now()
                
                logger.info(f"Updated satellite data: {len(overhead_satellites)} satellites above {self.min_elevation}° elevation")
                
                # Wait for next update
                time.sleep(self.config['update_interval'])
                
            except Exception as e:
                logger.error(f"Error in satellite update loop: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                time.sleep(30)  # Wait longer on errors
        
        logger.info("Satellite update loop ended")
    
    def get_current_satellites(self) -> List[Dict]:
        """Get current satellites above minimum elevation"""
        with self._lock:
            satellites = list(self.current_satellites.values())
            return sorted(satellites, key=lambda x: x['elevation'], reverse=True)
    
    def get_status(self) -> Dict:
        """Get satellite tracker status"""
        with self._lock:
            return {
                'running': self._running,
                'enabled': self.config['enabled'],
                'last_update': self.last_update.isoformat() if self.last_update else None,
                'last_tle_fetch': self.last_tle_fetch.isoformat() if self.last_tle_fetch else None,
                'satellite_count': len(self.current_satellites),
                'loaded_satellites': len(self.satellites),
                'min_elevation': self.min_elevation,
                'observer_location': {
                    'latitude': self.observer_lat,
                    'longitude': self.observer_lon,
                    'altitude_km': self.observer_alt_km
                },
                'tle_url': self.config['tle_url']
            }
    
    def is_running(self) -> bool:
        """Check if satellite tracker is running"""
        return self._running