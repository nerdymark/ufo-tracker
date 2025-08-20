"""
ADSB Flight Tracker Service
Fetches flight data from local PiAware SkyAware and processes nearby aircraft
"""

import requests
import time
import math
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import threading

from config.config import Config

logger = logging.getLogger(__name__)

class ADSBTracker:
    """ADSB flight tracker that fetches data from local PiAware SkyAware"""
    
    def __init__(self):
        """Initialize ADSB tracker"""
        self.config = Config.ADSB
        self.observer_lat = self.config['observer_location']['latitude']
        self.observer_lon = self.config['observer_location']['longitude']
        self.observer_alt = self.config['observer_location']['altitude_feet']
        self.max_distance = self.config['max_distance_miles']
        
        self.current_flights = {}
        self.last_update = None
        self._running = False
        self._update_thread = None
        self._lock = threading.Lock()
        
        logger.info("ADSB Tracker initialized")
    
    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in miles using Haversine formula"""
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = (math.sin(dlat/2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2)
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth's radius in miles
        earth_radius_miles = 3959.0
        distance = earth_radius_miles * c
        
        return distance
    
    def calculate_bearing(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate bearing from observer to aircraft in degrees"""
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlon_rad = math.radians(lon2 - lon1)
        
        y = math.sin(dlon_rad) * math.cos(lat2_rad)
        x = (math.cos(lat1_rad) * math.sin(lat2_rad) - 
             math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon_rad))
        
        bearing_rad = math.atan2(y, x)
        bearing_deg = math.degrees(bearing_rad)
        
        # Normalize to 0-360 degrees
        bearing_deg = (bearing_deg + 360) % 360
        
        return bearing_deg
    
    def calculate_elevation_angle(self, distance_miles: float, altitude_feet: float) -> float:
        """Calculate elevation angle from observer to aircraft"""
        if distance_miles <= 0:
            return 90.0
        
        # Convert distance to feet
        distance_feet = distance_miles * 5280
        
        # Calculate height difference
        height_diff = altitude_feet - self.observer_alt
        
        # Calculate elevation angle
        elevation_rad = math.atan2(height_diff, distance_feet)
        elevation_deg = math.degrees(elevation_rad)
        
        return max(0, elevation_deg)
    
    def fetch_aircraft_data(self) -> Optional[Dict]:
        """Fetch aircraft data from PiAware SkyAware"""
        try:
            url = self.config['piaware_url']
            timeout = Config.NETWORK['connection_timeout']
            
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            
            data = response.json()
            logger.debug(f"Fetched {len(data.get('aircraft', []))} aircraft records")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch ADSB data: {e}")
            return None
        except Exception as e:
            logger.error(f"Error processing ADSB data: {e}")
            return None
    
    def process_aircraft(self, aircraft_data: Dict) -> List[Dict]:
        """Process aircraft data and filter by distance and altitude"""
        if not aircraft_data or 'aircraft' not in aircraft_data:
            return []
        
        processed_flights = []
        current_time = datetime.now()
        
        for aircraft in aircraft_data['aircraft']:
            try:
                # Skip aircraft without position
                if 'lat' not in aircraft or 'lon' not in aircraft:
                    continue
                
                lat = float(aircraft['lat'])
                lon = float(aircraft['lon'])
                
                # Calculate distance
                distance = self.calculate_distance(
                    self.observer_lat, self.observer_lon, lat, lon
                )
                
                # Skip aircraft too far away
                if distance > self.max_distance:
                    continue
                
                # Get altitude (handle different altitude fields)
                altitude = None
                if 'alt_baro' in aircraft:
                    altitude = aircraft['alt_baro']
                elif 'altitude' in aircraft:
                    altitude = aircraft['altitude']
                
                # Skip if no altitude or outside altitude filter
                if altitude is None:
                    continue
                
                altitude = float(altitude)
                if (altitude < self.config['altitude_filter']['min_feet'] or 
                    altitude > self.config['altitude_filter']['max_feet']):
                    continue
                
                # Calculate bearing and elevation
                bearing = self.calculate_bearing(
                    self.observer_lat, self.observer_lon, lat, lon
                )
                elevation = self.calculate_elevation_angle(distance, altitude)
                
                # Build flight record
                flight = {
                    'hex': aircraft.get('hex', 'unknown'),
                    'flight': aircraft.get('flight', '').strip() or 'N/A',
                    'lat': lat,
                    'lon': lon,
                    'altitude': altitude,
                    'distance_miles': round(distance, 2),
                    'bearing_degrees': round(bearing, 1),
                    'elevation_degrees': round(elevation, 1),
                    'ground_speed': aircraft.get('gs', aircraft.get('ground_speed', 0)),
                    'track': aircraft.get('track', 0),
                    'vertical_rate': aircraft.get('vert_rate', aircraft.get('vr', 0)),
                    'squawk': aircraft.get('squawk', ''),
                    'category': aircraft.get('category', ''),
                    'last_seen': current_time.isoformat(),
                    'rssi': aircraft.get('rssi', 0),
                    'messages': aircraft.get('messages', 0)
                }
                
                processed_flights.append(flight)
                
            except (ValueError, TypeError) as e:
                logger.debug(f"Error processing aircraft {aircraft.get('hex', 'unknown')}: {e}")
                continue
        
        # Sort by distance (closest first)
        processed_flights.sort(key=lambda x: x['distance_miles'])
        
        # Limit number of displayed flights
        max_count = self.config['display_settings']['max_display_count']
        return processed_flights[:max_count]
    
    def start(self):
        """Start ADSB tracking"""
        if not self.config['enabled']:
            logger.info("ADSB tracking disabled in configuration")
            return False
        
        with self._lock:
            if self._running:
                logger.info("ADSB tracker already running")
                return True
            
            try:
                self._running = True
                self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
                self._update_thread.start()
                
                logger.info("ADSB tracker started")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start ADSB tracker: {e}")
                self._running = False
                return False
    
    def stop(self):
        """Stop ADSB tracking"""
        with self._lock:
            if not self._running:
                return
            
            self._running = False
            
            if self._update_thread and self._update_thread.is_alive():
                self._update_thread.join(timeout=2.0)
            
            logger.info("ADSB tracker stopped")
    
    def _update_loop(self):
        """Main update loop for fetching aircraft data"""
        logger.info("ADSB update loop started")
        
        while self._running:
            try:
                # Fetch and process aircraft data
                aircraft_data = self.fetch_aircraft_data()
                if aircraft_data:
                    processed_flights = self.process_aircraft(aircraft_data)
                    
                    with self._lock:
                        self.current_flights = {
                            flight['hex']: flight for flight in processed_flights
                        }
                        self.last_update = datetime.now()
                    
                    logger.debug(f"Updated ADSB data: {len(processed_flights)} flights within {self.max_distance} miles")
                
                # Wait for next update
                time.sleep(self.config['update_interval'])
                
            except Exception as e:
                logger.error(f"Error in ADSB update loop: {e}")
                time.sleep(5)  # Wait longer on errors
        
        logger.info("ADSB update loop ended")
    
    def get_current_flights(self) -> List[Dict]:
        """Get current flights within range"""
        with self._lock:
            flights = list(self.current_flights.values())
            return sorted(flights, key=lambda x: x['distance_miles'])
    
    def get_status(self) -> Dict:
        """Get ADSB tracker status"""
        with self._lock:
            return {
                'running': self._running,
                'enabled': self.config['enabled'],
                'last_update': self.last_update.isoformat() if self.last_update else None,
                'flight_count': len(self.current_flights),
                'max_distance_miles': self.max_distance,
                'observer_location': {
                    'latitude': self.observer_lat,
                    'longitude': self.observer_lon,
                    'altitude_feet': self.observer_alt
                },
                'piaware_url': self.config['piaware_url']
            }
    
    def is_running(self) -> bool:
        """Check if ADSB tracker is running"""
        return self._running