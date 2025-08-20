import requests
import json
import threading
import time
from typing import Dict, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ADSBService:
    def __init__(self, dump1090_url: str = "http://localhost:8080"):
        self.dump1090_url = dump1090_url
        self.aircraft_cache = {}
        self.last_update = None
        self.update_thread = None
        self.running = False
        self.lock = threading.Lock()
        
    def start(self, update_interval: int = 5):
        if not self.running:
            self.running = True
            self.update_thread = threading.Thread(
                target=self._update_loop,
                args=(update_interval,),
                daemon=True
            )
            self.update_thread.start()
            logger.info("ADSB service started")
    
    def stop(self):
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=5)
        logger.info("ADSB service stopped")
    
    def _update_loop(self, interval: int):
        while self.running:
            try:
                self._fetch_aircraft_data()
            except Exception as e:
                logger.error(f"Error updating ADSB data: {e}")
            time.sleep(interval)
    
    def _fetch_aircraft_data(self):
        try:
            response = requests.get(
                f"{self.dump1090_url}/data/aircraft.json",
                timeout=5
            )
            response.raise_for_status()
            
            data = response.json()
            
            with self.lock:
                self.aircraft_cache = {}
                
                for aircraft in data.get('aircraft', []):
                    if aircraft.get('seen', 999) < 30:
                        icao = aircraft.get('hex')
                        if icao:
                            self.aircraft_cache[icao] = {
                                'icao': icao,
                                'callsign': aircraft.get('flight', '').strip(),
                                'latitude': aircraft.get('lat'),
                                'longitude': aircraft.get('lon'),
                                'altitude': aircraft.get('alt_baro') or aircraft.get('alt_geom'),
                                'heading': aircraft.get('track'),
                                'speed': aircraft.get('gs'),
                                'vertical_rate': aircraft.get('baro_rate') or aircraft.get('geom_rate'),
                                'category': aircraft.get('category'),
                                'seen': aircraft.get('seen'),
                                'timestamp': datetime.utcnow().isoformat()
                            }
                
                self.last_update = datetime.utcnow()
                logger.debug(f"Updated ADSB data: {len(self.aircraft_cache)} aircraft")
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Could not fetch ADSB data from {self.dump1090_url}: {e}")
        except Exception as e:
            logger.error(f"Error processing ADSB data: {e}")
    
    def get_aircraft(self) -> List[Dict]:
        with self.lock:
            return list(self.aircraft_cache.values())
    
    def get_aircraft_by_icao(self, icao: str) -> Optional[Dict]:
        with self.lock:
            return self.aircraft_cache.get(icao)
    
    def get_aircraft_in_radius(self, lat: float, lon: float, radius_nm: float) -> List[Dict]:
        import math
        
        def haversine(lat1, lon1, lat2, lon2):
            R = 3440.1
            dLat = math.radians(lat2 - lat1)
            dLon = math.radians(lon2 - lon1)
            a = (math.sin(dLat/2) * math.sin(dLat/2) +
                 math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
                 math.sin(dLon/2) * math.sin(dLon/2))
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            return R * c
        
        aircraft_in_radius = []
        
        with self.lock:
            for aircraft in self.aircraft_cache.values():
                ac_lat = aircraft.get('latitude')
                ac_lon = aircraft.get('longitude')
                
                if ac_lat is not None and ac_lon is not None:
                    distance = haversine(lat, lon, ac_lat, ac_lon)
                    if distance <= radius_nm:
                        aircraft['distance'] = round(distance, 1)
                        aircraft_in_radius.append(aircraft)
        
        return sorted(aircraft_in_radius, key=lambda x: x.get('distance', 999))

# Initialize with config
from config.config import Config
adsb_service = ADSBService(Config.ADSB['piaware_url'])