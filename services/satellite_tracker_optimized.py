"""
Optimized Satellite Overhead Tracker Service
Tracks satellites with pre-calculated paths and proximity filtering
"""

import requests
import numpy as np
import time
import math
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Dict, Optional, Set
import threading
from collections import deque
import heapq

from sgp4.api import Satrec
from sgp4.earth_gravity import wgs84
from math import degrees, radians, sin, cos, sqrt, atan2, asin

from config.config import Config

logger = logging.getLogger(__name__)


class OptimizedSatelliteTracker:
    """Optimized satellite tracker with pre-calculation and efficient filtering"""
    
    def __init__(self):
        """Initialize optimized satellite tracker"""
        self.config = Config.SATELLITE
        self.observer_lat = self.config['observer_location']['latitude']
        self.observer_lon = self.config['observer_location']['longitude'] 
        self.observer_alt_km = self.config['observer_location']['altitude_km']
        self.min_elevation = self.config['min_elevation']
        
        # Core satellite data
        self.satellites = {}  # name -> Satrec object
        self.satellite_metadata = {}  # name -> metadata (norad_id, etc.)
        self.satellite_cache = {}  # name -> pre-calculated data
        self.visible_satellites = {}  # Currently visible satellites
        
        # Performance optimization
        self.batch_size = 50  # Process satellites in batches
        self.cache_duration = 300  # Cache predictions for 5 minutes
        self.max_prediction_points = 20  # Points to pre-calculate per satellite
        
        # State management
        self.last_update = None
        self.last_tle_fetch = None
        self.last_cache_refresh = None
        self.last_api_request = None  # Track last API request for rate limiting
        self._running = False
        self._update_thread = None
        self._cache_thread = None
        self._lock = threading.Lock()
        self._cache_lock = threading.Lock()
        
        # Performance metrics
        self.processing_times = deque(maxlen=100)
        self.satellites_processed = 0
        
        logger.info("Optimized Satellite Tracker initialized")
    
    def fetch_tle_data(self, tle_url: str = None) -> List[Dict]:
        """
        Fetch TLE data with local caching and rate limiting.
        Only downloads from CelesTrak if cache is older than configured hours.
        """
        if tle_url is None:
            tle_url = self.config['tle_url']
        
        cache_file = self.config.get('tle_cache_file', 'cache/tle/active_satellites.tle')
        cache_hours = self.config.get('tle_cache_hours', 3)
        
        # Create cache directory if it doesn't exist
        cache_dir = os.path.dirname(cache_file)
        os.makedirs(cache_dir, exist_ok=True)
        
        # Check if cache file exists and is still fresh
        cache_fresh = False
        if os.path.exists(cache_file):
            cache_age = time.time() - os.path.getmtime(cache_file)
            cache_age_hours = cache_age / 3600
            cache_fresh = cache_age_hours < cache_hours
            
            if cache_fresh:
                logger.info(f"Using cached TLE data (age: {cache_age_hours:.1f} hours)")
            else:
                logger.info(f"Cache expired (age: {cache_age_hours:.1f} hours), will fetch new data")
        
        # If cache is fresh, load from file
        if cache_fresh:
            try:
                with open(cache_file, 'r') as f:
                    content = f.read()
                return self._parse_tle_content(content)
            except Exception as e:
                logger.warning(f"Error reading cache file, will fetch from API: {e}")
        
        # Cache is stale or missing, fetch from API with rate limiting
        logger.info(f"Fetching TLE data from CelesTrak: {tle_url}")
        
        # Rate limiting: ensure at least 30 seconds between API requests
        min_interval = 30  # seconds
        if self.last_api_request:
            time_since_last = time.time() - self.last_api_request
            if time_since_last < min_interval:
                wait_time = min_interval - time_since_last
                logger.info(f"Rate limiting: waiting {wait_time:.1f} seconds before API request")
                time.sleep(wait_time)
        
        try:
            # Add rate limiting - respect CelesTrak's guidelines
            timeout = Config.NETWORK['connection_timeout']
            headers = {
                'User-Agent': 'UFO-Tracker/1.0 (contact: your-email@example.com)'  # Identify the application
            }
            
            self.last_api_request = time.time()  # Record API request time
            response = requests.get(tle_url, timeout=timeout, headers=headers)
            response.raise_for_status()
            
            # Save to cache file
            with open(cache_file, 'w') as f:
                f.write(response.text)
            
            logger.info(f"Successfully cached TLE data to {cache_file}")
            
            return self._parse_tle_content(response.text)
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logger.error("CelesTrak access blocked (403 Forbidden). Using cached data if available.")
                # Try to use existing cache even if stale
                if os.path.exists(cache_file):
                    logger.info("Using stale cached data due to API block")
                    with open(cache_file, 'r') as f:
                        content = f.read()
                    return self._parse_tle_content(content)
                else:
                    logger.error("No cached data available and API is blocked")
                    return []
            else:
                logger.error(f"HTTP error fetching TLE data: {e}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching TLE data: {e}")
            # Try to use cached data as fallback
            if os.path.exists(cache_file):
                logger.info("Using cached data as fallback due to fetch error")
                with open(cache_file, 'r') as f:
                    content = f.read()
                return self._parse_tle_content(content)
            return []
    
    def _parse_tle_content(self, content: str) -> List[Dict]:
        """
        Parse TLE content into satellite data structures.
        """
        lines = content.strip().split('\n')
        satellites = []
        
        # Parse TLE format (groups of 3 lines: name, line1, line2)
        for i in range(0, len(lines), 3):
            if i + 2 < len(lines):
                name = lines[i].strip()
                line1 = lines[i + 1].strip()
                line2 = lines[i + 2].strip()
                
                if line1.startswith('1 ') and line2.startswith('2 '):
                    # Extract NORAD ID from line 1 (columns 3-7, 1-based indexing)
                    norad_id = line1[2:7].strip() if len(line1) >= 7 else None
                    # Try to convert to integer to validate
                    try:
                        norad_id = int(norad_id) if norad_id else None
                    except ValueError:
                        norad_id = None
                    
                    satellites.append({
                        'name': name,
                        'line1': line1,
                        'line2': line2,
                        'norad_id': norad_id
                    })
        
        logger.info(f"Parsed {len(satellites)} satellites from TLE data")
        return satellites
    
    def quick_visibility_check(self, satellite: Satrec, jd: float, fr: float) -> bool:
        """
        Quick check if satellite might be visible (rough approximation).
        Returns True if satellite should be processed further.
        """
        try:
            # Quick propagation
            error, pos_teme, _ = satellite.sgp4(jd, fr)
            if error != 0:
                return False
            
            # Calculate distance from Earth center
            earth_radius = 6378.137  # km
            sat_magnitude = sqrt(pos_teme[0]**2 + pos_teme[1]**2 + pos_teme[2]**2)
            altitude_km = sat_magnitude - earth_radius
            
            # Filter by reasonable orbital altitudes
            # LEO: 160-2000km, MEO: 2000-35,786km, GEO: ~35,786km
            if altitude_km < 150 or altitude_km > 50000:
                return False
            
            # Quick range check from observer location with proper TEME to ECEF conversion
            # Calculate Greenwich Mean Sidereal Time for the observation time
            T = (jd - 2451545.0) / 36525.0  # Julian centuries since J2000.0
            gmst_deg = (280.46061837 + 360.98564736629 * (jd - 2451545.0) + 
                       T * T * (0.000387933 - T / 38710000.0)) % 360.0
            gmst_rad = radians(gmst_deg)
            
            # Convert TEME to ECEF
            cos_gmst = cos(gmst_rad)
            sin_gmst = sin(gmst_rad)
            
            sat_x_ecef = cos_gmst * pos_teme[0] + sin_gmst * pos_teme[1]
            sat_y_ecef = -sin_gmst * pos_teme[0] + cos_gmst * pos_teme[1]
            sat_z_ecef = pos_teme[2]
            
            # Observer position in ECEF
            lat_rad = radians(self.observer_lat)
            lon_rad = radians(self.observer_lon)
            
            obs_x = (earth_radius + self.observer_alt_km) * cos(lat_rad) * cos(lon_rad)
            obs_y = (earth_radius + self.observer_alt_km) * cos(lat_rad) * sin(lon_rad)
            obs_z = (earth_radius + self.observer_alt_km) * sin(lat_rad)
            
            # Distance from observer to satellite in ECEF
            dx = sat_x_ecef - obs_x
            dy = sat_y_ecef - obs_y
            dz = sat_z_ecef - obs_z
            range_km = sqrt(dx*dx + dy*dy + dz*dz)
            
            # Skip satellites that are extremely far (likely calculation errors)
            if range_km > 50000:
                return False
                
            return True
            
        except:
            return False
    
    def load_satellites(self, limit: int = None):
        """
        Load satellite data with intelligent filtering.
        """
        if limit is None:
            limit = self.config['max_satellites']
            
        logger.info(f"Loading satellites with limit: {limit}")
        tle_data = self.fetch_tle_data()
        
        if not tle_data:
            logger.error("No TLE data fetched")
            return
        
        # Priority categories for loading
        priority_keywords = {
            'ISS': 1,
            'TIANGONG': 1,
            'TIANHE': 1,
            'STARLINK': 2,
            'IRIDIUM': 2,
            'ONEWEB': 3,
            'GPS': 4,
            'GLONASS': 4,
            'GALILEO': 4,
            'BEIDOU': 4
        }
        
        # Sort satellites by priority
        def get_priority(sat_data):
            name_upper = sat_data['name'].upper()
            for keyword, priority in priority_keywords.items():
                if keyword in name_upper:
                    return priority
            return 5  # Default priority
        
        tle_data.sort(key=get_priority)
        
        satellites = {}
        count = 0
        errors = 0
        
        # Quick visibility pre-check for current time
        obs_time = datetime.now(timezone.utc)
        jd = obs_time.timestamp() / 86400.0 + 2440587.5
        fr = 0.0
        
        for sat_data in tle_data:
            if count >= limit:
                break
                
            try:
                # Create SGP4 satellite object
                satellite = Satrec.twoline2rv(sat_data['line1'], sat_data['line2'])
                
                # Quick visibility check
                if self.quick_visibility_check(satellite, jd, fr):
                    satellites[sat_data['name']] = satellite
                    # Store metadata including NORAD ID
                    self.satellite_metadata[sat_data['name']] = {
                        'norad_id': sat_data.get('norad_id'),
                        'loaded_at': datetime.now().isoformat()
                    }
                    count += 1
                    
                    if count % 100 == 0:
                        logger.info(f"Loaded {count} potentially visible satellites")
                        
            except Exception as e:
                errors += 1
                if errors < 10:  # Only log first few errors
                    logger.debug(f"Error parsing satellite {sat_data['name']}: {e}")
        
        with self._lock:
            self.satellites = satellites
            self.last_tle_fetch = datetime.now()
        
        logger.info(f"Loaded {count} satellites (filtered from {len(tle_data)} total)")
    
    def pre_calculate_path(self, name: str, satellite: Satrec, 
                          start_time: datetime, duration_minutes: int = 5) -> Dict:
        """
        Pre-calculate satellite path for the next few minutes.
        """
        logger.debug(f"Starting path calculation for {name}")
        path_points = []
        time_step = duration_minutes * 60 / self.max_prediction_points  # seconds
        
        for i in range(self.max_prediction_points):
            calc_time = start_time + timedelta(seconds=i * time_step)
            jd = calc_time.timestamp() / 86400.0 + 2440587.5
            fr = 0.0
            
            try:
                error, pos_teme, vel_teme = satellite.sgp4(jd, fr)
                if error == 0:
                    azimuth, elevation, range_km = self.calculate_look_angles(pos_teme, calc_time)
                    
                    # Calculate velocity magnitude in km/s
                    velocity_kms = sqrt(vel_teme[0]**2 + vel_teme[1]**2 + vel_teme[2]**2)
                    # Convert to mph (1 km/s = 2236.94 mph)
                    velocity_mph = velocity_kms * 2236.94
                    
                    # Check for NaN or infinite values
                    if not (math.isfinite(azimuth) and math.isfinite(elevation) and math.isfinite(range_km)):
                        logger.warning(f"Invalid coordinates for {name}: az={azimuth}, el={elevation}, range={range_km}")
                        continue
                    
                    path_points.append({
                        'time': calc_time.isoformat(),
                        'azimuth': round(azimuth, 1),
                        'elevation': round(elevation, 1),
                        'range_km': round(range_km, 1),
                        'velocity_mph': round(velocity_mph, 0),
                        'visible': elevation >= self.min_elevation
                    })
            except Exception as e:
                logger.debug(f"Error calculating position for {name} at step {i}: {e}")
                continue
        
        # Determine if satellite will be visible in the time window
        any_visible = any(p['visible'] for p in path_points) if path_points else False
        max_elevation = max((p['elevation'] for p in path_points), default=-90) if path_points else -90
        
        logger.debug(f"Completed path calculation for {name}: {len(path_points)} points, visible: {any_visible}")
        
        return {
            'name': name,
            'path': path_points,
            'will_be_visible': any_visible,
            'max_elevation': max_elevation,
            'calculated_at': datetime.now().isoformat(),
            'category': self.get_satellite_category(name),
            'norad_id': self.satellite_metadata.get(name, {}).get('norad_id')
        }
    
    def calculate_look_angles(self, sat_pos_teme: Tuple[float, float, float], 
                            obs_time: datetime) -> Tuple[float, float, float]:
        """
        Calculate azimuth, elevation, and range from observer to satellite.
        TEME coordinates need to be converted to ECEF using Greenwich Sidereal Time.
        """
        # Calculate Greenwich Sidereal Time for proper TEME to ECEF conversion
        # Julian date calculation
        jd = obs_time.timestamp() / 86400.0 + 2440587.5
        
        # Calculate Greenwich Mean Sidereal Time (GMST) in radians
        # This accounts for Earth's rotation
        T = (jd - 2451545.0) / 36525.0  # Julian centuries since J2000.0
        gmst_deg = (280.46061837 + 360.98564736629 * (jd - 2451545.0) + 
                   T * T * (0.000387933 - T / 38710000.0)) % 360.0
        gmst_rad = radians(gmst_deg)
        
        # Convert TEME to ECEF (Earth-Centered Earth-Fixed)
        # TEME rotates with Earth's mean rotation, ECEF is fixed to Earth
        cos_gmst = cos(gmst_rad)
        sin_gmst = sin(gmst_rad)
        
        # Rotation matrix from TEME to ECEF around Z-axis
        sat_x_ecef = cos_gmst * sat_pos_teme[0] + sin_gmst * sat_pos_teme[1]
        sat_y_ecef = -sin_gmst * sat_pos_teme[0] + cos_gmst * sat_pos_teme[1]
        sat_z_ecef = sat_pos_teme[2]  # Z component unchanged
        
        # Observer position in ECEF coordinates
        lat_rad = radians(self.observer_lat)
        lon_rad = radians(self.observer_lon)
        
        # Earth radius in km (WGS84)
        earth_radius = 6378.137
        
        # Observer position in ECEF
        cos_lat = cos(lat_rad)
        sin_lat = sin(lat_rad)
        cos_lon = cos(lon_rad)
        sin_lon = sin(lon_rad)
        
        obs_x_ecef = (earth_radius + self.observer_alt_km) * cos_lat * cos_lon
        obs_y_ecef = (earth_radius + self.observer_alt_km) * cos_lat * sin_lon
        obs_z_ecef = (earth_radius + self.observer_alt_km) * sin_lat
        
        # Vector from observer to satellite in ECEF
        dx = sat_x_ecef - obs_x_ecef
        dy = sat_y_ecef - obs_y_ecef
        dz = sat_z_ecef - obs_z_ecef
        
        # Range
        range_km = sqrt(dx*dx + dy*dy + dz*dz)
        
        # Convert to local topocentric coordinates (SEZ: South, East, Zenith)
        # Standard transformation from ECEF to topocentric
        south = -sin_lat * cos_lon * dx - sin_lat * sin_lon * dy + cos_lat * dz
        east = -sin_lon * dx + cos_lon * dy  
        up = cos_lat * cos_lon * dx + cos_lat * sin_lon * dy + sin_lat * dz
        
        # Calculate elevation and azimuth
        elevation_rad = asin(up / range_km) if range_km > 0 else 0
        elevation_deg = degrees(elevation_rad)
        
        # Azimuth (from North, clockwise)
        azimuth_rad = atan2(east, south)
        azimuth_deg = degrees(azimuth_rad)
        if azimuth_deg < 0:
            azimuth_deg += 360
        
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
    
    def refresh_cache(self):
        """
        Refresh the pre-calculated cache for all satellites.
        Runs in a separate thread to avoid blocking.
        """
        start_time = time.time()
        logger.info("Starting cache refresh")
        
        logger.info("Attempting to acquire lock...")
        with self._lock:
            logger.info("Lock acquired, getting satellite list...")
            satellites_to_process = list(self.satellites.items())
            logger.info(f"Got {len(satellites_to_process)} satellites from lock")
        logger.info("Lock released")
        
        logger.info(f"Processing {len(satellites_to_process)} satellites in batches of {self.batch_size}")
        
        new_cache = {}
        visible_count = 0
        processed_count = 0
        
        # Process in batches for better performance
        for i in range(0, len(satellites_to_process), self.batch_size):
            batch = satellites_to_process[i:i + self.batch_size]
            current_time = datetime.now(timezone.utc)
            
            logger.info(f"Processing batch {i//self.batch_size + 1}: satellites {i+1} to {min(i+len(batch), len(satellites_to_process))}")
            
            for name, satellite in batch:
                try:
                    logger.debug(f"Processing satellite: {name}")
                    cache_entry = self.pre_calculate_path(name, satellite, current_time)
                    
                    if cache_entry['will_be_visible']:
                        new_cache[name] = cache_entry
                        visible_count += 1
                        
                    processed_count += 1
                    
                except Exception as e:
                    logger.warning(f"Error caching satellite {name}: {e}")
                    processed_count += 1
            
            logger.info(f"Batch complete. Processed: {processed_count}/{len(satellites_to_process)}, Visible: {visible_count}")
            
            # Yield to other threads
            time.sleep(0.01)
        
        # Update cache atomically
        with self._cache_lock:
            self.satellite_cache = new_cache
            self.last_cache_refresh = datetime.now()
        
        elapsed = time.time() - start_time
        self.processing_times.append(elapsed)
        
        logger.info(f"Cache refresh complete: {visible_count} visible satellites "
                   f"out of {len(satellites_to_process)} in {elapsed:.2f}s")
    
    def get_overhead_satellites(self, obs_time: Optional[datetime] = None) -> List[Dict]:
        """
        Get satellites currently above the minimum elevation using cached data.
        """
        if obs_time is None:
            obs_time = datetime.now(timezone.utc)
        
        overhead_satellites = []
        
        with self._cache_lock:
            cache_copy = self.satellite_cache.copy()
        
        for name, cache_entry in cache_copy.items():
            # Find the closest pre-calculated point
            if not cache_entry['path']:
                continue
                
            # Get the FIRST point from path (current position)
            # Only use it if it's currently visible
            if cache_entry['path']:
                current_data = cache_entry['path'][0]  # First point is most recent
                current_visible = current_data.get('visible', False)
            else:
                current_visible = False
                current_data = None
            
            if current_visible and current_data:
                # Filter out satellites that are too far away (likely positioning errors)
                # Most LEO satellites are 200-2000km, MEO up to 35,786km for GEO
                range_km = current_data['range_km']
                if range_km > 50000:  # Skip satellites reported over 50,000km away
                    logger.debug(f"Skipping {name}: too far away ({range_km:.1f}km)")
                    continue
                
                # Calculate additional data if needed
                earth_radius = 6378.137
                altitude_km = current_data['range_km'] * sin(radians(current_data['elevation']))
                
                # Filter out satellites with impossible altitudes
                if altitude_km < 150 or altitude_km > 50000:  # LEO starts around 160km, filter beyond 50,000km
                    logger.debug(f"Skipping {name}: invalid altitude ({altitude_km:.1f}km)")
                    continue
                
                overhead_satellites.append({
                    'name': name,
                    'azimuth': current_data['azimuth'],
                    'elevation': current_data['elevation'],
                    'range_km': range_km,
                    'altitude_km': round(altitude_km, 1),
                    'velocity_mph': current_data.get('velocity_mph', 0),
                    'category': cache_entry['category'],
                    'max_elevation': cache_entry['max_elevation'],
                    'last_seen': obs_time.isoformat(),
                    'norad_id': cache_entry.get('norad_id'),
                    'path': cache_entry.get('path', [])  # Include the cached trajectory path
                })
        
        # Sort by elevation (highest first)
        overhead_satellites.sort(key=lambda x: x['elevation'], reverse=True)
        
        # Limit number of satellites
        max_count = self.config['display_settings']['max_display_count']
        return overhead_satellites[:max_count]
    
    def _cache_refresh_loop(self):
        """Background thread for cache refresh"""
        logger.info("Cache refresh loop started")
        
        while self._running:
            try:
                self.refresh_cache()
                
                # Wait before next refresh
                time.sleep(self.cache_duration)
                
            except Exception as e:
                logger.error(f"Error in cache refresh loop: {e}")
                time.sleep(60)
        
        logger.info("Cache refresh loop ended")
    
    def _update_loop(self):
        """Main update loop for updating visible satellites"""
        logger.info("Satellite update loop started")
        
        while self._running:
            try:
                # Check if we need to refresh TLE data
                if (self.last_tle_fetch is None or 
                    datetime.now() - self.last_tle_fetch > timedelta(hours=self.config['tle_refresh_hours'])):
                    logger.info("Refreshing TLE data")
                    self.load_satellites()
                    # Force cache refresh after loading new TLEs
                    self.refresh_cache()
                
                # Get current overhead satellites from cache
                overhead_satellites = self.get_overhead_satellites()
                
                with self._lock:
                    self.visible_satellites = {
                        sat['name']: sat for sat in overhead_satellites
                    }
                    self.last_update = datetime.now()
                    self.satellites_processed = len(self.satellite_cache)
                
                logger.info(f"Updated: {len(overhead_satellites)} visible satellites "
                           f"from {self.satellites_processed} cached")
                
                # Wait for next update
                time.sleep(self.config['update_interval'])
                
            except Exception as e:
                logger.error(f"Error in satellite update loop: {e}")
                time.sleep(30)
        
        logger.info("Satellite update loop ended")
    
    def start(self):
        """Start satellite tracking"""
        if not self.config['enabled']:
            logger.info("Satellite tracking disabled in configuration")
            return False
        
        with self._lock:
            if self._running:
                logger.info("Satellite tracker already running")
                return True
            
            self._running = True
        
        try:
            logger.info("Starting optimized satellite tracker")
            
            # Load satellite data
            self.load_satellites()
            
            # Initial cache population
            self.refresh_cache()
            
            # Start cache refresh thread
            self._cache_thread = threading.Thread(target=self._cache_refresh_loop, daemon=True)
            self._cache_thread.start()
            
            # Start update thread
            self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
            self._update_thread.start()
            
            logger.info("Optimized satellite tracker started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start satellite tracker: {e}")
            with self._lock:
                self._running = False
            return False
    
    def stop(self):
        """Stop satellite tracking"""
        with self._lock:
            if not self._running:
                return
            
            self._running = False
            
            # Wait for threads to finish
            for thread in [self._update_thread, self._cache_thread]:
                if thread and thread.is_alive():
                    thread.join(timeout=2.0)
            
            logger.info("Optimized satellite tracker stopped")
    
    def get_current_satellites(self) -> List[Dict]:
        """Get current satellites above minimum elevation"""
        with self._lock:
            satellites = list(self.visible_satellites.values())
            return sorted(satellites, key=lambda x: x['elevation'], reverse=True)
    
    def get_status(self) -> Dict:
        """Get satellite tracker status with performance metrics"""
        with self._lock:
            avg_processing_time = (
                sum(self.processing_times) / len(self.processing_times)
                if self.processing_times else 0
            )
            
            return {
                'running': self._running,
                'enabled': self.config['enabled'],
                'last_update': self.last_update.isoformat() if self.last_update else None,
                'last_tle_fetch': self.last_tle_fetch.isoformat() if self.last_tle_fetch else None,
                'last_cache_refresh': self.last_cache_refresh.isoformat() if self.last_cache_refresh else None,
                'visible_satellites': len(self.visible_satellites),
                'cached_satellites': len(self.satellite_cache),
                'loaded_satellites': len(self.satellites),
                'satellites_processed': self.satellites_processed,
                'avg_processing_time': round(avg_processing_time, 3),
                'min_elevation': self.min_elevation,
                'cache_duration': self.cache_duration,
                'observer_location': {
                    'latitude': self.observer_lat,
                    'longitude': self.observer_lon,
                    'altitude_km': self.observer_alt_km
                }
            }
    
    def is_running(self) -> bool:
        """Check if satellite tracker is running"""
        return self._running