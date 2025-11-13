#!/usr/bin/env python3
"""
UFO Tracker - API Service
Lightweight service for API endpoints and web interface (no camera streaming)
"""

import logging
import os
import sys
import time
import threading
import requests
from datetime import datetime
from flask import Flask, render_template, jsonify, request, Response, url_for, send_from_directory, redirect, send_file

# Setup logging first
from config.config import Config
from services.color_generator import color_generator

logging.basicConfig(
    level=getattr(logging, Config.LOGGING['level']),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import trajectory services
try:
    from services.compass_service import compass_service
    from services.adsb_service import adsb_service
    from services.trajectory_projector import trajectory_projector
    from services.mpu9250_sensor import MPU9250Sensor
    logger.info("Successfully imported trajectory and sensor services")
except ImportError as e:
    logger.warning(f"Could not import trajectory/sensor services: {e}")
    compass_service = None
    adsb_service = None
    trajectory_projector = None
    MPU9250Sensor = None

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY

# Global objects
pan_tilt = None
adsb_tracker = None
motion_sensor = None
mpu9250_sensor = None
feature_tracker = None
resource_cleanup_thread = None
cleanup_running = True

# Satellite service configuration
SATELLITE_SERVICE_URL = 'http://localhost:5003'

def initialize_pan_tilt():
    """Initialize pan-tilt controller"""
    global pan_tilt
    
    if Config.PAN_TILT['enabled']:
        try:
            from hardware.pan_tilt import PanTiltController
            pan_tilt = PanTiltController()
            logger.info("Pan-tilt controller initialized")
        except Exception as e:
            logger.error(f"Failed to initialize pan-tilt controller: {e}")
            pan_tilt = None
    else:
        logger.info("Pan-tilt controller disabled in config")

def initialize_adsb_tracker():
    """Initialize ADSB flight tracker"""
    global adsb_tracker
    
    if Config.ADSB['enabled']:
        try:
            from services.adsb_tracker import ADSBTracker
            adsb_tracker = ADSBTracker()
            adsb_tracker.start()
            logger.info("ADSB flight tracker initialized and started")
        except Exception as e:
            logger.error(f"Failed to initialize ADSB tracker: {e}")
            adsb_tracker = None
    else:
        logger.info("ADSB flight tracker disabled in config")

def get_satellite_service_status():
    """Get status from satellite service"""
    try:
        response = requests.get(f"{SATELLITE_SERVICE_URL}/status", timeout=5)
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        logger.warning(f"Could not reach satellite service: {e}")
        return None

def get_satellites_from_service():
    """Get satellites from satellite service"""
    try:
        response = requests.get(f"{SATELLITE_SERVICE_URL}/satellites", timeout=5)
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        logger.warning(f"Could not get satellites from service: {e}")
        return None

def initialize_motion_sensor():
    """Initialize MPU9250 motion and compass sensor"""
    global motion_sensor, mpu9250_sensor
    
    if Config.MOTION_SENSOR['enabled']:
        try:
            # Initialize MPU9250 sensor
            if MPU9250Sensor:
                mpu9250_sensor = MPU9250Sensor()
                if mpu9250_sensor.start():
                    motion_sensor = mpu9250_sensor  # Use MPU9250 as motion sensor
                    logger.info("MPU9250 motion and compass sensor initialized and started")
                else:
                    logger.warning("MPU9250 sensor failed to start")
                    mpu9250_sensor = None
                    motion_sensor = None
            else:
                logger.warning("MPU9250Sensor class not available")
                mpu9250_sensor = None
                motion_sensor = None
        except Exception as e:
            logger.error(f"Failed to initialize MPU9250 sensor: {e}")
            motion_sensor = None
            mpu9250_sensor = None
    else:
        logger.info("Motion sensor disabled in config")

def initialize_feature_tracker():
    """Initialize OpenCV feature tracker"""
    global feature_tracker
    
    try:
        from services.feature_tracker import initialize_feature_tracker
        feature_tracker = initialize_feature_tracker(Config)
        logger.info("Feature tracker initialized")
    except Exception as e:
        logger.error(f"Failed to initialize feature tracker: {e}")
        feature_tracker = None

def get_nearby_flights_for_annotation():
    """Get nearby flights for image annotation"""
    if not adsb_tracker or not Config.ADSB['enabled']:
        return []
    
    try:
        flights = adsb_tracker.get_current_flights()
        # Return flight info formatted for annotation
        flight_info = []
        for flight in flights:
            callsign = flight['flight'] if flight['flight'] != 'N/A' else f"Aircraft {flight['hex'][:6]}"
            altitude = flight['altitude'] if flight['altitude'] else 0
            distance = flight['distance_miles']
            bearing = flight['bearing_degrees'] if flight['bearing_degrees'] else 0
            
            flight_info.append({
                'callsign': callsign,
                'altitude_ft': int(altitude),
                'distance_miles': round(distance, 1),
                'bearing_deg': round(bearing),
                'hex': flight['hex']
            })
        
        return flight_info[:10]  # Limit to 10 flights to avoid cluttering
    except Exception as e:
        logger.error(f"Error getting flights for annotation: {e}")
        return []

def get_overhead_satellites_for_annotation():
    """Get overhead satellites for image annotation"""
    if not satellite_tracker or not Config.SATELLITE['enabled']:
        return []
    
    try:
        satellites = satellite_tracker.get_current_satellites()
        # Return satellite info formatted for annotation
        satellite_info = []
        for sat in satellites:
            name = sat['name']
            # Truncate long satellite names for display
            display_name = name if len(name) <= 20 else name[:17] + "..."
            
            satellite_info.append({
                'name': display_name,
                'full_name': name,
                'altitude_km': sat['altitude_km'],
                'elevation_deg': sat['elevation'],
                'azimuth_deg': sat['azimuth'],
                'range_km': sat['range_km'],
                'category': sat['category'],
                'velocity_kmh': sat['velocity_kmh']
            })
        
        return satellite_info[:8]  # Limit to 8 satellites to avoid cluttering
    except Exception as e:
        logger.error(f"Error getting satellites for annotation: {e}")
        return []

def get_motion_data_for_annotation():
    """Get motion sensor data for image annotation"""
    if not motion_sensor or not Config.MOTION_SENSOR['enabled']:
        return None
    
    try:
        data = motion_sensor.get_current_data()
        summary = motion_sensor.get_motion_summary()
        
        if not data or not data.get('timestamp'):
            return None
        
        return {
            'acceleration': data['acceleration'],
            'orientation': data['orientation'],
            'temperature': data['temperature'],
            'motion_detected': data['motion_detected'],
            'vibration_level': data['vibration_level'],
            'tilt_angle': data['tilt_angle'],
            'stability_score': summary['stability_score'],
            'calibrated': data['calibrated']
        }
    except Exception as e:
        logger.error(f"Error getting motion data for annotation: {e}")
        return None

def check_camera_active(camera_type):
    """Check if a camera service is active by trying to connect to it"""
    try:
        import requests
        # Try to get camera status from camera service
        response = requests.get(f'http://localhost:5001/{camera_type}_status', timeout=1)
        return response.status_code == 200
    except:
        # If we can't connect, assume camera is inactive
        return False

def get_local_ip():
    """Get the system's local IP address"""
    import socket
    
    try:
        # Get hostname IP
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        
        # If that returns localhost, try a different method
        if local_ip.startswith('127.'):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(('8.8.8.8', 80))
                local_ip = s.getsockname()[0]
            except:
                local_ip = '127.0.0.1'
            finally:
                s.close()
        
        return local_ip
    except Exception as e:
        logger.error(f"Error getting local IP: {e}")
        return '127.0.0.1'

def cleanup_resources():
    """Cleanup resources periodically"""
    global cleanup_running
    
    while cleanup_running:
        try:
            # Basic cleanup every 30 seconds
            time.sleep(30)
        except Exception as e:
            logger.error(f"Error in resource cleanup: {e}")

# Web interface routes
@app.route('/')
def dashboard():
    """Main dashboard"""
    return render_template('unified_dashboard.html', server_ip=get_local_ip())

@app.route('/viewer')
def viewer():
    """Camera viewer page"""
    return render_template('viewer.html')

@app.route('/frame_viewer')
def frame_viewer():
    """Frame viewer page"""
    return render_template('frame_viewer.html')

@app.route('/camera_controls')
def camera_controls():
    """Camera controls page"""
    return render_template('camera_controls.html')

@app.route('/stacking')
def stacking():
    """Image stacking page"""
    return render_template('stacking.html')

@app.route('/test_trajectory')
def test_trajectory():
    """Trajectory overlay test page"""
    try:
        with open('/home/mark/ufo-tracker/test_trajectory_overlay.html', 'r') as f:
            return f.read()
    except FileNotFoundError:
        return "Test page not found", 404

# API endpoints
@app.route('/api/test')
def api_test():
    """Simple test API endpoint"""
    logger.info("TEST API CALLED - This should be fast")
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "service": "api-only"
    })

