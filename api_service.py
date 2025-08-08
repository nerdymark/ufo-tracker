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
from datetime import datetime
from flask import Flask, render_template, jsonify, request, Response, url_for, send_from_directory, redirect

# Setup logging first
from config.config import Config

logging.basicConfig(
    level=getattr(logging, Config.LOGGING['level']),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY

# Global objects
pan_tilt = None
resource_cleanup_thread = None
cleanup_running = True

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

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

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

if __name__ == '__main__':
    try:
        logger.info("Starting UFO Tracker API Service...")
        
        # Initialize pan-tilt controller
        initialize_pan_tilt()
        
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