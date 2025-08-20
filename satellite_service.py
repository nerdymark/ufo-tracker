#!/usr/bin/env python3
"""
UFO Tracker - Satellite Service
Standalone service for satellite tracking with status monitoring
"""

import logging
import sys
import time
import threading
from datetime import datetime, timezone
from flask import Flask, jsonify, request
import traceback

# Setup logging first
from config.config import Config

logging.basicConfig(
    level=getattr(logging, Config.LOGGING['level']),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Global satellite tracker and status
satellite_tracker = None
loading_status = {
    'loading': False,
    'progress': 0,
    'total_satellites': 0,
    'loaded_satellites': 0,
    'last_update': None,
    'next_update': None,
    'error': None,
    'status': 'stopped'
}

def initialize_satellite_tracker():
    """Initialize satellite tracker with progress tracking"""
    global satellite_tracker, loading_status
    
    try:
        logger.info("Initializing satellite tracker...")
        loading_status.update({
            'loading': True,
            'progress': 0,
            'status': 'initializing',
            'error': None
        })
        
        from services.satellite_tracker_optimized import OptimizedSatelliteTracker
        
        # Create tracker with custom progress callback
        satellite_tracker = OptimizedSatelliteTracker()
        
        # Monkey patch the load_satellites method to track progress
        original_load_satellites = satellite_tracker.load_satellites
        
        def load_satellites_with_progress(limit=None):
            loading_status['status'] = 'loading_satellites'
            loading_status['progress'] = 5  # Starting fetch
            
            # Fetch TLE data
            tle_data = satellite_tracker.fetch_tle_data()
            loading_status['total_satellites'] = len(tle_data)
            loading_status['progress'] = 10
            
            # Apply config limit
            config_limit = Config.SATELLITE.get('max_satellites', 1000)
            if limit:
                tle_data = tle_data[:min(limit, config_limit)]
            else:
                tle_data = tle_data[:config_limit]
            loading_status['total_satellites'] = len(tle_data)
            
            logger.info(f"Loading {len(tle_data)} satellites...")
            
            # Load satellites with progress tracking
            from sgp4.api import Satrec
            
            for i, sat_data in enumerate(tle_data):
                try:
                    # Create satellite record using SGP4
                    sat = Satrec.twoline2rv(sat_data['line1'], sat_data['line2'])
                    if sat:
                        satellite_tracker.satellites[sat_data['name']] = sat
                        # Store metadata including NORAD ID
                        satellite_tracker.satellite_metadata[sat_data['name']] = {
                            'norad_id': sat_data.get('norad_id'),
                            'loaded_at': datetime.now().isoformat()
                        }
                        loading_status['loaded_satellites'] = i + 1
                        
                        # Update progress (10% for fetch, 80% for loading, 10% for finalization)
                        progress = 10 + int((i + 1) / len(tle_data) * 80)
                        loading_status['progress'] = min(progress, 90)
                        
                        # Log every 100 satellites
                        if (i + 1) % 100 == 0:
                            logger.info(f"Loaded {i + 1} potentially visible satellites")
                            
                except Exception as e:
                    logger.warning(f"Failed to load satellite {sat_data['name']}: {e}")
                    continue
            
            loading_status['progress'] = 95
            
            # Filter and cache visible satellites with debugging
            logger.info("Starting cache refresh with debugging")
            try:
                satellite_tracker.refresh_cache()
                
            except Exception as e:
                logger.error(f"Cache refresh failed: {e}")
                loading_status.update({
                    'loading': False,
                    'progress': 95,
                    'status': 'error',
                    'error': str(e)
                })
                return
            
            loading_status.update({
                'loading': False,
                'progress': 100,
                'status': 'ready',
                'last_update': datetime.now(timezone.utc).isoformat(),
                'next_update': (datetime.now(timezone.utc).timestamp() + 
                              Config.SATELLITE.get('refresh_interval', 3600))
            })
            
            logger.info(f"Satellite tracker ready with {len(satellite_tracker.satellites)} satellites")
        
        # Replace the method
        satellite_tracker.load_satellites = load_satellites_with_progress
        
        # Start the tracker
        satellite_tracker.start()
        
        return satellite_tracker
        
    except Exception as e:
        logger.error(f"Failed to initialize satellite tracker: {e}")
        loading_status.update({
            'loading': False,
            'status': 'error',
            'error': str(e)
        })
        traceback.print_exc()
        return None

@app.route('/status')
def get_status():
    """Get satellite service status"""
    try:
        status_data = loading_status.copy()
        
        if satellite_tracker and hasattr(satellite_tracker, 'get_current_satellites'):
            try:
                visible = satellite_tracker.get_current_satellites()
                status_data['visible_count'] = len(visible)
                status_data['visible_satellites'] = [sat['name'] for sat in visible[:10]]  # First 10 names
            except Exception as e:
                logger.warning(f"Error getting visible satellites: {e}")
                status_data['visible_count'] = 0
                status_data['visible_satellites'] = []
        else:
            status_data['visible_count'] = 0
            status_data['visible_satellites'] = []
        
        return jsonify(status_data)
        
    except Exception as e:
        logger.error(f"Error in status endpoint: {e}")
        return jsonify({
            'loading': False,
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/satellites')
def get_satellites():
    """Get currently visible satellites"""
    try:
        if not satellite_tracker:
            return jsonify({
                'error': 'Satellite tracker not initialized',
                'satellites': []
            }), 503
        
        if loading_status['loading']:
            return jsonify({
                'error': 'Still loading satellites',
                'progress': loading_status['progress'],
                'satellites': []
            }), 503
        
        visible = satellite_tracker.get_current_satellites()
        
        satellites_data = []
        for sat in visible:
            # Use range_km for distance and convert to miles (1 km = 0.621371 miles)
            distance_km = sat.get('range_km', sat.get('distance', 0))
            distance_miles = round(distance_km * 0.621371, 1) if distance_km else 0
            
            # Get velocity in mph (already calculated in satellite tracker)
            velocity_mph = sat.get('velocity_mph', 0)
            
            satellites_data.append({
                'name': sat.get('name', 'Unknown'),
                'azimuth': sat.get('azimuth', 0),
                'elevation': sat.get('elevation', 0),
                'distance': distance_miles,  # Distance in miles
                'velocity': velocity_mph,  # Velocity in mph
                'norad_id': sat.get('norad_id'),  # NORAD catalog number for links
                'path': sat.get('path', [])  # Include trajectory path for frontend display
            })
        
        return jsonify({
            'satellites': satellites_data,
            'count': len(satellites_data),
            'last_update': loading_status.get('last_update')
        })
        
    except Exception as e:
        logger.error(f"Error getting satellites: {e}")
        return jsonify({
            'error': str(e),
            'satellites': []
        }), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'satellite-tracker',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

def start_satellite_tracker_async():
    """Start satellite tracker in background thread"""
    try:
        initialize_satellite_tracker()
    except Exception as e:
        logger.error(f"Error starting satellite tracker: {e}")
        loading_status.update({
            'loading': False,
            'status': 'error',
            'error': str(e)
        })

if __name__ == '__main__':
    logger.info("Starting UFO Tracker Satellite Service...")
    
    try:
        # Start satellite tracker in background
        tracker_thread = threading.Thread(target=start_satellite_tracker_async, daemon=True)
        tracker_thread.start()
        
        # Start Flask app on port 5003
        logger.info("Starting satellite service on port 5003...")
        app.run(
            host='0.0.0.0',
            port=5003,
            debug=False,
            threaded=True,
            processes=1
        )
        
    except KeyboardInterrupt:
        logger.info("Satellite service stopped by user")
    except Exception as e:
        logger.error(f"Satellite service error: {e}")
        traceback.print_exc()