@app.route('/api/system_status')
def system_status():
    """Get system status"""
    try:
        import shutil
        
        # Get disk usage
        disk_usage = shutil.disk_usage('/')
        
        status = {
            'timestamp': datetime.now().isoformat(),
            'service': 'api-only',
            'pan_tilt': {
                'enabled': Config.PAN_TILT['enabled'],
                'connected': pan_tilt.is_connected() if pan_tilt else False
            },
            'cameras': {
                'ir': {
                    'enabled': Config.CAMERA_SETTINGS['ir_camera']['enabled'],
                    'active': check_camera_active('ir')
                },
                'hq': {
                    'enabled': Config.CAMERA_SETTINGS['hq_camera']['enabled'],
                    'active': check_camera_active('hq')
                },
                'streaming_service': 'http://localhost:5001'
            },
            'storage': {
                'total': disk_usage.total,
                'used': disk_usage.used,
                'free': disk_usage.free,
                'percent': round((disk_usage.used / disk_usage.total) * 100, 1)
            }
        }
        
        if pan_tilt and pan_tilt.is_connected():
            status['pan_tilt'].update(pan_tilt.get_status())
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/pan_tilt', methods=['GET', 'POST'])
def pan_tilt_control():
    """Pan-tilt control API endpoint"""
    if not pan_tilt:
        return jsonify({'error': 'Pan-tilt controller not available'}), 503
    
    try:
        if request.method == 'GET':
            # Get status
            status = pan_tilt.get_status()
            return jsonify(status)
        
        elif request.method == 'POST':
            # Control commands
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No JSON data provided'}), 400
            
            action = data.get('action')
            if not action:
                return jsonify({'error': 'No action specified'}), 400
            
            logger.info(f"Pan-tilt action: {action}")
            
            if action == 'move_to':
                pan_angle = data.get('pan', 0.0)
                tilt_angle = data.get('tilt', 0.0)
                
                if pan_tilt.move_to(pan_angle, tilt_angle):
                    return jsonify({
                        'success': True,
                        'message': f'Moving to pan={pan_angle}°, tilt={tilt_angle}°'
                    })
                else:
                    return jsonify({'error': 'Failed to start movement'}), 500
                    
            elif action == 'move_relative':
                pan_steps = data.get('pan_steps', 0)
                tilt_steps = data.get('tilt_steps', 0)
                
                if pan_tilt.move_relative(pan_steps, tilt_steps):
                    return jsonify({
                        'success': True,
                        'message': f'Moving relative pan={pan_steps} steps, tilt={tilt_steps} steps'
                    })
                else:
                    return jsonify({'error': 'Failed to start relative movement'}), 500
            
            elif action == 'home':
                if pan_tilt.home():
                    return jsonify({
                        'success': True,
                        'message': 'Homing to center position'
                    })
                else:
                    return jsonify({'error': 'Failed to home mechanism'}), 500
            
            elif action == 'calibrate':
                axis = data.get('axis')  # 'pan' or 'tilt'
                limit_type = data.get('limit_type')  # 'min' or 'max'
                
                if not axis or not limit_type:
                    return jsonify({'error': 'Missing axis or limit_type parameter'}), 400
                
                if pan_tilt.calibrate_limits(axis, limit_type):
                    return jsonify({
                        'success': True,
                        'message': f'Calibrated {axis} {limit_type} limit'
                    })
                else:
                    return jsonify({'error': 'Failed to calibrate limit'}), 500
            
            elif action == 'set_speed':
                speed = data.get('speed', 100)
                pan_tilt.set_speed(speed)
                return jsonify({
                    'success': True,
                    'message': f'Speed set to {speed}'
                })
            
            elif action == 'enable_motors':
                logger.info("Starting enable_motors action")
                result = pan_tilt.enable_motors()
                logger.info(f"Enable motors result: {result}")
                if result:
                    return jsonify({
                        'success': True,
                        'message': 'Motors enabled (holding torque on)',
                        'motors_enabled': True
                    })
                else:
                    return jsonify({'error': 'Failed to enable motors'}), 500
            
            elif action == 'disable_motors':
                if pan_tilt.disable_motors():
                    return jsonify({
                        'success': True,
                        'message': 'Motors disabled (holding torque off)',
                        'motors_enabled': False
                    })
                else:
                    return jsonify({'error': 'Failed to disable motors'}), 500
            
            elif action == 'start_keepalive':
                if pan_tilt.start_keepalive():
                    return jsonify({
                        'success': True,
                        'message': 'Keepalive started - motors will stay powered during long exposures'
                    })
                else:
                    return jsonify({'error': 'Failed to start keepalive'}), 500
            
            elif action == 'stop_keepalive':
                pan_tilt.stop_keepalive()
                return jsonify({
                    'success': True,
                    'message': 'Keepalive stopped'
                })
            
            elif action == 'set_keepalive_interval':
                interval = data.get('interval', 5.0)
                pan_tilt.set_keepalive_interval(interval)
                return jsonify({
                    'success': True,
                    'message': f'Keepalive interval set to {interval} seconds'
                })
            
            else:
                return jsonify({'error': f'Unknown action: {action}'}), 400
    
    except Exception as e:
        logger.error(f"Error in pan_tilt_control: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/pan_tilt/motors', methods=['POST'])
def pan_tilt_motors():
    """Motor enable/disable endpoint"""
    if not pan_tilt:
        return jsonify({"error": "Pan-tilt controller not available"}), 503
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        enabled = data.get('enabled', True)
        
        if enabled:
            result = pan_tilt.enable_motors()
            if result:
                return jsonify({
                    "success": True,
                    "message": "Motors enabled",
                    "motors_enabled": True
                })
            else:
                return jsonify({"success": False, "error": "Failed to enable motors"}), 500
        else:
            result = pan_tilt.disable_motors()
            if result:
                return jsonify({
                    "success": True,
                    "message": "Motors disabled", 
                    "motors_enabled": False
                })
            else:
                return jsonify({"success": False, "error": "Failed to disable motors"}), 500
                
    except Exception as e:
        logger.error(f"Error in pan_tilt_motors: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/motors/move_relative', methods=['POST'])
def motors_move_relative():
    """Move motors relative to current position (for feature tracking)"""
    if not pan_tilt:
        return jsonify({"error": "Pan-tilt controller not available"}), 503
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        pan_delta = data.get('pan_delta', 0.0)  # degrees
        tilt_delta = data.get('tilt_delta', 0.0)  # degrees
        
        # Convert degrees to steps (assuming 1.8 degrees per step)
        steps_per_degree = 1.0 / 1.8
        pan_steps = int(pan_delta * steps_per_degree)
        tilt_steps = int(tilt_delta * steps_per_degree)
        
        if pan_tilt.move_relative(pan_steps, tilt_steps):
            return jsonify({
                "success": True,
                "message": f"Moving relative pan={pan_delta:.2f}°, tilt={tilt_delta:.2f}°",
                "pan_steps": pan_steps,
                "tilt_steps": tilt_steps
            })
        else:
            return jsonify({"success": False, "error": "Failed to start relative movement"}), 500
            
    except Exception as e:
        logger.error(f"Error in motors_move_relative: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/pan_tilt/keepalive', methods=['POST'])
def pan_tilt_keepalive():
    """Keepalive enable/disable endpoint"""
    if not pan_tilt:
        return jsonify({"error": "Pan-tilt controller not available"}), 503
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        enabled = data.get('enabled', True)
        
        if enabled:
            result = pan_tilt.start_keepalive()
            if result:
                return jsonify({
                    "success": True,
                    "message": "Keepalive enabled",
                    "keepalive_enabled": True
                })
            else:
                return jsonify({"success": False, "error": "Failed to enable keepalive"}), 500
        else:
            pan_tilt.stop_keepalive()
            return jsonify({
                "success": True,
                "message": "Keepalive disabled",
                "keepalive_enabled": False
            })
                
    except Exception as e:
        logger.error(f"Error in pan_tilt_keepalive: {e}")
        return jsonify({"error": str(e)}), 500

# ============= NEW PAN-TILT WASD CONTROL ENDPOINTS =============

@app.route('/api/pantilt/status')
def get_pantilt_status():
    """Get pan-tilt controller status"""
    if not pan_tilt:
        return jsonify({"error": "Pan-tilt controller not available"}), 503
    
    try:
        status = pan_tilt.get_status()
        return jsonify({
            "success": True,
            "status": status
        })
    except Exception as e:
        logger.error(f"Error getting pan-tilt status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/pantilt/move_relative', methods=['POST'])
def move_pantilt_relative():
    """Move pan-tilt relative to current position (WASD control)"""
    if not pan_tilt:
        return jsonify({"error": "Pan-tilt controller not available"}), 503
    
    try:
        data = request.json
        pan_steps = data.get('pan_steps', 0)
        tilt_steps = data.get('tilt_steps', 0)
        fine_step = data.get('fine_step', False)
        
        # Apply fine step modifier (10% of normal step)
        if fine_step:
            pan_steps = int(pan_steps * 0.1)
            tilt_steps = int(tilt_steps * 0.1)
        
        # Ensure motors are enabled before movement
        if not pan_tilt.get_motors_enabled():
            pan_tilt.enable_motors()
        
        success = pan_tilt.move_relative(pan_steps, tilt_steps)
        
        return jsonify({
            "success": success,
            "message": f"Relative movement pan_steps={pan_steps}, tilt_steps={tilt_steps} {'started' if success else 'failed'}"
        })
    except Exception as e:
        logger.error(f"Error moving pan-tilt relative: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/pantilt/enable_motors', methods=['POST'])
def enable_pantilt_motors():
    """Enable pan-tilt stepper motors"""
    if not pan_tilt:
        return jsonify({"error": "Pan-tilt controller not available"}), 503
    
    try:
        success = pan_tilt.enable_motors()
        return jsonify({
            "success": success,
            "message": "Motors enabled" if success else "Failed to enable motors"
        })
    except Exception as e:
        logger.error(f"Error enabling pan-tilt motors: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/pantilt/disable_motors', methods=['POST'])
def disable_pantilt_motors():
    """Disable pan-tilt stepper motors"""
    if not pan_tilt:
        return jsonify({"error": "Pan-tilt controller not available"}), 503
    
    try:
        success = pan_tilt.disable_motors()
        return jsonify({
            "success": success,
            "message": "Motors disabled" if success else "Failed to disable motors"
        })
    except Exception as e:
        logger.error(f"Error disabling pan-tilt motors: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/pantilt/start_keepalive', methods=['POST'])
def start_pantilt_keepalive():
    """Start pan-tilt keepalive pulses during long exposures"""
    if not pan_tilt:
        return jsonify({"error": "Pan-tilt controller not available"}), 503
    
    try:
        success = pan_tilt.start_keepalive()
        return jsonify({
            "success": success,
            "message": "Keepalive started" if success else "Failed to start keepalive"
        })
    except Exception as e:
        logger.error(f"Error starting pan-tilt keepalive: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/pantilt/stop_keepalive', methods=['POST'])
def stop_pantilt_keepalive():
    """Stop pan-tilt keepalive pulses"""
    if not pan_tilt:
        return jsonify({"error": "Pan-tilt controller not available"}), 503
    
    try:
        pan_tilt.stop_keepalive()
        return jsonify({
            "success": True,
            "message": "Keepalive stopped"
        })
    except Exception as e:
        logger.error(f"Error stopping pan-tilt keepalive: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/pantilt/home', methods=['POST'])
def home_pantilt():
    """Home the pan-tilt mechanism to center position"""
    if not pan_tilt:
        return jsonify({"error": "Pan-tilt controller not available"}), 503
    
    try:
        # Ensure motors are enabled before movement
        if not pan_tilt.get_motors_enabled():
            pan_tilt.enable_motors()
        
        success = pan_tilt.home()
        return jsonify({
            "success": success,
            "message": "Homing completed" if success else "Homing failed"
        })
    except Exception as e:
        logger.error(f"Error homing pan-tilt: {e}")
        return jsonify({"error": str(e)}), 500

# ============= END NEW PAN-TILT ENDPOINTS =============

@app.route('/api/camera_settings/<camera>', methods=['GET', 'POST'])
def camera_settings_api(camera):
    """Camera settings API - proxies to camera service"""
    import requests
    
    camera_service_url = 'http://localhost:5001'
    
    try:
        if request.method == 'GET':
            # Proxy GET request to camera service
            response = requests.get(f'{camera_service_url}/api/camera_settings/{camera}', timeout=5)
            return jsonify(response.json()), response.status_code
            
        elif request.method == 'POST':
            # Proxy POST request to camera service
            data = request.get_json()
            response = requests.post(
                f'{camera_service_url}/api/camera_settings/{camera}',
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            return jsonify(response.json()), response.status_code
    
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': 'Camera service timeout - service may be busy'
        }), 504
    except requests.exceptions.ConnectionError:
        return jsonify({
            'success': False,
            'error': 'Cannot connect to camera service on port 5001'
        }), 503
    except Exception as e:
        logger.error(f"Error proxying camera settings for {camera}: {e}")
        return jsonify({
            'success': False,
            'error': f'Proxy error: {str(e)}'
        }), 500

@app.route('/api/camera_dynamic_exposure/<camera>', methods=['POST'])
def camera_dynamic_exposure(camera):
    """Camera dynamic exposure API - proxies to camera service"""
    import requests
    
    camera_service_url = 'http://localhost:5001'
    
    try:
        response = requests.post(f'{camera_service_url}/api/camera_dynamic_exposure/{camera}', timeout=10)
        return jsonify(response.json()), response.status_code
    
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': 'Camera service timeout - dynamic exposure analysis may take time'
        }), 504
    except requests.exceptions.ConnectionError:
        return jsonify({
            'success': False,
            'error': 'Cannot connect to camera service on port 5001'
        }), 503
    except Exception as e:
        logger.error(f"Error proxying dynamic exposure for {camera}: {e}")
        return jsonify({
            'success': False,
            'error': f'Proxy error: {str(e)}'
        }), 500

@app.route('/api/camera_day_mode/<camera>', methods=['POST'])
def camera_day_mode(camera):
    """Camera day mode API - proxies to camera service"""
    import requests
    
    camera_service_url = 'http://localhost:5001'
    
    try:
        response = requests.post(f'{camera_service_url}/api/camera_day_mode/{camera}', timeout=5)
        return jsonify(response.json()), response.status_code
    
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': 'Camera service timeout'
        }), 504
    except requests.exceptions.ConnectionError:
        return jsonify({
            'success': False,
            'error': 'Cannot connect to camera service on port 5001'
        }), 503
    except Exception as e:
        logger.error(f"Error proxying day mode for {camera}: {e}")
        return jsonify({
            'success': False,
            'error': f'Proxy error: {str(e)}'
        }), 500

@app.route('/api/camera_night_mode/<camera>', methods=['POST'])
def camera_night_mode(camera):
    """Camera night mode API - proxies to camera service"""
    import requests
    
    camera_service_url = 'http://localhost:5001'
    
    try:
        response = requests.post(f'{camera_service_url}/api/camera_night_mode/{camera}', timeout=5)
        return jsonify(response.json()), response.status_code
    
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': 'Camera service timeout'
        }), 504
    except requests.exceptions.ConnectionError:
        return jsonify({
            'success': False,
            'error': 'Cannot connect to camera service on port 5001'
        }), 503
    except Exception as e:
        logger.error(f"Error proxying night mode for {camera}: {e}")
        return jsonify({
            'success': False,
            'error': f'Proxy error: {str(e)}'
        }), 500

@app.route('/api/camera_restart_streaming/<camera>', methods=['POST'])
def camera_restart_streaming(camera):
    """Camera restart streaming API - proxies to camera service"""
    import requests
    
    camera_service_url = 'http://localhost:5001'
    
    try:
        response = requests.post(f'{camera_service_url}/api/camera_restart_streaming/{camera}', timeout=10)
        return jsonify(response.json()), response.status_code
    
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': 'Camera service timeout - streaming restart may take time'
        }), 504
    except requests.exceptions.ConnectionError:
        return jsonify({
            'success': False,
            'error': 'Cannot connect to camera service on port 5001'
        }), 503
    except Exception as e:
        logger.error(f"Error proxying restart streaming for {camera}: {e}")
        return jsonify({
            'success': False,
            'error': f'Proxy error: {str(e)}'
        }), 500

# Static file serving
@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files"""
    return send_from_directory('static', filename)

# Health check
@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'service': 'api-only',
        'timestamp': datetime.now().isoformat(),
        'pan_tilt_available': pan_tilt is not None,
        'camera_service': 'http://localhost:5001'
    })

# Auto-tracker endpoints (stub implementation for client-side tracking)
@app.route('/api/auto_tracker/status')
def auto_tracker_status():
    """Get auto tracker status - client-side implementation"""
    return jsonify({
        "enabled": False,
        "tracking_active": False,
        "objects_tracked": 0,
        "motion_detected": False,
        "message": "Client-side tracking only"
    })

@app.route('/api/auto_tracker/start', methods=['POST'])
def auto_tracker_start():
    """Start the auto tracker - client-side implementation"""
    # Since tracking is client-side, just return success
    return jsonify({
        "success": True,
        "message": "Client-side auto-tracking enabled",
        "mode": "client-side"
    })

@app.route('/api/auto_tracker/stop', methods=['POST'])
def auto_tracker_stop():
    """Stop the auto tracker - client-side implementation"""
    return jsonify({
        "success": True,
        "message": "Client-side auto-tracking disabled"
    })

@app.route('/api/auto_tracker/clear_history', methods=['POST'])
def auto_tracker_clear_history():
    """Clear tracking history - client-side implementation"""
    return jsonify({
        "success": True,
        "message": "Tracking history cleared (client-side)"
    })

@app.route('/api/auto_tracker/export')
def auto_tracker_export():
    """Export tracking data - client-side implementation"""
    # Return empty tracking data
    tracking_data = {
        "timestamp": datetime.now().isoformat(),
        "mode": "client-side",
        "tracks": [],
        "message": "No server-side tracking data available"
    }
    return jsonify(tracking_data)

# ============================================================================
# Compass and Trajectory API Routes
# ============================================================================

@app.route('/api/compass/calibrate', methods=['POST'])
def calibrate_compass():
    """Set north reference for compass calibration"""
    try:
        if compass_service is None:
            return jsonify({'error': 'Compass service not available'}), 503
        
        data = request.get_json()
        current_heading = data.get('current_heading', 0)
        
        compass_service.set_north_reference(current_heading)
        
        return jsonify({
            'success': True,
            'message': 'Compass calibrated to north',
            'calibration_offset': compass_service.calibration_offset
        })
        
    except Exception as e:
        logger.error(f"Error calibrating compass: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/compass/status')
def get_compass_status():
    """Get current compass status and orientation"""
    try:
        if compass_service is None:
            return jsonify({'error': 'Compass service not available'}), 503
        
        return jsonify(compass_service.get_orientation_data())
        
    except Exception as e:
        logger.error(f"Error getting compass status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/compass/update', methods=['POST'])
def update_compass():
    """Update compass readings"""
    try:
        if compass_service is None:
            return jsonify({'error': 'Compass service not available'}), 503
        
        data = request.get_json()
        heading = data.get('heading', 0)
        tilt_x = data.get('tilt_x', 0)
        tilt_y = data.get('tilt_y', 0)
        
        compass_service.update_heading(heading, tilt_x, tilt_y)
        
        return jsonify({
            'success': True,
            'true_heading': compass_service.get_true_heading()
        })
        
    except Exception as e:
        logger.error(f"Error updating compass: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/satellites/visible')
def get_visible_satellites():
    """Get currently visible satellites with trajectory data"""
    try:
        # Try to get satellite data from the satellite service
        try:
            response = requests.get('http://localhost:5003/satellites', timeout=2)
            if response.ok:
                data = response.json()
                # Add unique colors to each satellite
                if 'satellites' in data:
                    for sat in data['satellites']:
                        # Use NORAD ID if available, otherwise use name
                        sat_id = sat.get('norad_id', sat.get('name', ''))
                        if sat_id:
                            sat['color'] = color_generator.generate_color(str(sat_id), 'satellite')
                return jsonify(data)
        except:
            pass
        
        # Fallback response if satellite service is not running
        return jsonify({
            'satellites': [],
            'count': 0,
            'error': 'Satellite service not available'
        })
        
    except Exception as e:
        logger.error(f"Error getting satellites: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/aircraft')
def get_aircraft():
    """Get currently tracked aircraft"""
    try:
        if adsb_service is None:
            return jsonify({
                'aircraft': [],
                'count': 0,
                'error': 'ADSB service not available'
            })
        
        # Start service if not running
        if not adsb_service.running:
            adsb_service.start()
        
        aircraft = adsb_service.get_aircraft()
        
        # Add unique colors to each aircraft
        for ac in aircraft:
            if 'icao' in ac:
                ac['color'] = color_generator.generate_color(ac['icao'], 'aircraft')
        
        return jsonify({
            'aircraft': aircraft,
            'count': len(aircraft),
            'last_update': adsb_service.last_update.isoformat() if adsb_service.last_update else None
        })
        
    except Exception as e:
        logger.error(f"Error getting aircraft: {e}")
        return jsonify({'error': str(e), 'aircraft': []}), 500

@app.route('/api/trajectories/project', methods=['POST'])
def project_trajectories():
    """Project satellite and aircraft trajectories onto camera view"""
    try:
        if trajectory_projector is None or compass_service is None:
            return jsonify({'error': 'Trajectory services not available'}), 503
        
        data = request.get_json()
        
        # Update projector settings
        fov_h = data.get('fov_horizontal', 180)
        fov_v = data.get('fov_vertical', 90)
        trajectory_projector.set_fov(fov_h, fov_v)
        
        # Get current compass orientation
        orientation = compass_service.get_orientation_data()
        trajectory_projector.set_camera_orientation(
            orientation['heading'],
            orientation['tilt_x'],
            orientation['tilt_y']
        )
        
        # Get objects to project
        satellites = data.get('satellites', [])
        aircraft = data.get('aircraft', [])
        
        screen_width = data.get('screen_width', 1920)
        screen_height = data.get('screen_height', 1080)
        
        projections = []
        
        # Project satellite trajectories
        for sat in satellites:
            trajectory = trajectory_projector.calculate_satellite_trajectory(sat)
            projected = trajectory_projector.project_trajectory(
                trajectory, screen_width, screen_height
            )
            if projected:
                projections.append({
                    'type': 'satellite',
                    'name': sat.get('name'),
                    'points': projected
                })
        
        # Project aircraft trajectories
        for ac in aircraft:
            trajectory = trajectory_projector.calculate_aircraft_trajectory(ac)
            projected = trajectory_projector.project_trajectory(
                trajectory, screen_width, screen_height
            )
            if projected:
                projections.append({
                    'type': 'aircraft',
                    'name': ac.get('callsign'),
                    'points': projected
                })
        
        return jsonify({
            'projections': projections,
            'compass_heading': orientation['heading'],
            'fov': {'horizontal': fov_h, 'vertical': fov_v}
        })
        
    except Exception as e:
        logger.error(f"Error projecting trajectories: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# Camera Auto-Tuning API Routes  
# ============================================================================

@app.route('/api/camera_auto_tune/<camera_type>', methods=['POST'])
def camera_auto_tune(camera_type):
    """Auto-tune camera settings using histogram analysis"""
    try:
        if camera_type not in ['ir', 'hq']:
            return jsonify({"success": False, "error": "Invalid camera type"}), 400
        
        # Get parameters from request
        data = request.get_json() if request.is_json else {}
        quick_mode = data.get('quick_mode', True)
        is_day = data.get('is_day', None)
        
        # Auto-detect day/night if not specified
        if is_day is None:
            import datetime
            current_hour = datetime.datetime.now().hour
            is_day = 6 <= current_hour <= 20
        
        logger.info(f"Auto-tuning {camera_type} camera (day={is_day}, quick={quick_mode})")
        
        # Use the remote auto-tuner
        from camera.auto_tuner import RemoteCameraAutoTuner
        tuner = RemoteCameraAutoTuner()
        
        # Run the tuning
        best_settings = tuner.auto_tune_camera_remote(camera_type, is_day=is_day, quick_mode=quick_mode)
        
        if best_settings:
            return jsonify({
                "success": True,
                "settings": {
                    "exposure_time": best_settings.exposure_time,
                    "gain": best_settings.gain,
                    "brightness": best_settings.brightness,
                    "contrast": best_settings.contrast,
                    "score": best_settings.score
                },
                "message": f"Auto-tuning complete ({'quick' if quick_mode else 'comprehensive'} mode)",
                "mode": "day" if is_day else "night"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Auto-tuning failed to find optimal settings"
            }), 500
        
    except Exception as e:
        logger.error(f"Camera auto-tune error for {camera_type}: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/camera_fine_tune/<camera_type>', methods=['POST'])
def camera_fine_tune(camera_type):
    """Fine-tune current camera settings"""
    try:
        if camera_type not in ['ir', 'hq']:
            return jsonify({"success": False, "error": "Invalid camera type"}), 400
        
        logger.info(f"Fine-tuning {camera_type} camera")
        
        # Use the remote auto-tuner for fine-tuning
        from camera.auto_tuner import RemoteCameraAutoTuner
        tuner = RemoteCameraAutoTuner()
        
        # Run fine-tuning
        improved_settings = tuner.fine_tune_settings_remote(camera_type)
        
        if improved_settings:
            return jsonify({
                "success": True,
                "settings": {
                    "exposure_time": improved_settings.exposure_time,
                    "gain": improved_settings.gain,
                    "brightness": improved_settings.brightness,
                    "contrast": improved_settings.contrast,
                    "score": improved_settings.score
                },
                "message": "Fine-tuning complete - settings optimized",
                "adjustments": "Fine-tuned adjustments applied based on histogram analysis"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Fine-tuning failed to improve settings"
            }), 500
        
    except Exception as e:
        logger.error(f"Camera fine-tune error for {camera_type}: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/camera_dynamic_mode/<camera_type>', methods=['POST'])
def camera_dynamic_mode(camera_type):
    """Dynamic camera tuning mode using enhanced histogram analysis"""
    try:
        if camera_type not in ['ir', 'hq']:
            return jsonify({"success": False, "error": "Invalid camera type"}), 400
        
        logger.info(f"Starting dynamic mode tuning for {camera_type} camera")
        
        # Auto-detect day/night
        import datetime
        current_hour = datetime.datetime.now().hour
        is_day = 6 <= current_hour <= 20
        
        # Use the remote auto-tuner with quick mode for dynamic adjustment
        from camera.auto_tuner import RemoteCameraAutoTuner
        tuner = RemoteCameraAutoTuner()
        
        # Run quick tuning for dynamic mode
        best_settings = tuner.auto_tune_camera_remote(camera_type, is_day=is_day, quick_mode=True)
        
        if best_settings:
            return jsonify({
                "success": True,
                "settings": {
                    "exposure_time": best_settings.exposure_time,
                    "gain": best_settings.gain,
                    "brightness": best_settings.brightness,
                    "contrast": best_settings.contrast,
                    "score": best_settings.score
                },
                "message": "Dynamic mode tuning complete",
                "mode": "day" if is_day else "night",
                "tuning_type": "dynamic"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Dynamic mode tuning failed"
            }), 500
        
    except Exception as e:
        logger.error(f"Camera dynamic mode error for {camera_type}: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/camera_quick_tune/<camera_type>', methods=['POST'])
def camera_quick_tune(camera_type):
    """Quick tune camera settings (alias for auto-tune with quick_mode=True)"""
    try:
        if camera_type not in ['ir', 'hq']:
            return jsonify({"success": False, "error": "Invalid camera type"}), 400
        
        logger.info(f"Quick tuning {camera_type} camera")
        
        # Auto-detect day/night
        import datetime
        current_hour = datetime.datetime.now().hour
        is_day = 6 <= current_hour <= 20
        
        # Use the remote auto-tuner in quick mode
        from camera.auto_tuner import RemoteCameraAutoTuner
        tuner = RemoteCameraAutoTuner()
        
        # Run quick tuning
        best_settings = tuner.auto_tune_camera_remote(camera_type, is_day=is_day, quick_mode=True)
        
        if best_settings:
            return jsonify({
                "success": True,
                "settings": {
                    "exposure_time": best_settings.exposure_time,
                    "gain": best_settings.gain,
                    "brightness": best_settings.brightness,
                    "contrast": best_settings.contrast,
                    "score": best_settings.score
                },
                "message": "Quick tuning complete",
                "mode": "day" if is_day else "night",
                "tuning_type": "quick"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Quick tuning failed"
            }), 500
        
    except Exception as e:
        logger.error(f"Camera quick tune error for {camera_type}: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ============================================================================
# Satellite Tracking API Routes
# ============================================================================

@app.route('/api/satellite/status')
def satellite_status():
    """Get satellite tracker status from satellite service"""
    try:
        status = get_satellite_service_status()
        if status:
            return jsonify(status)
        else:
            return jsonify({
                'loading': False,
                'status': 'service_unavailable',
                'enabled': Config.SATELLITE['enabled'],
                'error': 'Satellite service not available'
            }), 503
    except Exception as e:
        logger.error(f"Error getting satellite status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/satellite/overhead')
def satellite_overhead():
    """Get satellites currently overhead from satellite service"""
    try:
        data = get_satellites_from_service()
        if data and 'satellites' in data:
            return jsonify({
                'success': True,
                'satellites': data['satellites'],
                'count': data.get('count', len(data['satellites'])),
                'min_elevation': Config.SATELLITE['min_elevation'],
                'last_update': data.get('last_update')
            })
        else:
            return jsonify({
                'success': False,
                'satellites': [],
                'count': 0,
                'error': 'Satellite service not available or still loading'
            }), 503
    except Exception as e:
        logger.error(f"Error getting overhead satellites: {e}")
        return jsonify({
            'success': False,
            'satellites': [],
            'count': 0,
            'error': str(e)
        }), 500

@app.route('/api/satellite/refresh', methods=['POST'])
def satellite_refresh():
    """Refresh satellite TLE data - proxy to satellite service"""
    try:
        # For now, just return status as refresh is handled automatically by the service
        status = get_satellite_service_status()
        if status:
            return jsonify({
                'success': True,
                'message': 'Satellite service is running',
                'status': status
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Satellite service not available'
            }), 503
    except Exception as e:
        logger.error(f"Error refreshing satellite data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# Motion Sensor API Routes
# ============================================================================

@app.route('/api/motion/status')
def motion_status():
    """Get motion sensor status"""
    try:
        if motion_sensor:
            status = motion_sensor.get_status()
            return jsonify(status)
        else:
            return jsonify({
                'running': False,
                'enabled': Config.MOTION_SENSOR['enabled'],
                'hardware_available': False,
                'error': 'Motion sensor not initialized'
            }), 503
    except Exception as e:
        logger.error(f"Error getting motion sensor status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/motion/data')
def motion_data():
    """Get current motion sensor data"""
    try:
        if motion_sensor and motion_sensor.is_running():
            current_data = motion_sensor.get_current_data()
            motion_summary = motion_sensor.get_motion_summary()
            
            return jsonify({
                'success': True,
                'data': current_data,
                'summary': motion_summary,
                'timestamp': current_data.get('timestamp')
            })
        else:
            return jsonify({
                'success': False,
                'data': {},
                'summary': {},
                'error': 'Motion sensor not running'
            }), 503
    except Exception as e:
        logger.error(f"Error getting motion sensor data: {e}")
        return jsonify({
            'success': False,
            'data': {},
            'summary': {},
            'error': str(e)
        }), 500

@app.route('/api/motion/calibrate', methods=['POST'])
def motion_calibrate():
    """Calibrate motion sensor"""
    try:
        if motion_sensor:
            success = motion_sensor.recalibrate()
            if success:
                return jsonify({
                    'success': True,
                    'message': 'Motion sensor calibrated successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Calibration failed'
                }), 500
        else:
            return jsonify({
                'success': False,
                'error': 'Motion sensor not available'
            }), 503
    except Exception as e:
        logger.error(f"Error calibrating motion sensor: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sensor/compass')
def sensor_compass():
    """Get compass data specifically for trajectory overlay"""
    try:
        if motion_sensor and motion_sensor.is_running():
            current_data = motion_sensor.get_current_data()
            compass_data = current_data.get('compass', {})
            
            return jsonify({
                'success': True,
                'data': {
                    'true_heading': compass_data.get('true_heading', 0),
                    'magnetic_heading': compass_data.get('magnetic_heading', 0),
                    'calibrated': compass_data.get('calibrated', False),
                    'declination': compass_data.get('magnetic_declination', 0)
                }
            })
        else:
            return jsonify({
                'success': False,
                'data': {},
                'error': 'Motion sensor not running'
            }), 503
    except Exception as e:
        logger.error(f"Error getting compass data: {e}")
        return jsonify({
            'success': False,
            'data': {},
            'error': str(e)
        }), 500

@app.route('/api/sensor/mpu9250')
def sensor_mpu9250():
    """Get complete MPU9250 sensor data for trajectory overlay"""
    try:
        if motion_sensor and motion_sensor.is_running():
            current_data = motion_sensor.get_current_data()
            
            return jsonify({
                'success': True,
                'data': {
                    'compass': current_data.get('compass', {}),
                    'orientation': current_data.get('orientation', {}),
                    'acceleration': current_data.get('acceleration', {}),
                    'gyroscope': current_data.get('gyroscope', {}),
                    'magnetometer': current_data.get('magnetometer', {}),
                    'motion_detected': current_data.get('motion_detected', False),
                    'tilt_angle': current_data.get('tilt_angle', 0),
                    'timestamp': current_data.get('timestamp')
                }
            })
        else:
            return jsonify({
                'success': False,
                'data': {},
                'error': 'MPU9250 sensor not running'
            }), 503
    except Exception as e:
        logger.error(f"Error getting MPU9250 data: {e}")
        return jsonify({
            'success': False,
            'data': {},
            'error': str(e)
        }), 500

# ============================================================================
# Camera Capture API Routes
# ============================================================================

@app.route('/api/capture/<camera_type>', methods=['POST'])
def api_capture_frame(camera_type):
    """Capture a single frame from the specified camera via frame service"""
    try:
        import requests
        import cv2
        import numpy as np
        from datetime import datetime
        import os
        
        # Validate camera type
        if camera_type not in ['ir', 'hq']:
            return jsonify({
                'success': False,
                'error': 'Invalid camera type. Use "ir" or "hq"'
            }), 400
        
        # Get frame from the frame service
        try:
            response = requests.get(f'http://localhost:5002/{camera_type}_frame', timeout=5)
            if response.status_code != 200:
                return jsonify({
                    'success': False,
                    'error': f'{camera_type.upper()} camera not available'
                }), 503
            
            # Convert response content to image
            nparr = np.frombuffer(response.content, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is None:
                return jsonify({
                    'success': False,
                    'error': 'Failed to decode frame'
                }), 500
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get frame from frame service: {e}")
            return jsonify({
                'success': False,
                'error': 'Frame service not available'
            }), 503
        
        # Save to gallery/images directory from config
        gallery_dirs = Config.STORAGE.get('gallery_dirs', [])
        images_dir = None
        for dir_path, url_prefix in gallery_dirs:
            if 'images' in dir_path:
                images_dir = dir_path
                break
        
        save_path = images_dir or 'static/gallery/images'
        os.makedirs(save_path, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'{camera_type}_capture_{timestamp}.jpg'
        filepath = os.path.join(save_path, filename)
        
        # Add annotations with flight data
        from PIL import Image, ImageDraw, ImageFont
        
        # Convert OpenCV image to PIL
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(frame_rgb)
        draw = ImageDraw.Draw(pil_image)
        
        # Try to load fonts
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        except:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        
        # Add timestamp and camera info
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary_text = f"{timestamp_str} | {camera_type.upper()} Manual Capture"
        
        # Draw timestamp background
        bbox = draw.textbbox((0, 0), summary_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        draw.rectangle(
            [10, 10, 10 + text_width + 8, 10 + text_height + 8],
            fill=(0, 0, 0, 128),
            outline=(255, 255, 0)
        )
        
        draw.text((14, 14), summary_text, fill=(255, 255, 0), font=font)
        
        # Add nearby flights information
        info_y = 10 + text_height + 20
        nearby_flights = get_nearby_flights_for_annotation()
        if nearby_flights:
            # Add flight header
            flight_header = f"🛩️ Nearby Aircraft ({len(nearby_flights)} within {Config.ADSB['max_distance_miles']} mi):"
            draw.text((14, info_y), flight_header, fill=(135, 206, 235), font=small_font)  # Sky blue
            info_y += 16
            
            # Add individual flights
            for i, flight in enumerate(nearby_flights):
                flight_text = f"  {flight['callsign']}: {flight['distance_miles']}mi, {flight['altitude_ft']:,}ft, {flight['bearing_deg']}°"
                draw.text((14, info_y), flight_text, fill=(176, 224, 230), font=small_font)  # Light blue
                info_y += 14
                
                # Limit to prevent image overflow
                if i >= 7:  # Show max 8 flights to prevent clutter
                    remaining = len(nearby_flights) - (i + 1)
                    if remaining > 0:
                        draw.text((14, info_y), f"  ... and {remaining} more aircraft", fill=(176, 224, 230), font=small_font)
                    break
        else:
            # Note when no flights are detected
            no_flights_text = f"📡 No aircraft within {Config.ADSB['max_distance_miles']} miles"
            draw.text((14, info_y), no_flights_text, fill=(144, 238, 144), font=small_font)  # Light green
        
        # Add space before satellite section
        info_y += 20
        
        # Add overhead satellites information
        overhead_satellites = get_overhead_satellites_for_annotation()
        if overhead_satellites:
            # Add satellite header
            satellite_header = f"🛰️ Overhead Satellites ({len(overhead_satellites)} above {Config.SATELLITE['min_elevation']}°):"
            draw.text((14, info_y), satellite_header, fill=(255, 165, 0), font=small_font)  # Orange
            info_y += 16
            
            # Add individual satellites
            for i, sat in enumerate(overhead_satellites):
                sat_text = f"  {sat['name']}: {sat['elevation_deg']}° elev, {sat['altitude_km']}km alt, {sat['category']}"
                draw.text((14, info_y), sat_text, fill=(255, 215, 0), font=small_font)  # Gold
                info_y += 14
                
                # Limit to prevent image overflow
                if i >= 5:  # Show max 6 satellites to prevent clutter
                    remaining = len(overhead_satellites) - (i + 1)
                    if remaining > 0:
                        draw.text((14, info_y), f"  ... and {remaining} more satellites", fill=(255, 215, 0), font=small_font)
                    break
        else:
            # Note when no satellites are detected
            no_satellites_text = f"🛰️ No satellites above {Config.SATELLITE['min_elevation']}° elevation"
            draw.text((14, info_y), no_satellites_text, fill=(144, 238, 144), font=small_font)  # Light green
        
        # Add space before motion sensor section
        info_y += 20
        
        # Add motion sensor information
        motion_data = get_motion_data_for_annotation()
        if motion_data:
            # Add motion sensor header
            motion_header = f"📱 Motion Sensor ({'Calibrated' if motion_data['calibrated'] else 'Uncalibrated'})"
            draw.text((14, info_y), motion_header, fill=(255, 20, 147), font=small_font)  # Deep pink
            info_y += 16
            
            # Add orientation data
            orient = motion_data['orientation']
            orientation_text = f"  Orientation: P:{orient['pitch']:.1f}° R:{orient['roll']:.1f}° Y:{orient['yaw']:.1f}°"
            draw.text((14, info_y), orientation_text, fill=(255, 105, 180), font=small_font)  # Hot pink
            info_y += 14
            
            # Add motion status and stability
            stability = motion_data['stability_score']
            motion_status = "MOTION" if motion_data['motion_detected'] else "STABLE"
            motion_text = f"  Status: {motion_status} | Stability: {stability:.0f}% | Tilt: {motion_data['tilt_angle']:.1f}°"
            draw.text((14, info_y), motion_text, fill=(255, 105, 180), font=small_font)  # Hot pink
            info_y += 14
            
            # Add temperature if available
            if motion_data['temperature'] != 0:
                temp_text = f"  Temperature: {motion_data['temperature']:.1f}°C | Vibration: {motion_data['vibration_level']:.1f}°/s"
                draw.text((14, info_y), temp_text, fill=(255, 105, 180), font=small_font)  # Hot pink
        else:
            # Note when motion sensor not available
            no_motion_text = "📱 Motion sensor not available"
            draw.text((14, info_y), no_motion_text, fill=(144, 238, 144), font=small_font)  # Light green
        
        # Save with high quality
        pil_image.save(filepath, 'JPEG', quality=95)
        
        if os.path.exists(filepath):
            logger.info(f"Captured annotated frame from {camera_type} camera: {filename}")
            return jsonify({
                'success': True,
                'filename': filename,
                'path': filepath,
                'url': f'/static/gallery/images/{filename}',
                'message': f'Annotated image captured successfully',
                'nearby_flights': len(nearby_flights),
                'overhead_satellites': len(overhead_satellites)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save annotated image'
            }), 500
            
    except Exception as e:
        logger.error(f"Capture error for {camera_type}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/save_stack', methods=['POST'])
def api_save_stack():
    """Save a stacked image from client-side processing"""
    try:
        import base64
        from datetime import datetime
        import os
        
        data = request.json
        if not data or 'image' not in data:
            return jsonify({
                'success': False,
                'error': 'No image data provided'
            }), 400
        
        camera_type = data.get('camera', 'unknown')
        image_data = data['image']
        
        # Remove data URL prefix if present
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        # Decode base64 image
        image_bytes = base64.b64decode(image_data)
        
        # Save to gallery/stacks directory from config
        gallery_dirs = Config.STORAGE.get('gallery_dirs', [])
        stacks_dir = None
        for dir_path, url_prefix in gallery_dirs:
            if 'stacks' in dir_path:
                stacks_dir = dir_path
                break
        
        save_path = stacks_dir or 'static/gallery/stacks'
        os.makedirs(save_path, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'stacked_{camera_type}_{timestamp}.jpg'
        filepath = os.path.join(save_path, filename)
        
        # Load image and add flight annotations
        from PIL import Image, ImageDraw, ImageFont
        from io import BytesIO
        
        # Load the image from bytes
        pil_image = Image.open(BytesIO(image_bytes))
        draw = ImageDraw.Draw(pil_image)
        
        # Try to load fonts
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        except:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        
        # Add timestamp and stacking info
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary_text = f"{timestamp_str} | {camera_type.upper()} Image Stack"
        
        # Draw timestamp background
        bbox = draw.textbbox((0, 0), summary_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        draw.rectangle(
            [10, 10, 10 + text_width + 8, 10 + text_height + 8],
            fill=(0, 0, 0, 128),
            outline=(255, 255, 0)
        )
        
        draw.text((14, 14), summary_text, fill=(255, 255, 0), font=font)
        
        # Add nearby flights information
        info_y = 10 + text_height + 20
        nearby_flights = get_nearby_flights_for_annotation()
        if nearby_flights:
            # Add flight header
            flight_header = f"🛩️ Nearby Aircraft ({len(nearby_flights)} within {Config.ADSB['max_distance_miles']} mi):"
            draw.text((14, info_y), flight_header, fill=(135, 206, 235), font=small_font)  # Sky blue
            info_y += 16
            
            # Add individual flights
            for i, flight in enumerate(nearby_flights):
                flight_text = f"  {flight['callsign']}: {flight['distance_miles']}mi, {flight['altitude_ft']:,}ft, {flight['bearing_deg']}°"
                draw.text((14, info_y), flight_text, fill=(176, 224, 230), font=small_font)  # Light blue
                info_y += 14
                
                # Limit to prevent image overflow
                if i >= 7:  # Show max 8 flights to prevent clutter
                    remaining = len(nearby_flights) - (i + 1)
                    if remaining > 0:
                        draw.text((14, info_y), f"  ... and {remaining} more aircraft", fill=(176, 224, 230), font=small_font)
                    break
        else:
            # Note when no flights are detected
            no_flights_text = f"📡 No aircraft within {Config.ADSB['max_distance_miles']} miles"
            draw.text((14, info_y), no_flights_text, fill=(144, 238, 144), font=small_font)  # Light green
        
        # Add space before satellite section
        info_y += 20
        
        # Add overhead satellites information
        overhead_satellites = get_overhead_satellites_for_annotation()
        if overhead_satellites:
            # Add satellite header
            satellite_header = f"🛰️ Overhead Satellites ({len(overhead_satellites)} above {Config.SATELLITE['min_elevation']}°):"
            draw.text((14, info_y), satellite_header, fill=(255, 165, 0), font=small_font)  # Orange
            info_y += 16
            
            # Add individual satellites
            for i, sat in enumerate(overhead_satellites):
                sat_text = f"  {sat['name']}: {sat['elevation_deg']}° elev, {sat['altitude_km']}km alt, {sat['category']}"
                draw.text((14, info_y), sat_text, fill=(255, 215, 0), font=small_font)  # Gold
                info_y += 14
                
                # Limit to prevent image overflow
                if i >= 5:  # Show max 6 satellites to prevent clutter
                    remaining = len(overhead_satellites) - (i + 1)
                    if remaining > 0:
                        draw.text((14, info_y), f"  ... and {remaining} more satellites", fill=(255, 215, 0), font=small_font)
                    break
        else:
            # Note when no satellites are detected
            no_satellites_text = f"🛰️ No satellites above {Config.SATELLITE['min_elevation']}° elevation"
            draw.text((14, info_y), no_satellites_text, fill=(144, 238, 144), font=small_font)  # Light green
        
        # Add space before motion sensor section
        info_y += 20
        
        # Add motion sensor information
        motion_data = get_motion_data_for_annotation()
        if motion_data:
            # Add motion sensor header
            motion_header = f"📱 Motion Sensor ({'Calibrated' if motion_data['calibrated'] else 'Uncalibrated'})"
            draw.text((14, info_y), motion_header, fill=(255, 20, 147), font=small_font)  # Deep pink
            info_y += 16
            
            # Add orientation data
            orient = motion_data['orientation']
            orientation_text = f"  Orientation: P:{orient['pitch']:.1f}° R:{orient['roll']:.1f}° Y:{orient['yaw']:.1f}°"
            draw.text((14, info_y), orientation_text, fill=(255, 105, 180), font=small_font)  # Hot pink
            info_y += 14
            
            # Add motion status and stability
            stability = motion_data['stability_score']
            motion_status = "MOTION" if motion_data['motion_detected'] else "STABLE"
            motion_text = f"  Status: {motion_status} | Stability: {stability:.0f}% | Tilt: {motion_data['tilt_angle']:.1f}°"
            draw.text((14, info_y), motion_text, fill=(255, 105, 180), font=small_font)  # Hot pink
            info_y += 14
            
            # Add temperature if available
            if motion_data['temperature'] != 0:
                temp_text = f"  Temperature: {motion_data['temperature']:.1f}°C | Vibration: {motion_data['vibration_level']:.1f}°/s"
                draw.text((14, info_y), temp_text, fill=(255, 105, 180), font=small_font)  # Hot pink
        else:
            # Note when motion sensor not available
            no_motion_text = "📱 Motion sensor not available"
            draw.text((14, info_y), no_motion_text, fill=(144, 238, 144), font=small_font)  # Light green
        
        # Save the annotated image with high quality
        pil_image.save(filepath, 'JPEG', quality=95)
        
        logger.info(f"Saved annotated stacked image: {filename} with {len(nearby_flights)} nearby flights")
        return jsonify({
            'success': True,
            'filename': filename,
            'path': filepath,
            'message': 'Stacked image saved successfully'
        })
        
    except Exception as e:
        logger.error(f"Save stack error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# Gallery API Routes
# ============================================================================

@app.route('/api/gallery/images')
def api_gallery_images():
    """Get list of all images from multiple gallery directories"""
    try:
        images = []
        
        # Get gallery directories from config
        gallery_dirs = Config.STORAGE.get('gallery_dirs', [
            ('static/gallery/images', '/static/gallery/images/'),
            ('static/gallery/stacks', '/static/gallery/stacks/'),
            ('detections', '/detections/')
        ])
        
        for dir_path, url_prefix in gallery_dirs:
            # Create directory if it doesn't exist
            os.makedirs(dir_path, exist_ok=True)
            
            # Get all image files from this directory
            if os.path.exists(dir_path):
                for filename in os.listdir(dir_path):
                    if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                        filepath = os.path.join(dir_path, filename)
                        try:
                            stat = os.stat(filepath)
                            images.append({
                                'name': filename,
                                'url': url_prefix + filename,
                                'size': stat.st_size,
                                'date': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                'type': dir_path.split('/')[-1]  # Add type for categorization
                            })
                        except Exception as e:
                            logger.error(f"Error processing gallery image {filename}: {e}")
        
        # Sort by date (newest first)
        images.sort(key=lambda x: x['date'], reverse=True)
        
        return jsonify({
            'success': True,
            'images': images,
            'count': len(images)
        })
        
    except Exception as e:
        logger.error(f"Gallery images error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/gallery/delete', methods=['POST'])
def api_gallery_delete():
    """Delete a specific image from the gallery"""
    try:
        data = request.json
        filename = data.get('filename')
        
        if not filename:
            return jsonify({
                'success': False,
                'error': 'No filename provided'
            }), 400
        
        # Security check - prevent directory traversal
        if '..' in filename or '\\' in filename:
            return jsonify({
                'success': False,
                'error': 'Invalid filename'
            }), 400
        
        # Try multiple locations where gallery images might be stored
        possible_paths = [
            os.path.join('static/gallery/images', filename),
            os.path.join('static/gallery/stacks', filename),
            os.path.join('detections', filename),
            os.path.join(Config.STORAGE['save_path'], filename)
        ]
        
        filepath = None
        for path in possible_paths:
            if os.path.exists(path):
                filepath = path
                logger.info(f"Found file at: {filepath}")
                break
        
        if not filepath:
            logger.error(f"File '{filename}' not found in any gallery directory")
            logger.error(f"Searched: {possible_paths}")
            return jsonify({
                'success': False,
                'error': 'File not found'
            }), 404
        
        # Delete the file
        os.remove(filepath)
        logger.info(f"Deleted gallery image: {filename}")
        
        return jsonify({
            'success': True,
            'message': f'Deleted {filename}'
        })
        
    except Exception as e:
        logger.error(f"Gallery delete error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/gallery/clear', methods=['POST'])
def api_gallery_clear():
    """Clear all images from the gallery"""
    try:
        gallery_path = Config.STORAGE['save_path']
        
        if not os.path.exists(gallery_path):
            return jsonify({
                'success': True,
                'message': 'Gallery already empty'
            })
        
        count = 0
        for filename in os.listdir(gallery_path):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                try:
                    os.remove(os.path.join(gallery_path, filename))
                    count += 1
                except Exception as e:
                    logger.error(f"Error deleting {filename}: {e}")
        
        logger.info(f"Cleared gallery: deleted {count} images")
        
        return jsonify({
            'success': True,
            'message': f'Deleted {count} images'
        })
        
    except Exception as e:
        logger.error(f"Gallery clear error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/gallery/upload', methods=['POST'])
def api_gallery_upload():
    """Upload images to the gallery"""
    try:
        if 'files' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No files provided'
            }), 400
        
        gallery_path = Config.STORAGE['save_path']
        os.makedirs(gallery_path, exist_ok=True)
        
        uploaded = 0
        files = request.files.getlist('files')
        
        for file in files:
            if file and file.filename:
                # Security check - sanitize filename
                filename = os.path.basename(file.filename)
                if '..' in filename:
                    continue
                
                # Add timestamp to filename to avoid collisions
                base, ext = os.path.splitext(filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{base}_{timestamp}{ext}"
                
                filepath = os.path.join(gallery_path, filename)
                file.save(filepath)
                uploaded += 1
                logger.info(f"Uploaded gallery image: {filename}")
        
        return jsonify({
            'success': True,
            'uploaded': uploaded,
            'message': f'Uploaded {uploaded} image(s)'
        })
        
    except Exception as e:
        logger.error(f"Gallery upload error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/gallery/export')
def api_gallery_export():
    """Export all gallery images as a zip file"""
    try:
        import zipfile
        from io import BytesIO
        
        gallery_path = Config.STORAGE['save_path']
        
        # Create zip file in memory
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for filename in os.listdir(gallery_path):
                if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    filepath = os.path.join(gallery_path, filename)
                    zip_file.write(filepath, filename)
        
        zip_buffer.seek(0)
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'gallery_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
        )
        
    except Exception as e:
        logger.error(f"Gallery export error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/detections/<filename>')
def serve_gallery_image(filename):
    """Serve gallery images from the detections directory"""
    try:
        # Security check - prevent directory traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            return "Invalid filename", 400
        
        gallery_path = Config.STORAGE['save_path']
        filepath = os.path.join(gallery_path, filename)
        
        if os.path.exists(filepath):
            return send_file(filepath, mimetype='image/jpeg')
        else:
            return "File not found", 404
            
    except Exception as e:
        logger.error(f"Error serving gallery image {filename}: {e}")
        return "Error serving image", 500

# ============================================================================
# Timelapse API Routes  
# ============================================================================

@app.route('/api/timelapse/status')
def api_timelapse_status():
    """Get timelapse service status"""
    try:
        from timelapse_service import TimelapseService
        
        # Check if service is running (this is a simplified check)
        # In production, you'd want a proper service registry
        status = {
            "available": True,
            "running": False,  # This would be set by actual service
            "current_hour": datetime.now().strftime("%Y-%m-%d_%H"),
            "output_directory": "static/gallery/videos"
        }
        
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        logger.error(f"Timelapse status error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/timelapse/videos')
def api_timelapse_videos():
    """Get list of available timelapse videos"""
    try:
        videos_dir = "static/gallery/videos"
        os.makedirs(videos_dir, exist_ok=True)
        
        videos = []
        
        if os.path.exists(videos_dir):
            for filename in os.listdir(videos_dir):
                if filename.lower().endswith('.mp4') and filename.startswith('timelapse_'):
                    filepath = os.path.join(videos_dir, filename)
                    try:
                        stat = os.stat(filepath)
                        
                        # Parse video type and hour from filename
                        # timelapse_hq_2025-01-01_12.mp4 or timelapse_combined_2025-01-01_12.mp4
                        parts = filename.replace('.mp4', '').split('_')
                        video_type = parts[1] if len(parts) > 1 else 'unknown'
                        hour_key = '_'.join(parts[2:]) if len(parts) > 2 else 'unknown'
                        
                        videos.append({
                            'name': filename,
                            'url': f"/static/gallery/videos/{filename}",
                            'size': stat.st_size,
                            'date': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            'type': video_type,
                            'hour': hour_key,
                            'duration': 'unknown'  # Could be calculated with ffprobe if needed
                        })
                    except Exception as e:
                        logger.error(f"Error processing video {filename}: {e}")
        
        # Sort by date (newest first)
        videos.sort(key=lambda x: x['date'], reverse=True)
        
        return jsonify({
            'success': True,
            'videos': videos,
            'count': len(videos)
        })
        
    except Exception as e:
        logger.error(f"Timelapse videos error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/timelapse/delete', methods=['POST'])
def api_timelapse_delete():
    """Delete a timelapse video"""
    try:
        data = request.json
        filename = data.get('filename')
        
        if not filename:
            return jsonify({
                'success': False,
                'error': 'No filename provided'
            }), 400
        
        # Security check
        if '..' in filename or '\\' in filename or not filename.endswith('.mp4'):
            return jsonify({
                'success': False,
                'error': 'Invalid filename'
            }), 400
        
        videos_dir = "static/gallery/videos"
        filepath = os.path.join(videos_dir, filename)
        
        if os.path.exists(filepath) and filename.startswith('timelapse_'):
            os.remove(filepath)
            logger.info(f"Deleted timelapse video: {filename}")
            
            return jsonify({
                'success': True,
                'message': f'Video {filename} deleted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Video not found or invalid'
            }), 404
            
    except Exception as e:
        logger.error(f"Timelapse delete error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/timelapse/cleanup', methods=['POST'])
def api_timelapse_cleanup():
    """Cleanup old timelapse videos"""
    try:
        data = request.json or {}
        days_to_keep = data.get('days', 7)
        
        videos_dir = "static/gallery/videos"
        cutoff_time = datetime.now() - timedelta(days=days_to_keep)
        
        deleted_count = 0
        
        if os.path.exists(videos_dir):
            for filename in os.listdir(videos_dir):
                if filename.lower().endswith('.mp4') and filename.startswith('timelapse_'):
                    filepath = os.path.join(videos_dir, filename)
                    stat = os.stat(filepath)
                    file_time = datetime.fromtimestamp(stat.st_mtime)
                    
                    if file_time < cutoff_time:
                        os.remove(filepath)
                        deleted_count += 1
                        logger.info(f"Cleaned up old timelapse: {filename}")
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Cleaned up {deleted_count} old videos'
        })
        
    except Exception as e:
        logger.error(f"Timelapse cleanup error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# Motion Detection API Routes
# ============================================================================

@app.route('/api/motion/capture_with_annotations', methods=['POST'])
def api_motion_capture_with_annotations():
    """Capture a frame with motion detection annotations"""
    try:
        import requests
        import cv2
        import numpy as np
        import base64
        from io import BytesIO
        from PIL import Image, ImageDraw, ImageFont
        
        data = request.json or {}
        camera_type = data.get('camera', 'hq')  # Default to HQ camera
        motion_areas = data.get('motionAreas', [])
        detection_info = data.get('detectionInfo', {})
        
        # Validate camera type
        if camera_type not in ['ir', 'hq']:
            return jsonify({
                'success': False,
                'error': 'Invalid camera type. Use "ir" or "hq"'
            }), 400
        
        # Get frame from the frame service
        try:
            response = requests.get(f'http://localhost:5002/{camera_type}_frame', timeout=5)
            if response.status_code != 200:
                return jsonify({
                    'success': False,
                    'error': f'{camera_type.upper()} camera not available'
                }), 503
            
            # Convert response content to PIL Image
            image = Image.open(BytesIO(response.content))
            draw = ImageDraw.Draw(image)
            
            # Try to load a font, fallback to default if not available
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
                small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
            except:
                font = ImageFont.load_default()
                small_font = ImageFont.load_default()
            
            # Draw motion detection annotations
            for i, area in enumerate(motion_areas):
                x = int(area.get('x', 0))
                y = int(area.get('y', 0))
                width = int(area.get('width', 50))
                height = int(area.get('height', 50))
                intensity = area.get('intensity', 0)
                
                # Draw bounding box
                draw.rectangle(
                    [x, y, x + width, y + height],
                    outline=(0, 255, 0),
                    width=2
                )
                
                # Draw filled background for label
                label = f"Object {i+1}"
                bbox = draw.textbbox((0, 0), label, font=font)
                label_width = bbox[2] - bbox[0]
                label_height = bbox[3] - bbox[1]
                
                draw.rectangle(
                    [x, y - label_height - 4, x + label_width + 4, y],
                    fill=(0, 255, 0),
                    outline=(0, 255, 0)
                )
                
                # Draw object label
                draw.text((x + 2, y - label_height - 2), label, fill=(0, 0, 0), font=font)
                
                # Draw intensity if provided
                if intensity > 0:
                    intensity_text = f"INT: {int(intensity)}"
                    draw.text((x + 2, y + 2), intensity_text, fill=(0, 255, 0), font=small_font)
            
            # Add timestamp and detection summary
            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            summary_text = f"{timestamp_str} | {camera_type.upper()} | Objects: {len(motion_areas)}"
            
            # Draw timestamp background
            bbox = draw.textbbox((0, 0), summary_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            draw.rectangle(
                [10, 10, 10 + text_width + 8, 10 + text_height + 8],
                fill=(0, 0, 0, 128),
                outline=(255, 255, 0)
            )
            
            draw.text((14, 14), summary_text, fill=(255, 255, 0), font=font)
            
            # Add detection info if provided
            info_y = 10 + text_height + 20
            if detection_info:
                for key, value in detection_info.items():
                    info_text = f"{key}: {value}"
                    draw.text((14, info_y), info_text, fill=(255, 255, 255), font=small_font)
                    info_y += 16
            
            # Add nearby flights information
            nearby_flights = get_nearby_flights_for_annotation()
            if nearby_flights:
                # Add flight header
                flight_header = f"🛩️ Nearby Aircraft ({len(nearby_flights)} within {Config.ADSB['max_distance_miles']} mi):"
                draw.text((14, info_y), flight_header, fill=(135, 206, 235), font=small_font)  # Sky blue
                info_y += 16
                
                # Add individual flights
                for i, flight in enumerate(nearby_flights):
                    flight_text = f"  {flight['callsign']}: {flight['distance_miles']}mi, {flight['altitude_ft']:,}ft, {flight['bearing_deg']}°"
                    draw.text((14, info_y), flight_text, fill=(176, 224, 230), font=small_font)  # Light blue
                    info_y += 14
                    
                    # Limit to prevent image overflow
                    if i >= 7:  # Show max 8 flights to prevent clutter
                        remaining = len(nearby_flights) - (i + 1)
                        if remaining > 0:
                            draw.text((14, info_y), f"  ... and {remaining} more aircraft", fill=(176, 224, 230), font=small_font)
                        break
            else:
                # Note when no flights are detected
                no_flights_text = f"📡 No aircraft within {Config.ADSB['max_distance_miles']} miles"
                draw.text((14, info_y), no_flights_text, fill=(144, 238, 144), font=small_font)  # Light green
                info_y += 16
            
            # Add space before satellite section
            info_y += 10
            
            # Add overhead satellites information
            overhead_satellites = get_overhead_satellites_for_annotation()
            if overhead_satellites:
                # Add satellite header
                satellite_header = f"🛰️ Overhead Satellites ({len(overhead_satellites)} above {Config.SATELLITE['min_elevation']}°):"
                draw.text((14, info_y), satellite_header, fill=(255, 165, 0), font=small_font)  # Orange
                info_y += 16
                
                # Add individual satellites
                for i, sat in enumerate(overhead_satellites):
                    sat_text = f"  {sat['name']}: {sat['elevation_deg']}° elev, {sat['altitude_km']}km alt, {sat['category']}"
                    draw.text((14, info_y), sat_text, fill=(255, 215, 0), font=small_font)  # Gold
                    info_y += 14
                    
                    # Limit to prevent image overflow
                    if i >= 5:  # Show max 6 satellites to prevent clutter
                        remaining = len(overhead_satellites) - (i + 1)
                        if remaining > 0:
                            draw.text((14, info_y), f"  ... and {remaining} more satellites", fill=(255, 215, 0), font=small_font)
                        break
            else:
                # Note when no satellites are detected
                no_satellites_text = f"🛰️ No satellites above {Config.SATELLITE['min_elevation']}° elevation"
                draw.text((14, info_y), no_satellites_text, fill=(144, 238, 144), font=small_font)  # Light green
            
            # Add space before motion sensor section
            info_y += 15
            
            # Add motion sensor information
            motion_data = get_motion_data_for_annotation()
            if motion_data:
                # Add motion sensor header
                motion_header = f"📱 Motion Sensor ({'Calibrated' if motion_data['calibrated'] else 'Uncalibrated'})"
                draw.text((14, info_y), motion_header, fill=(255, 20, 147), font=small_font)  # Deep pink
                info_y += 16
                
                # Add orientation data
                orient = motion_data['orientation']
                orientation_text = f"  Orientation: P:{orient['pitch']:.1f}° R:{orient['roll']:.1f}° Y:{orient['yaw']:.1f}°"
                draw.text((14, info_y), orientation_text, fill=(255, 105, 180), font=small_font)  # Hot pink
                info_y += 14
                
                # Add motion status and stability
                stability = motion_data['stability_score']
                motion_status = "MOTION" if motion_data['motion_detected'] else "STABLE"
                motion_text = f"  Status: {motion_status} | Stability: {stability:.0f}% | Tilt: {motion_data['tilt_angle']:.1f}°"
                draw.text((14, info_y), motion_text, fill=(255, 105, 180), font=small_font)  # Hot pink
            else:
                # Note when motion sensor not available
                no_motion_text = "📱 Motion sensor not available"
                draw.text((14, info_y), no_motion_text, fill=(144, 238, 144), font=small_font)  # Light green
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get frame from frame service: {e}")
            return jsonify({
                'success': False,
                'error': 'Frame service not available'
            }), 503
        
        # Save annotated image to gallery
        save_path = 'static/gallery/images'
        os.makedirs(save_path, exist_ok=True)
        
        filename = f'motion_{camera_type}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.jpg'
        filepath = os.path.join(save_path, filename)
        
        # Save with high quality
        image.save(filepath, 'JPEG', quality=95)
        
        logger.info(f"Motion detection snapshot saved: {filename}")
        
        return jsonify({
            'success': True,
            'filename': filename,
            'path': filepath,
            'url': f'/static/gallery/images/{filename}',
            'camera': camera_type,
            'timestamp': timestamp_str,
            'objects_detected': len(motion_areas),
            'file_size': os.path.getsize(filepath)
        })
        
    except Exception as e:
        logger.error(f"Motion capture error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/motion/settings', methods=['GET', 'POST'])
def api_motion_settings():
    """Get or update motion detection settings"""
    try:
        if request.method == 'POST':
            data = request.json or {}
            
            # Here you could save settings to a config file or database
            # For now, just return the settings that were sent
            settings = {
                'sensitivity': data.get('sensitivity', 40),
                'min_area': data.get('min_area', 100),
                'enabled': data.get('enabled', False),
                'auto_capture': data.get('auto_capture', True),
                'capture_threshold': data.get('capture_threshold', 2)
            }
            
            logger.info(f"Motion detection settings updated: {settings}")
            
            return jsonify({
                'success': True,
                'settings': settings,
                'message': 'Settings updated successfully'
            })
            
        else:
            # GET request - return current settings
            # Default settings (in production, load from config)
            settings = {
                'sensitivity': 40,
                'min_area': 100,
                'enabled': False,
                'auto_capture': True,
                'capture_threshold': 2
            }
            
            return jsonify({
                'success': True,
                'settings': settings
            })
            
    except Exception as e:
        logger.error(f"Motion settings error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ============================================================================
# ADSB Flight Tracking API Routes  
# ============================================================================

@app.route('/api/adsb/status')
def adsb_status():
    """Get ADSB tracker status"""
    if not adsb_tracker:
        return jsonify({"error": "ADSB tracker not available"}), 503
    
    try:
        status = adsb_tracker.get_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting ADSB status: {e}")
        return jsonify({"error": "Failed to get ADSB status"}), 500

@app.route('/api/adsb/flights')
def adsb_flights():
    """Get current flights within configured range"""
    if not adsb_tracker:
        return jsonify({"error": "ADSB tracker not available"}), 503
    
    try:
        flights = adsb_tracker.get_current_flights()
        return jsonify({
            "success": True,
            "flight_count": len(flights),
            "flights": flights,
            "last_update": adsb_tracker.get_status()["last_update"]
        })
    except Exception as e:
        logger.error(f"Error getting ADSB flights: {e}")
        return jsonify({"error": "Failed to get flights data"}), 500

@app.route('/api/adsb/test_connection')
def adsb_test_connection():
    """Test connection to PiAware SkyAware ADSB feeder"""
    if not adsb_service:
        return jsonify({"error": "ADSB service not available"}), 503
    
    try:
        # Test the connection by getting current aircraft
        aircraft = adsb_service.get_aircraft()
        total_aircraft = len(aircraft)
        
        return jsonify({
            "success": True,
            "connection_status": "OK",
            "piaware_url": Config.ADSB['piaware_url'],
            "total_aircraft_received": total_aircraft,
            "message": f"Successfully connected to PiAware - received {total_aircraft} aircraft records"
        })
    except Exception as e:
        logger.error(f"Error testing ADSB connection: {e}")
        return jsonify({
            "success": False,
            "connection_status": "Error",
            "piaware_url": Config.ADSB['piaware_url'],
            "error": str(e)
        })

# Feature Tracking API Endpoints
@app.route('/api/feature_tracker/still_frame/<camera_type>')
def get_still_frame_for_tracking(camera_type):
    """Get a still frame for feature selection"""
    if not feature_tracker:
        return jsonify({"error": "Feature tracker not available"}), 503
    
    try:
        import cv2
        import base64
        
        # Get frame from feature tracker
        frame = feature_tracker.get_still_frame(camera_type)
        if frame is None:
            return jsonify({"error": "Failed to get frame"}), 500
        
        # Convert to JPEG for transmission
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        frame_b64 = base64.b64encode(buffer).decode('utf-8')
        
        return jsonify({
            "success": True,
            "frame_data": frame_b64,
            "camera_type": camera_type,
            "frame_shape": frame.shape[:2]  # [height, width]
        })
        
    except Exception as e:
        logger.error(f"Error getting still frame: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/feature_tracker/select', methods=['POST'])
def select_tracking_feature():
    """Select a feature at specified coordinates for tracking"""
    if not feature_tracker:
        return jsonify({"error": "Feature tracker not available"}), 503
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        x = data.get('x')
        y = data.get('y')
        camera_type = data.get('camera_type', 'ir')
        
        if x is None or y is None:
            return jsonify({"error": "Missing x or y coordinates"}), 400
        
        # Get fresh frame
        frame = feature_tracker.get_still_frame(camera_type)
        if frame is None:
            return jsonify({"error": "Failed to get frame for feature selection"}), 500
        
        # Select feature at the specified point
        success = feature_tracker.select_feature_at_point(int(x), int(y), frame)
        
        if success:
            status = feature_tracker.get_status()
            return jsonify({
                "success": True,
                "message": "Feature selected successfully",
                "feature_point": status['target_point'],
                "selected_point": status['selected_point'],
                "camera_type": camera_type
            })
        else:
            return jsonify({
                "success": False,
                "error": "No trackable feature found at the selected point"
            }), 400
        
    except Exception as e:
        logger.error(f"Error selecting tracking feature: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/feature_tracker/start', methods=['POST'])
def start_feature_tracking():
    """Start feature tracking with motors"""
    if not feature_tracker:
        return jsonify({"error": "Feature tracker not available"}), 503
    
    try:
        success = feature_tracker.start_tracking()
        
        if success:
            return jsonify({
                "success": True,
                "message": "Feature tracking started",
                "status": feature_tracker.get_status()
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to start tracking - no feature selected or already running"
            }), 400
        
    except Exception as e:
        logger.error(f"Error starting feature tracking: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/feature_tracker/stop', methods=['POST'])
def stop_feature_tracking():
    """Stop feature tracking"""
    if not feature_tracker:
        return jsonify({"error": "Feature tracker not available"}), 503
    
    try:
        feature_tracker.stop_tracking()
        
        return jsonify({
            "success": True,
            "message": "Feature tracking stopped",
            "status": feature_tracker.get_status()
        })
        
    except Exception as e:
        logger.error(f"Error stopping feature tracking: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/feature_tracker/status')
def get_feature_tracker_status():
    """Get current feature tracker status"""
    if not feature_tracker:
        return jsonify({"error": "Feature tracker not available"}), 503
    
    try:
        status = feature_tracker.get_status()
        return jsonify({
            "success": True,
            "status": status
        })
        
    except Exception as e:
        logger.error(f"Error getting feature tracker status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/feature_tracker/clear', methods=['POST'])
def clear_feature_selection():
    """Clear the current feature selection"""
    if not feature_tracker:
        return jsonify({"error": "Feature tracker not available"}), 503
    
    try:
        feature_tracker.clear_selection()
        
        return jsonify({
            "success": True,
            "message": "Feature selection cleared",
            "status": feature_tracker.get_status()
        })
        
    except Exception as e:
        logger.error(f"Error clearing feature selection: {e}")
        return jsonify({"error": str(e)}), 500

# MPU9250 Sensor API Endpoints
@app.route('/api/sensor/data')
def get_sensor_data():
    """Get current MPU9250 sensor data"""
    if not mpu9250_sensor:
        return jsonify({"error": "MPU9250 sensor not available"}), 503
    
    try:
        data = mpu9250_sensor.get_current_data()
        return jsonify({
            "success": True,
            "data": data
        })
    except Exception as e:
        logger.error(f"Error reading sensor data: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sensor/compass')
def get_compass_data():
    """Get compass-specific data from MPU9250"""
    if not mpu9250_sensor:
        return jsonify({"error": "MPU9250 sensor not available"}), 503
    
    try:
        compass_data = mpu9250_sensor.get_compass_data()
        return jsonify({
            "success": True,
            "data": compass_data
        })
    except Exception as e:
        logger.error(f"Error reading compass data: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sensor/status')
def get_sensor_status():
    """Get MPU9250 sensor status"""
    if not mpu9250_sensor:
        return jsonify({"error": "MPU9250 sensor not available"}), 503
    
    try:
        status = mpu9250_sensor.get_status()
        return jsonify({
            "success": True,
            "status": status
        })
    except Exception as e:
        logger.error(f"Error reading sensor status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sensor/calibrate/accelerometer', methods=['POST'])
def calibrate_accelerometer():
    """Calibrate accelerometer and gyroscope"""
    if not mpu9250_sensor:
        return jsonify({"error": "MPU9250 sensor not available"}), 503
    
    try:
        data = request.get_json() if request.is_json else {}
        samples = data.get('samples', 1000)
        
        success = mpu9250_sensor.calibrate_accelerometer_gyroscope(samples)
        return jsonify({
            "success": success,
            "message": "Accelerometer and gyroscope calibration completed" if success else "Calibration failed"
        })
    except Exception as e:
        logger.error(f"Error calibrating accelerometer: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sensor/calibrate/magnetometer', methods=['POST'])
def calibrate_magnetometer():
    """Calibrate magnetometer for compass functionality"""
    if not mpu9250_sensor:
        return jsonify({"error": "MPU9250 sensor not available"}), 503
    
    try:
        data = request.get_json() if request.is_json else {}
        duration = data.get('duration', 60)
        
        success = mpu9250_sensor.calibrate_magnetometer(duration)
        return jsonify({
            "success": success,
            "message": f"Magnetometer calibration completed in {duration}s" if success else "Calibration failed"
        })
    except Exception as e:
        logger.error(f"Error calibrating magnetometer: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sensor/compass/set_declination', methods=['POST'])
def set_magnetic_declination():
    """Set magnetic declination for true north calculation"""
    if not mpu9250_sensor:
        return jsonify({"error": "MPU9250 sensor not available"}), 503
    
    try:
        data = request.get_json()
        if not data or 'declination' not in data:
            return jsonify({"error": "Declination value required"}), 400
        
        declination = float(data['declination'])
        mpu9250_sensor.set_magnetic_declination(declination)
        
        return jsonify({
            "success": True,
            "message": f"Magnetic declination set to {declination}°"
        })
    except Exception as e:
        logger.error(f"Error setting magnetic declination: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sensor/compass/set_north', methods=['POST'])
def set_compass_north():
    """Set current heading as north reference"""
    if not mpu9250_sensor:
        return jsonify({"error": "MPU9250 sensor not available"}), 503

    try:
        data = request.get_json() if request.is_json else {}
        current_heading = data.get('current_heading')

        if current_heading is None:
            # Use current heading from sensor
            compass_data = mpu9250_sensor.get_compass_data()
            current_heading = compass_data['heading']

        mpu9250_sensor.set_compass_north_reference(current_heading)

        return jsonify({
            "success": True,
            "message": f"North reference set to current heading: {current_heading}°"
        })
    except Exception as e:
        logger.error(f"Error setting compass north reference: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sensor/calibrate/level_north', methods=['POST'])
def calibrate_level_north():
    """Auto-calibrate compass: Level device and point north"""
    if not mpu9250_sensor:
        return jsonify({"error": "MPU9250 sensor not available"}), 503

    try:
        data = request.get_json() if request.is_json else {}
        samples = data.get('samples', 100)
        tolerance = data.get('tolerance', 5.0)

        result = mpu9250_sensor.calibrate_level_and_north(samples, tolerance)

        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error in level-and-north calibration: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/sensor/is_level', methods=['GET'])
def check_is_level():
    """Check if device is currently level"""
    if not mpu9250_sensor:
        return jsonify({"error": "MPU9250 sensor not available"}), 503

    try:
        tolerance = request.args.get('tolerance', 5.0, type=float)
        is_level, tilt_angle = mpu9250_sensor.is_level(tolerance)

        return jsonify({
            "success": True,
            "is_level": is_level,
            "tilt_angle": round(tilt_angle, 2),
            "tolerance": tolerance,
            "message": f"Device is {'level' if is_level else 'not level'} (tilt={tilt_angle:.1f}°)"
        })
    except Exception as e:
        logger.error(f"Error checking level status: {e}")
        return jsonify({"error": str(e)}), 500

def cleanup_on_exit():
    """Cleanup resources on exit"""
    global cleanup_running
    
    logger.info("Shutting down API service...")
    cleanup_running = False
    
    if pan_tilt:
        try:
            pan_tilt.cleanup()
            logger.info("Pan-tilt controller cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up pan-tilt controller: {e}")
    
    if adsb_tracker:
        try:
            adsb_tracker.stop()
            logger.info("ADSB tracker cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up ADSB tracker: {e}")
    
    if feature_tracker:
        try:
            feature_tracker.stop_tracking()
            logger.info("Feature tracker cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up feature tracker: {e}")
    
    if mpu9250_sensor:
        try:
            mpu9250_sensor.stop()
            logger.info("MPU9250 sensor cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up MPU9250 sensor: {e}")

if __name__ == '__main__':
    try:
        logger.info("Starting UFO Tracker API Service...")
        
        # Initialize pan-tilt controller
        initialize_pan_tilt()
        
        # Initialize ADSB flight tracker
        initialize_adsb_tracker()
        
        # Note: Satellite tracker is now a separate service on port 5003
        logger.info("Satellite tracker runs as separate service on port 5003")
        
        # Initialize motion sensor
        initialize_motion_sensor()
        
        # Initialize feature tracker
        initialize_feature_tracker()
        
        # Start resource cleanup thread
        resource_cleanup_thread = threading.Thread(target=cleanup_resources, daemon=True)
        resource_cleanup_thread.start()
        logger.info("Resource cleanup thread started")
        
        logger.info("Starting UFO Tracker API service...")
        
        # Start Flask app on port 5000 (API only)
        app.run(
            host=Config.HOST,
            port=Config.PORT,  # 5000
            debug=False,
            threaded=True,
            processes=1
        )
        
    except KeyboardInterrupt:
        logger.info("API service stopped by user")
    except Exception as e:
        logger.error(f"API service error: {e}")
    finally:
        cleanup_on_exit()