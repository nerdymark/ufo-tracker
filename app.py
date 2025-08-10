#!/usr/bin/env python3
"""
UFO Tracker - Main Flask Application
Dual-camera system for detecting and tracking UFOs using Raspberry Pi
"""

from flask import Flask, render_template, Response, jsonify, request, send_file, g
import logging
import os
import gc
import threading
import time
import psutil
import cv2
import numpy as np
from datetime import datetime

from camera.camera_manager import CameraManager
from detection.motion_detector import MotionDetector
from detection.image_processor import ImageProcessor
from detection.auto_tracker import AutoTracker
from hardware.pan_tilt import PanTiltController
from config.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Reduced from DEBUG to improve performance
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/ufo_tracker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

# Request timing middleware
@app.before_request
def before_request():
    """Track request start time and log request details"""
    g.start_time = time.time()
    g.request_id = int(time.time() * 1000000) % 1000000  # Simple request ID
    
    # Log system resources for main page requests
    if request.path == '/':
        try:
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            cpu_percent = process.cpu_percent()
            logger.info(f"[REQ-{g.request_id}] SYSTEM: Memory={memory_mb:.1f}MB, CPU={cpu_percent:.1f}%")
        except Exception as e:
            logger.warning(f"[REQ-{g.request_id}] Could not get system info: {e}")
    
    logger.info(f"[REQ-{g.request_id}] START {request.method} {request.path} from {request.remote_addr}")

@app.after_request
def after_request(response):
    """Add CORS headers and log request completion time"""
    # Add CORS headers
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    
    # Log request timing
    if hasattr(g, 'start_time'):
        duration = (time.time() - g.start_time) * 1000  # Convert to milliseconds
        request_id = getattr(g, 'request_id', 'unknown')
        # Handle streaming responses that can't report size
        try:
            size = response.content_length or (len(response.get_data()) if hasattr(response, 'get_data') and not response.direct_passthrough else 0)
        except (RuntimeError, AttributeError):
            size = 0  # Streaming response
        logger.info(f"[REQ-{request_id}] COMPLETE {request.method} {request.path} -> {response.status_code} ({size} bytes) in {duration:.1f}ms")
    
    return response

@app.route('/api/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    """Handle preflight OPTIONS requests for API endpoints"""
    response = Response()
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# Initialize components
camera_manager = None
motion_detector = None
image_processor = None
pan_tilt = None
auto_tracker = None

def initialize_components():
    """Initialize camera manager and other components"""
    global camera_manager, motion_detector, image_processor, pan_tilt, auto_tracker
    
    try:
        # Initialize camera manager with timeout
        logger.info("Initializing camera manager...")
        camera_manager = CameraManager()
        logger.info("Camera manager initialized successfully")
        
        # Start camera streaming
        if camera_manager.start_streaming():
            logger.info("Camera streaming started successfully")
        else:
            logger.warning("Failed to start camera streaming")
        
        # Initialize image processor
        image_processor = ImageProcessor()
        logger.info("Image processor initialized successfully")
        
        # Motion detection disabled per user request
        motion_detector = None
        logger.info("Motion detector disabled")
        
        # Initialize auto tracker (without motion detector) - but don't start it by default
        auto_tracker = AutoTracker(camera_manager, None)
        logger.info("Auto tracker initialized successfully (not started by default)")
        
        # Auto tracker will be started only when user navigates to Auto Tracking mode
        logger.info("Auto tracker ready for on-demand activation")
        
        # Initialize pan-tilt controller (placeholder)
        pan_tilt = PanTiltController()
        logger.info("Pan-tilt controller initialized (placeholder)")
        
        # Start periodic cleanup thread to prevent memory leaks
        def cleanup_resources():
            while True:
                try:
                    time.sleep(300)  # Every 5 minutes
                    collected = gc.collect()
                    if collected > 0:
                        logger.debug(f"Garbage collected {collected} objects")
                except Exception as e:
                    logger.error(f"Cleanup error: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_resources, daemon=True)
        cleanup_thread.start()
        logger.info("Resource cleanup thread started")
        
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        raise

@app.route('/')
def index():
    """Main dashboard page"""
    request_id = getattr(g, 'request_id', 'unknown')
    start_time = time.time()
    
    logger.info(f"[REQ-{request_id}] Starting template render...")
    
    # Get the system's IP address
    import socket
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
    
    # Time the template rendering
    template_start = time.time()
    response_content = render_template('unified_dashboard.html', server_ip=local_ip)
    template_time = (time.time() - template_start) * 1000
    logger.info(f"[REQ-{request_id}] Template render completed in {template_time:.1f}ms")
    
    # Time the response creation
    response_start = time.time()
    response = app.response_class(
        response_content,
        mimetype='text/html'
    )
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response_time = (time.time() - response_start) * 1000
    logger.info(f"[REQ-{request_id}] Response creation completed in {response_time:.1f}ms")
    
    total_time = (time.time() - start_time) * 1000
    logger.info(f"[REQ-{request_id}] Index route total time: {total_time:.1f}ms")
    
    return response

@app.route('/unified')
def unified():
    """Unified dashboard page"""
    import socket
    # Get the system's IP address
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
    return render_template('unified_dashboard.html', server_ip=local_ip)

@app.route('/old_dashboard')
def old_dashboard():
    """Original dashboard page"""
    return render_template('index.html')

@app.route('/viewer')
def viewer():
    """Camera viewer page"""
    return render_template('viewer.html')

@app.route('/test_stream')
def test_stream():
    """Simple camera stream test page"""
    return render_template('test_stream.html')

@app.route('/stacked_test')
def stacked_test():
    """Stacked image color and flickering test page"""
    import socket
    # Get the system's IP address
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
    return render_template('stacked_test.html', server_ip=local_ip)

@app.route('/frame_viewer')
def frame_viewer():
    """Frame-based camera viewer (alternative to MJPEG streams)"""
    return render_template('frame_viewer.html')

@app.route('/camera_controls')
def camera_controls():
    """Camera controls page for adjusting exposure and gain"""
    return render_template('camera_controls.html')

@app.route('/test_controls')
def test_controls():
    """Test page for camera controls"""
    from flask import send_file
    return send_file('test_controls.html')

@app.route('/simple_controls')
def simple_controls():
    """Simple camera controls page"""
    from flask import send_file
    return send_file('simple_controls.html')

@app.route('/concurrency_test')
def concurrency_test():
    """Concurrency testing page"""
    from flask import send_file
    return send_file('concurrency_test.html')

@app.route('/image_test')
def image_test():
    """Image loading test page"""
    from flask import send_file
    return send_file('image_test.html')

@app.route('/monitoring')
def monitoring():
    """System monitoring page"""
    from flask import send_file
    return send_file('monitoring.html')

def generate_test_stream():
    """Generate test stream with static image - finite for testing"""
    frame_count = 0
    for frame_count in range(5):  # Just 5 frames for testing
        # Create test frame
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        frame[:] = (100, 150, 200)  # Light blue background
        
        # Add text
        cv2.putText(frame, f"Test Frame {frame_count}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(frame, time.strftime('%H:%M:%S'), (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # Encode to JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if ret:
            frame_bytes = buffer.tobytes()
            
            # Browser-compatible MJPEG without Content-Length
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' +
                   frame_bytes + b'\r\n')
            
            if frame_count % 10 == 0:  # Log every 10th frame
                pass  # Logging disabled
        
        frame_count += 1
        time.sleep(0.1)  # Back to 10 FPS

def generate_ir_stream():
    """Generate IR camera stream directly"""
    frame_count = 0
    logger.info("Starting IR stream generation")
    
    try:
        while frame_count < 10000:  # Limit to prevent runaway loops
            if camera_manager and camera_manager.ir_camera and camera_manager.ir_camera.is_active():
                frame = camera_manager.ir_camera.get_frame()
                if frame is not None:
                    # Keep RGB format for browser display (Picamera2 provides RGB)
                    # No color conversion needed - browsers expect RGB
                    
                    # Encode to JPEG directly (OpenCV can handle RGB for JPEG)
                    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    if ret:
                        frame_bytes = buffer.tobytes()
                        
                        # Browser-compatible MJPEG without Content-Length
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' +
                               frame_bytes + b'\r\n')
                    
                        if frame_count % 10 == 0:  # Log every 10th frame
                            pass  # Logging disabled
            
            frame_count += 1
            time.sleep(0.1)  # 10 FPS
            
    except GeneratorExit:
        logger.info("IR stream generator closed by client")
    except Exception as e:
        logger.error(f"IR stream generator error: {e}")
    finally:
        logger.info(f"IR stream generator finished after {frame_count} frames")

def generate_hq_stream():
    """Generate HQ camera stream directly"""
    frame_count = 0
    logger.info("Starting HQ stream generation")
    
    try:
        while frame_count < 10000:  # Limit to prevent runaway loops
            if camera_manager and camera_manager.hq_camera and camera_manager.hq_camera.is_active():
                frame = camera_manager.hq_camera.get_frame()
                if frame is not None:
                    # Keep RGB format for browser display (Picamera2 provides RGB)
                    # No color conversion needed - browsers expect RGB
                    
                    # Encode to JPEG directly (OpenCV can handle RGB for JPEG)
                    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    if ret:
                        frame_bytes = buffer.tobytes()
                        
                        # Browser-compatible MJPEG without Content-Length
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' +
                               frame_bytes + b'\r\n')
                    
                        if frame_count % 10 == 0:  # Log every 10th frame
                            pass  # Logging disabled
            
            frame_count += 1
            time.sleep(0.1)  # 10 FPS
            
    except GeneratorExit:
        logger.info("HQ stream generator closed by client")
    except Exception as e:
        logger.error(f"HQ stream generator error: {e}")
    finally:
        logger.info(f"HQ stream generator finished after {frame_count} frames")

@app.route('/simple_test')
def simple_test():
    """Ultra simple streaming test"""
    def simple_generator():
        for i in range(3):
            data = f"Frame {i}\n".encode()
            yield data
            logger.info(f"Yielded simple frame {i}")
            time.sleep(1)
    
    logger.info("Simple test route called")
    return Response(simple_generator(), mimetype='text/plain')

@app.route('/test_feed')
def test_feed():
    """Test video feed with static image"""
    logger.info("Test feed route called")
    response = Response(
        generate_test_stream(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'close'
    return response

@app.route('/ir_feed')
def ir_feed():
    """Infrared camera video feed"""
    logger.info("IR feed route called")
    if camera_manager and camera_manager.ir_camera and camera_manager.ir_camera.is_active():
        try:
            logger.info("Creating direct IR stream response")
            response = Response(
                generate_ir_stream(),
                mimetype='multipart/x-mixed-replace; boundary=frame',
                direct_passthrough=True
            )
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            response.headers['Connection'] = 'close'
            return response
        except Exception as e:
            logger.error(f"Error serving IR feed: {e}")
            return "IR camera feed error", 503
    else:
        return "IR camera not available", 503

@app.route('/hq_feed')
def hq_feed():
    """High-quality camera video feed"""
    logger.info("HQ feed route called")
    if camera_manager and camera_manager.hq_camera and camera_manager.hq_camera.is_active():
        try:
            logger.info("Creating direct HQ stream response")
            response = Response(
                generate_hq_stream(),
                mimetype='multipart/x-mixed-replace; boundary=frame',
                direct_passthrough=True
            )
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            response.headers['Connection'] = 'close'
            return response
        except Exception as e:
            logger.error(f"Error serving HQ feed: {e}")
            return "HQ camera feed error", 503
    else:
        return "HQ camera not available", 503

# Frame endpoints moved to camera service (port 5001)

@app.route('/detection_status')
def detection_status():
    """Get current motion detection status"""
    if motion_detector:
        status = motion_detector.get_status()
        return jsonify(status)
    else:
        return jsonify({"error": "Motion detector not available"}), 503

@app.route('/api/pan_tilt', methods=['GET', 'POST'])
def pan_tilt_control():
    """Pan-tilt control endpoint"""
    logger.info(f"Pan-tilt API called: {request.method} from {request.remote_addr}")
    if not pan_tilt:
        logger.error("Pan-tilt controller not available")
        return jsonify({"error": "Pan-tilt controller not available"}), 503
    
    if request.method == 'GET':
        logger.info("Processing GET request for pan-tilt status")
        # Return current status
        try:
            status = pan_tilt.get_status()
            calibration = pan_tilt.get_calibration_status()
            status['calibration'] = calibration
            return jsonify(status)
        except Exception as e:
            logger.error(f"Error getting pan-tilt status: {e}")
            return jsonify({"error": "Failed to get pan-tilt status"}), 500
    
    elif request.method == 'POST':
        # Handle pan-tilt commands
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "No JSON data provided"}), 400
            
            action = data.get('action')
            
            if action == 'move_to':
                pan_angle = data.get('pan', 0.0)
                tilt_angle = data.get('tilt', 0.0)
                blocking = data.get('blocking', False)
                
                if pan_tilt.move_to(pan_angle, tilt_angle, blocking):
                    return jsonify({
                        "success": True,
                        "message": f"Moving to pan={pan_angle:.1f}°, tilt={tilt_angle:.1f}°",
                        "position": {"pan": pan_angle, "tilt": tilt_angle}
                    })
                else:
                    return jsonify({"error": "Failed to move to position"}), 500
            
            elif action == 'move_relative':
                pan_steps = data.get('pan_steps', 0)
                tilt_steps = data.get('tilt_steps', 0)
                
                if pan_tilt.move_relative(pan_steps, tilt_steps):
                    position = pan_tilt.get_position()
                    return jsonify({
                        "success": True,
                        "message": f"Moved {pan_steps} pan steps, {tilt_steps} tilt steps",
                        "position": {"pan": position[0], "tilt": position[1]}
                    })
                else:
                    return jsonify({"error": "Failed to move relative"}), 500
            
            elif action == 'home':
                if pan_tilt.home():
                    return jsonify({
                        "success": True,
                        "message": "Homed to center position",
                        "position": {"pan": 0.0, "tilt": 0.0}
                    })
                else:
                    return jsonify({"error": "Failed to home"}), 500
            
            elif action == 'calibrate':
                axis = data.get('axis')  # 'pan' or 'tilt'
                limit_type = data.get('limit_type')  # 'min' or 'max'
                
                if not axis or not limit_type:
                    return jsonify({"error": "Missing axis or limit_type for calibration"}), 400
                
                if axis not in ['pan', 'tilt'] or limit_type not in ['min', 'max']:
                    return jsonify({"error": "Invalid axis or limit_type"}), 400
                
                if pan_tilt.calibrate_limits(axis, limit_type):
                    calibration = pan_tilt.get_calibration_status()
                    return jsonify({
                        "success": True,
                        "message": f"Set {axis} {limit_type} limit at current position",
                        "calibration": calibration
                    })
                else:
                    return jsonify({"error": "Failed to calibrate"}), 500
            
            elif action == 'set_speed':
                speed = data.get('speed', 100)
                pan_tilt.set_speed(speed)
                return jsonify({
                    "success": True,
                    "message": f"Speed set to {speed}",
                    "speed": speed
                })
            
            elif action == 'enable_motors':
                logger.info("Starting enable_motors action")
                result = pan_tilt.enable_motors()
                logger.info(f"enable_motors returned: {result}")
                if result:
                    return jsonify({
                        "success": True,
                        "message": "Motors enabled (holding torque on)",
                        "motors_enabled": True
                    })
                else:
                    return jsonify({"error": "Failed to enable motors"}), 500
            
            elif action == 'disable_motors':
                if pan_tilt.disable_motors():
                    return jsonify({
                        "success": True,
                        "message": "Motors disabled (power saving mode)",
                        "motors_enabled": False
                    })
                else:
                    return jsonify({"error": "Failed to disable motors"}), 500
            
            elif action == 'start_keepalive':
                if pan_tilt.start_keepalive():
                    return jsonify({
                        "success": True,
                        "message": "Keepalive started - motors will stay powered during long exposures"
                    })
                else:
                    return jsonify({"error": "Failed to start keepalive"}), 500
            
            elif action == 'stop_keepalive':
                pan_tilt.stop_keepalive()
                return jsonify({
                    "success": True,
                    "message": "Keepalive stopped"
                })
            
            elif action == 'set_keepalive_interval':
                interval = data.get('interval', 5.0)
                pan_tilt.set_keepalive_interval(interval)
                return jsonify({
                    "success": True,
                    "message": f"Keepalive interval set to {interval}s"
                })
            
            else:
                return jsonify({"error": f"Unknown action: {action}"}), 400
                
        except Exception as e:
            logger.error(f"Error in pan-tilt control: {e}")
            return jsonify({"error": f"Pan-tilt control error: {str(e)}"}), 500

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
        logger.error(f"Error in motor control: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

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
        logger.error(f"Error in keepalive control: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/test')
def api_test():
    """Simple test endpoint"""
    logger.info("TEST API CALLED - This should be fast")
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

@app.route('/api/system_status')
def system_status():
    """Get overall system status"""
    try:
        status = {
            "timestamp": datetime.now().isoformat(),
            "cameras": {
                "ir_camera": camera_manager.ir_camera.is_active() if camera_manager and camera_manager.ir_camera else False,
                "hq_camera": camera_manager.hq_camera.is_active() if camera_manager and camera_manager.hq_camera else False
            },
            "motion_detector": motion_detector.is_running() if motion_detector else False,
            "auto_tracker": auto_tracker.is_running() if auto_tracker else False,
            "pan_tilt": pan_tilt.is_connected() if pan_tilt else False
        }
        
        # Add storage information
        try:
            if motion_detector:
                storage_info = motion_detector.get_storage_info()
                status["storage"] = storage_info
        except Exception as e:
            logger.warning(f"Could not get storage info: {e}")
            status["storage"] = {"error": "storage info unavailable"}
        
        response = jsonify(status)
        # Add CORS headers
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response
        
    except Exception as e:
        logger.error(f"Error in system_status: {e}")
        error_response = jsonify({
            "error": "system status unavailable",
            "timestamp": datetime.now().isoformat(),
            "cameras": {"ir_camera": False, "hq_camera": False},
            "motion_detector": False,
            "auto_tracker": False,
            "pan_tilt": False
        })
        error_response.headers.add('Access-Control-Allow-Origin', '*')
        error_response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        error_response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return error_response, 500

@app.route('/api/camera_settings/<camera_type>', methods=['GET', 'POST', 'HEAD'])
def camera_settings(camera_type):
    """Get or set camera settings"""
    if camera_type not in ['ir', 'hq']:
        return jsonify({"error": "Invalid camera type"}), 400
    
    if not camera_manager:
        return jsonify({"error": "Camera manager not available"}), 503
    
    camera = camera_manager.ir_camera if camera_type == 'ir' else camera_manager.hq_camera
    if not camera or not camera.is_active():
        return jsonify({"error": f"{camera_type.upper()} camera not available"}), 503
    
    if request.method in ['GET', 'HEAD']:
        # Get current settings
        try:
            settings = {
                "exposure_time": camera.get_exposure_time(),
                "gain": camera.get_gain(),
                "auto_exposure": camera.get_auto_exposure(),
                "brightness": camera.get_brightness(),
                "contrast": camera.get_contrast()
            }
            return jsonify(settings)
        except Exception as e:
            logger.error(f"Error getting {camera_type} camera settings: {e}")
            return jsonify({
                "error": f"Failed to get {camera_type} camera settings",
                "exposure_time": 100000,
                "gain": 4.0,
                "auto_exposure": True,
                "brightness": 0.5,
                "contrast": 1.2
            }), 500
    
    elif request.method == 'POST':
        # Set new settings
        try:
            data = request.get_json() or {}
            result = {"success": True, "updated": []}
            
            # IMPORTANT: Set auto_exposure first, as it affects other controls
            if 'auto_exposure' in data:
                if camera.set_auto_exposure(bool(data['auto_exposure'])):
                    result["updated"].append("auto_exposure")
                else:
                    result["success"] = False
            
            # Only set manual controls if auto_exposure is off
            if not data.get('auto_exposure', camera.get_auto_exposure()):
                if 'exposure_time' in data:
                    if camera.set_exposure(int(data['exposure_time'])):
                        result["updated"].append("exposure_time")
                    else:
                        result["success"] = False
                
                if 'gain' in data:
                    if camera.set_gain(float(data['gain'])):
                        result["updated"].append("gain")
                    else:
                        result["success"] = False
            
            # Brightness and contrast can be set regardless of auto_exposure
            if 'brightness' in data:
                if camera.set_brightness(float(data['brightness'])):
                    result["updated"].append("brightness")
                else:
                    result["success"] = False
            
            if 'contrast' in data:
                if camera.set_contrast(float(data['contrast'])):
                    result["updated"].append("contrast")
                else:
                    result["success"] = False
            
            return jsonify(result)
        except Exception as e:
            logger.error(f"Error setting {camera_type} camera settings: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    # Fallback for unsupported methods (should not happen with Flask routing)
    return jsonify({"error": "Method not supported"}), 405

@app.route('/api/camera_auto_tune/<camera_type>', methods=['POST'])
def camera_auto_tune(camera_type):
    """Auto-tune camera settings using histogram analysis"""
    if camera_type not in ['ir', 'hq']:
        return jsonify({"error": "Invalid camera type"}), 400
    
    if not camera_manager:
        return jsonify({"error": "Camera manager not available"}), 503
    
    camera = camera_manager.ir_camera if camera_type == 'ir' else camera_manager.hq_camera
    if not camera or not camera.is_active():
        return jsonify({"error": f"{camera_type.upper()} camera not available"}), 503
    
    try:
        # Get parameters from request
        data = request.get_json() if request.is_json else {}
        quick_mode = data.get('quick_mode', True)
        is_day = data.get('is_day', None)
        
        # Auto-detect day/night if not specified
        if is_day is None:
            import datetime
            current_hour = datetime.datetime.now().hour
            is_day = 6 <= current_hour <= 20
        
        # Import auto-tuner
        from camera.auto_tuner import CameraAutoTuner
        auto_tuner = CameraAutoTuner()
        
        # Run auto-tuning
        logger.info(f"Starting auto-tuning for {camera_type} camera (day={is_day}, quick={quick_mode})")
        best_settings = auto_tuner.auto_tune_camera(camera, is_day=is_day, quick_mode=quick_mode)
        
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
                "mode": "day" if is_day else "night"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Auto-tuning failed to find optimal settings"
            }), 500
            
    except Exception as e:
        logger.error(f"Error auto-tuning {camera_type} camera: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/camera_dynamic_mode/<camera_type>', methods=['POST'])
def camera_dynamic_mode(camera_type):
    """Enable/disable dynamic exposure mode (continuous histogram-based optimization)"""
    if camera_type not in ['ir', 'hq']:
        return jsonify({"error": "Invalid camera type"}), 400
    
    if not camera_manager:
        return jsonify({"error": "Camera manager not available"}), 503
    
    try:
        data = request.get_json() if request.is_json else {}
        enabled = data.get('enabled', False)
        
        if enabled:
            # Start dynamic mode thread for the camera
            camera = camera_manager.ir_camera if camera_type == 'ir' else camera_manager.hq_camera
            if not camera or not camera.is_active():
                return jsonify({"error": f"{camera_type.upper()} camera not available"}), 503
            
            # Store dynamic mode state (would need to implement continuous optimization thread)
            # For now, just run a single auto-tune
            from camera.auto_tuner import CameraAutoTuner
            auto_tuner = CameraAutoTuner()
            
            import datetime
            current_hour = datetime.datetime.now().hour
            is_day = 6 <= current_hour <= 20
            
            logger.info(f"Enabling dynamic mode for {camera_type} camera")
            best_settings = auto_tuner.auto_tune_camera(camera, is_day=is_day, quick_mode=True)
            
            if best_settings:
                return jsonify({
                    "success": True,
                    "message": f"Dynamic mode enabled for {camera_type} camera",
                    "initial_settings": {
                        "exposure_time": best_settings.exposure_time,
                        "gain": best_settings.gain,
                        "brightness": best_settings.brightness,
                        "contrast": best_settings.contrast,
                        "score": best_settings.score
                    }
                })
            else:
                return jsonify({
                    "success": False,
                    "error": "Failed to initialize dynamic mode"
                }), 500
        else:
            # Disable dynamic mode
            logger.info(f"Disabling dynamic mode for {camera_type} camera")
            return jsonify({
                "success": True,
                "message": f"Dynamic mode disabled for {camera_type} camera"
            })
            
    except Exception as e:
        logger.error(f"Error setting dynamic mode for {camera_type} camera: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/camera_dynamic_exposure/<camera_type>', methods=['POST'])
def camera_dynamic_exposure(camera_type):
    """Apply dynamic exposure optimization (alias for dynamic_mode for compatibility)"""
    if camera_type not in ['ir', 'hq']:
        return jsonify({"error": "Invalid camera type"}), 400
    
    if not camera_manager:
        return jsonify({"error": "Camera manager not available"}), 503
    
    try:
        camera = camera_manager.ir_camera if camera_type == 'ir' else camera_manager.hq_camera
        if not camera or not camera.is_active():
            return jsonify({"error": f"{camera_type.upper()} camera not available"}), 503
        
        from camera.auto_tuner import CameraAutoTuner
        auto_tuner = CameraAutoTuner()
        
        import datetime
        current_hour = datetime.datetime.now().hour
        is_day = 6 <= current_hour <= 20
        
        logger.info(f"Applying dynamic exposure for {camera_type} camera")
        best_settings = auto_tuner.auto_tune_camera(camera, is_day=is_day, quick_mode=True)
        
        if best_settings:
            adjustment_msg = f"Optimized: exp={best_settings.exposure_time}μs, gain={best_settings.gain:.1f}, score={best_settings.score:.1f}"
            return jsonify({
                "success": True,
                "adjustment": adjustment_msg,
                "settings": {
                    "exposure_time": best_settings.exposure_time,
                    "gain": best_settings.gain,
                    "brightness": best_settings.brightness,
                    "contrast": best_settings.contrast,
                    "score": best_settings.score
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to apply dynamic exposure"
            }), 500
            
    except Exception as e:
        logger.error(f"Error applying dynamic exposure for {camera_type} camera: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/camera_fine_tune/<camera_type>', methods=['POST'])
def camera_fine_tune(camera_type):
    """Fine-tune current camera settings"""
    if camera_type not in ['ir', 'hq']:
        return jsonify({"error": "Invalid camera type"}), 400
    
    if not camera_manager:
        return jsonify({"error": "Camera manager not available"}), 503
    
    try:
        camera = camera_manager.ir_camera if camera_type == 'ir' else camera_manager.hq_camera
        if not camera or not camera.is_active():
            return jsonify({"error": f"{camera_type.upper()} camera not available"}), 503
        
        from camera.auto_tuner import CameraAutoTuner, CameraSettings
        auto_tuner = CameraAutoTuner()
        
        # Get current settings
        current_settings = CameraSettings(
            exposure_time=camera.get_exposure_time(),
            gain=camera.get_gain(),
            brightness=camera.get_brightness(),
            contrast=camera.get_contrast()
        )
        
        logger.info(f"Fine-tuning {camera_type} camera settings")
        improved_settings = auto_tuner.fine_tune_settings(camera, current_settings)
        
        if improved_settings:
            return jsonify({
                "success": True,
                "message": f"Fine-tuning complete for {camera_type} camera",
                "improvement": f"Score improved from {current_settings.score:.2f} to {improved_settings.score:.2f}",
                "settings": {
                    "exposure_time": improved_settings.exposure_time,
                    "gain": improved_settings.gain,
                    "brightness": improved_settings.brightness,
                    "contrast": improved_settings.contrast,
                    "score": improved_settings.score
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": "Fine-tuning failed"
            }), 500
            
    except Exception as e:
        logger.error(f"Error during fine-tuning for {camera_type} camera: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/auto_tracker/status')
def auto_tracker_status():
    """Get auto tracker status"""
    if auto_tracker:
        return jsonify(auto_tracker.get_status())
    else:
        return jsonify({"error": "Auto tracker not available"}), 503

@app.route('/api/auto_tracker/start', methods=['POST'])
def auto_tracker_start():
    """Start the auto tracker service"""
    if not auto_tracker:
        return jsonify({"error": "Auto tracker not available"}), 503
    
    try:
        if auto_tracker.start():
            logger.info("Auto tracker started via API")
            return jsonify({
                "success": True,
                "message": "Auto tracker started successfully"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to start auto tracker"
            }), 500
    except Exception as e:
        logger.error(f"Error starting auto tracker: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/auto_tracker/stop', methods=['POST'])
def auto_tracker_stop():
    """Stop the auto tracker service"""
    if not auto_tracker:
        return jsonify({"error": "Auto tracker not available"}), 503
    
    try:
        auto_tracker.stop()
        logger.info("Auto tracker stopped via API")
        return jsonify({
            "success": True,
            "message": "Auto tracker stopped successfully"
        })
    except Exception as e:
        logger.error(f"Error stopping auto tracker: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/auto_tracker/enable', methods=['POST'])
def auto_tracker_enable():
    """Enable or disable auto tracking (requires tracker to be started first)"""
    if not auto_tracker:
        return jsonify({"error": "Auto tracker not available"}), 503
    
    data = request.get_json() or {}
    enabled = data.get('enabled', True)
    
    try:
        # If enabling tracking but auto tracker isn't running, start it first
        if enabled and not auto_tracker.is_running():
            if not auto_tracker.start():
                return jsonify({
                    "success": False,
                    "error": "Failed to start auto tracker"
                }), 500
        
        auto_tracker.enable_tracking(enabled)
        return jsonify({
            "success": True,
            "enabled": enabled,
            "message": f"Auto tracking {'enabled' if enabled else 'disabled'}"
        })
    except Exception as e:
        logger.error(f"Error setting auto tracker state: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/auto_tracker/calibrate', methods=['POST'])
def auto_tracker_calibrate():
    """Manually calibrate camera correlation"""
    if not auto_tracker:
        return jsonify({"error": "Auto tracker not available"}), 503
    
    try:
        success = auto_tracker.calibrate_cameras()
        return jsonify({
            "success": success,
            "message": "Camera calibration " + ("successful" if success else "failed")
        })
    except Exception as e:
        logger.error(f"Error calibrating cameras: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/auto_tracker/settings', methods=['GET', 'POST'])
def auto_tracker_settings():
    """Get or set auto tracker settings"""
    if not auto_tracker:
        return jsonify({"error": "Auto tracker not available"}), 503
    
    if request.method == 'GET':
        # Get current settings
        return jsonify({
            "target_selection_mode": auto_tracker.target_selection_mode,
            "tracking_timeout": auto_tracker.tracking_timeout,
            "auto_calibration_enabled": auto_tracker.auto_calibration_enabled,
            "calibration_interval": auto_tracker.calibration_interval
        })
    
    elif request.method == 'POST':
        # Set new settings
        data = request.get_json() or {}
        result = {"success": True, "updated": []}
        
        if 'target_selection_mode' in data:
            auto_tracker.set_target_selection_mode(data['target_selection_mode'])
            result["updated"].append("target_selection_mode")
        
        if 'tracking_timeout' in data:
            auto_tracker.set_tracking_timeout(float(data['tracking_timeout']))
            result["updated"].append("tracking_timeout")
        
        if 'auto_calibration_enabled' in data:
            auto_tracker.auto_calibration_enabled = bool(data['auto_calibration_enabled'])
            result["updated"].append("auto_calibration_enabled")
        
        if 'calibration_interval' in data:
            auto_tracker.calibration_interval = int(data['calibration_interval'])
            result["updated"].append("calibration_interval")
        
        return jsonify(result)

@app.route('/api/camera/hq/roi', methods=['POST'])
def set_hq_camera_roi():
    """Set HQ camera region of interest for zooming"""
    if not camera_manager or not camera_manager.hq_camera:
        return jsonify({"error": "HQ camera not available"}), 503
    
    try:
        data = request.get_json()
        x = int(data['x'])
        y = int(data['y'])
        width = int(data['width'])
        height = int(data['height'])
        
        success = camera_manager.hq_camera.set_roi(x, y, width, height)
        
        if success:
            return jsonify({
                "success": True,
                "roi": {"x": x, "y": y, "width": width, "height": height}
            })
        else:
            return jsonify({"error": "Failed to set ROI"}), 500
            
    except Exception as e:
        logger.error(f"Error setting HQ camera ROI: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/camera/hq/roi/reset', methods=['POST'])
def reset_hq_camera_roi():
    """Reset HQ camera to full view"""
    if not camera_manager or not camera_manager.hq_camera:
        return jsonify({"error": "HQ camera not available"}), 503
    
    try:
        success = camera_manager.hq_camera.reset_roi()
        
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to reset ROI"}), 500
            
    except Exception as e:
        logger.error(f"Error resetting HQ camera ROI: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/camera/hq/roi', methods=['GET'])
def get_hq_camera_roi():
    """Get current HQ camera ROI"""
    if not camera_manager or not camera_manager.hq_camera:
        return jsonify({"error": "HQ camera not available"}), 503
    
    try:
        roi = camera_manager.hq_camera.get_roi()
        has_roi = camera_manager.hq_camera.has_roi()
        
        if has_roi and roi:
            x, y, width, height = roi
            return jsonify({
                "success": True,
                "active": True,
                "roi": {"x": x, "y": y, "width": width, "height": height}
            })
        else:
            return jsonify({
                "success": True,
                "active": False,
                "roi": None
            })
            
    except Exception as e:
        logger.error(f"Error getting HQ camera ROI: {e}")
        return jsonify({"error": str(e)}), 500

# DISABLED - Stacking functionality
# @app.route('/stacked_frame')
# def stacked_frame():
    """Get a single stacked frame (for desktop browser compatibility)"""
    import cv2
    import numpy as np
    
    try:
        camera_type = request.args.get('camera', 'ir')
        stack_count = int(request.args.get('count', 5))
        
        logger.info(f"Stacked frame request: camera={camera_type}, count={stack_count}")
        
        if image_processor and camera_manager:
            # Add current frames to processor
            if camera_manager.ir_camera and camera_manager.ir_camera.is_streaming():
                ir_frame = camera_manager.get_frame_ir()
                if ir_frame is not None:
                    image_processor.add_frame_to_stack('ir', ir_frame)
            
            if camera_manager.hq_camera and camera_manager.hq_camera.is_streaming():
                hq_frame = camera_manager.get_frame_hq()
                if hq_frame is not None:
                    image_processor.add_frame_to_stack('hq', hq_frame)
            
            # Generate stacked image
            stacked = image_processor.stack_images(camera_type, stack_count)
            
            if stacked is not None:
                # Stacked image should be in RGB format, convert to BGR for OpenCV JPEG encoding
                if len(stacked.shape) == 3 and stacked.shape[2] == 3:
                    stacked_bgr = cv2.cvtColor(stacked, cv2.COLOR_RGB2BGR)
                    success, buffer = cv2.imencode('.jpg', stacked_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    if success:
                        return Response(buffer.tobytes(), mimetype='image/jpeg')
        
        # Return a placeholder if no stacked image available
        placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(placeholder, f'Stacking {camera_type.upper()}...', (200, 240), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        success, buffer = cv2.imencode('.jpg', placeholder)
        if success:
            return Response(buffer.tobytes(), mimetype='image/jpeg')
        
    except Exception as e:
        logger.error(f"Error generating stacked frame: {e}")
    
    return "Stacked frame not available", 503

# DISABLED - Long exposure stacking functionality
# @app.route('/long_exposure_frame')
# def long_exposure_frame():
    """Get a single long exposure stacked frame"""
    import cv2
    import numpy as np
    
    try:
        camera_type = request.args.get('camera', 'ir')
        stack_count = int(request.args.get('count', 10))  # Default to more frames for long exposure
        
        logger.info(f"Long exposure frame request: camera={camera_type}, count={stack_count}")
        
        if image_processor and camera_manager:
            # Add current frames to processor
            if camera_manager.ir_camera and camera_manager.ir_camera.is_streaming():
                ir_frame = camera_manager.get_frame_ir()
                if ir_frame is not None:
                    image_processor.add_frame_to_stack('ir', ir_frame)
            
            if camera_manager.hq_camera and camera_manager.hq_camera.is_streaming():
                hq_frame = camera_manager.get_frame_hq()
                if hq_frame is not None:
                    image_processor.add_frame_to_stack('hq', hq_frame)
            
            # Generate long exposure stacked image
            stacked = image_processor.long_exposure_stack(camera_type, stack_count)
            
            if stacked is not None:
                # Stacked image should be in RGB format, convert to BGR for OpenCV JPEG encoding
                if len(stacked.shape) == 3 and stacked.shape[2] == 3:
                    stacked_bgr = cv2.cvtColor(stacked, cv2.COLOR_RGB2BGR)
                    success, buffer = cv2.imencode('.jpg', stacked_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    if success:
                        return Response(buffer.tobytes(), mimetype='image/jpeg')
        
        # Return a placeholder if no stacked image available
        placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(placeholder, f'Long Exposure {camera_type.upper()}...', (150, 240), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        success, buffer = cv2.imencode('.jpg', placeholder)
        if success:
            return Response(buffer.tobytes(), mimetype='image/jpeg')
        
    except Exception as e:
        logger.error(f"Error generating long exposure frame: {e}")
    
    return "Long exposure frame not available", 503
    import cv2
    import numpy as np
    
    try:
        camera_type = request.args.get('camera', 'ir')
        stack_count = int(request.args.get('count', 10))  # Default to more frames for long exposure
        
        logger.info(f"Long exposure frame request: camera={camera_type}, count={stack_count}")
        
        if image_processor and camera_manager:
            # Add current frames to processor
            if camera_manager.ir_camera and camera_manager.ir_camera.is_streaming():
                ir_frame = camera_manager.get_frame_ir()
                if ir_frame is not None:
                    image_processor.add_frame_to_stack('ir', ir_frame)
            
            if camera_manager.hq_camera and camera_manager.hq_camera.is_streaming():
                hq_frame = camera_manager.get_frame_hq()
                if hq_frame is not None:
                    image_processor.add_frame_to_stack('hq', hq_frame)
            
            # Generate long exposure stacked image
            stacked = image_processor.long_exposure_stack(camera_type, stack_count)
            
            if stacked is not None:
                # Stacked image should be in RGB format, convert to BGR for OpenCV JPEG encoding
                if len(stacked.shape) == 3 and stacked.shape[2] == 3:
                    stacked_bgr = cv2.cvtColor(stacked, cv2.COLOR_RGB2BGR)
                    success, buffer = cv2.imencode('.jpg', stacked_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    if success:
                        return Response(buffer.tobytes(), mimetype='image/jpeg')
        
        # Return a placeholder if no stacked image available
        placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(placeholder, f'Long Exposure {camera_type.upper()}...', (150, 240), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        success, buffer = cv2.imencode('.jpg', placeholder)
        if success:
            return Response(buffer.tobytes(), mimetype='image/jpeg')
        
    except Exception as e:
        logger.error(f"Error generating long exposure frame: {e}")
    
    return "Long exposure frame not available", 503

# DISABLED - Infinite exposure stacking functionality
# @app.route('/infinite_exposure_frame')
# def infinite_exposure_frame():
    """Get a single infinite exposure stacked frame using all available frames"""
    import cv2
    import numpy as np
    
    try:
        camera_type = request.args.get('camera', 'ir')
        
        logger.info(f"Infinite exposure frame request: camera={camera_type}")
        
        if image_processor and camera_manager:
            # Add current frames to processor
            if camera_manager.ir_camera and camera_manager.ir_camera.is_streaming():
                ir_frame = camera_manager.get_frame_ir()
                if ir_frame is not None:
                    image_processor.add_frame_to_stack('ir', ir_frame)
            
            if camera_manager.hq_camera and camera_manager.hq_camera.is_streaming():
                hq_frame = camera_manager.get_frame_hq()
                if hq_frame is not None:
                    image_processor.add_frame_to_stack('hq', hq_frame)
            
            # Generate infinite exposure stacked image
            stacked = image_processor.infinite_exposure_stack(camera_type)
            
            if stacked is not None:
                # Stacked image should be in RGB format, convert to BGR for OpenCV JPEG encoding
                if len(stacked.shape) == 3 and stacked.shape[2] == 3:
                    stacked_bgr = cv2.cvtColor(stacked, cv2.COLOR_RGB2BGR)
                    success, buffer = cv2.imencode('.jpg', stacked_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    if success:
                        return Response(buffer.tobytes(), mimetype='image/jpeg')
        
        # Return a placeholder if no stacked image available
        placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(placeholder, f'Infinite Exposure {camera_type.upper()}...', (120, 240), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        success, buffer = cv2.imencode('.jpg', placeholder)
        if success:
            return Response(buffer.tobytes(), mimetype='image/jpeg')
        
    except Exception as e:
        logger.error(f"Error generating infinite exposure frame: {e}")
    
    return "Infinite exposure frame not available", 503

def generate_frame_stream(camera_type):
    """Generate MJPEG stream from individual frames (fallback when streaming fails)"""
    import cv2
    import time
    import numpy as np
    
    def get_camera_frame():
        """Get frame from the specified camera"""
        if camera_type == 'ir' and camera_manager and camera_manager.ir_camera:
            return camera_manager.ir_camera.get_frame()
        elif camera_type == 'hq' and camera_manager and camera_manager.hq_camera:
            return camera_manager.hq_camera.get_frame()
        return None
    
    while True:
        try:
            frame = get_camera_frame()
            if frame is not None:
                # Encode frame as JPEG
                success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if success:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                else:
                    logger.warning(f"Failed to encode {camera_type} frame")
            else:
                # Send placeholder frame if no camera frame available
                placeholder = cv2.imread('static/placeholder.jpg')
                if placeholder is None:
                    # Create a simple placeholder
                    placeholder = 255 * np.ones((240, 320, 3), dtype=np.uint8)
                    cv2.putText(placeholder, f'{camera_type.upper()} Camera', (50, 120), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
                    cv2.putText(placeholder, 'Loading...', (100, 160), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
                
                success, buffer = cv2.imencode('.jpg', placeholder)
                if success:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            
            time.sleep(0.1)  # 10 FPS for frame-based streaming
            
        except Exception as e:
            logger.error(f"Error in frame stream generator for {camera_type}: {e}")
            time.sleep(1)  # Wait longer on error

# DISABLED - Stacked feed functionality
# @app.route('/stacked_feed')
# def stacked_feed():
    """Live streaming feed of stacked images"""
    # Get parameters outside the generator to avoid request context issues
    camera_type = request.args.get('camera', 'ir')
    stack_count = int(request.args.get('count', 5))
    
    def generate_stacked_stream():
        import cv2
        import time
        
        # Buffer to store last valid frame to prevent black flickers
        last_valid_frame = None
        frame_buffer = None
        
        while True:
            try:
                if image_processor and camera_manager:
                    # Add current frames to processor
                    if camera_manager.ir_camera and camera_manager.ir_camera.is_streaming():
                        ir_frame = camera_manager.get_frame_ir()
                        if ir_frame is not None:
                            # Ensure frame is in RGB format before adding to stack
                            if len(ir_frame.shape) == 3 and ir_frame.shape[2] == 3:
                                image_processor.add_frame_to_stack('ir', ir_frame)
                    
                    if camera_manager.hq_camera and camera_manager.hq_camera.is_streaming():
                        hq_frame = camera_manager.get_frame_hq()
                        if hq_frame is not None:
                            # Ensure frame is in RGB format before adding to stack
                            if len(hq_frame.shape) == 3 and hq_frame.shape[2] == 3:
                                image_processor.add_frame_to_stack('hq', hq_frame)
                    
                    # Generate stacked image
                    stacked = image_processor.stack_images(camera_type, stack_count)
                    
                    if stacked is not None:
                        # Stacked image should be in RGB format, convert to BGR for OpenCV JPEG encoding
                        if len(stacked.shape) == 3 and stacked.shape[2] == 3:
                            stacked_bgr = cv2.cvtColor(stacked, cv2.COLOR_RGB2BGR)
                            success, buffer = cv2.imencode('.jpg', stacked_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
                            if success:
                                frame_buffer = buffer.tobytes()
                                last_valid_frame = frame_buffer
                                yield (b'--frame\r\n'
                                       b'Content-Type: image/jpeg\r\n\r\n' + frame_buffer + b'\r\n')
                    
                    # If we have no new stacked image but have a last valid frame, use it
                    elif last_valid_frame is not None:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + last_valid_frame + b'\r\n')
                    
                    # If no frames at all, create a placeholder black frame
                    else:
                        # Create a black placeholder frame
                        placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
                        success, buffer = cv2.imencode('.jpg', placeholder, [cv2.IMWRITE_JPEG_QUALITY, 95])
                        if success:
                            frame_buffer = buffer.tobytes()
                            yield (b'--frame\r\n'
                                   b'Content-Type: image/jpeg\r\n\r\n' + frame_buffer + b'\r\n')
                
                # Control frame rate (3 FPS for stacked images - slightly faster)
                time.sleep(0.33)
                
            except Exception as e:
                logger.error(f"Error in stacked stream: {e}")
                time.sleep(1.0)
    
    return Response(generate_stacked_stream(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/stacked_frame')
def stacked_frame():
    """Server-side stacking disabled - use client-side stacking instead"""
    return "Server-side stacking disabled - use client-side JavaScript stacking", 404

@app.route('/long_exposure_frame')
def long_exposure_frame():
    """Server-side stacking disabled - use client-side stacking instead"""
    return "Server-side stacking disabled - use client-side JavaScript stacking", 404

@app.route('/infinite_exposure_frame')
def infinite_exposure_frame():
    """Server-side stacking disabled - use client-side stacking instead"""
    return "Server-side stacking disabled - use client-side JavaScript stacking", 404

@app.route('/stacked_feed')
def stacked_feed():
    """Server-side stacking disabled - use client-side stacking instead"""
    return "Server-side stacking disabled - use client-side JavaScript stacking", 404

@app.route('/aligned_frame')
def aligned_frame():
    """Get feature-aligned camera frames (placeholder)"""
    import cv2
    import numpy as np
    
    try:
        # Create a simple placeholder since alignment is disabled
        placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(placeholder, 'Feature Alignment', (200, 200), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (100, 100, 100), 2)
        cv2.putText(placeholder, 'Disabled for Compatibility', (150, 250), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 100), 2)
        
        success, buffer = cv2.imencode('.jpg', placeholder)
        if success:
            return Response(buffer.tobytes(), mimetype='image/jpeg')
        
    except Exception as e:
        logger.error(f"Error generating aligned frame placeholder: {e}")
    
    return "Aligned frame not available", 503

# DISABLED - Aligned frame functionality
# @app.route('/aligned_frame')
# def aligned_frame():
    """Get feature-aligned camera frames"""
    if image_processor and camera_manager:
        # Add current frames to processor
        if camera_manager.ir_camera and camera_manager.ir_camera.is_streaming():
            ir_frame = camera_manager.get_frame_ir()
            if ir_frame is not None:
                image_processor.add_frame_to_stack('ir', ir_frame)
        
        if camera_manager.hq_camera and camera_manager.hq_camera.is_streaming():
            hq_frame = camera_manager.get_frame_hq()
            if hq_frame is not None:
                image_processor.add_frame_to_stack('hq', hq_frame)
        
        # Get alignment parameters
        method = request.args.get('method', 'orb')
        show_features = request.args.get('show_features', 'false').lower() == 'true'
        
        # Generate aligned image
        aligned = image_processor.align_cameras(method, show_features)
        
        if aligned is not None:
            import cv2
            # Aligned image should be in RGB format, convert to BGR for OpenCV JPEG encoding
            if len(aligned.shape) == 3 and aligned.shape[2] == 3:
                aligned_bgr = cv2.cvtColor(aligned, cv2.COLOR_RGB2BGR)
            else:
                aligned_bgr = aligned
            success, buffer = cv2.imencode('.jpg', aligned_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
            if success:
                return Response(buffer.tobytes(), mimetype='image/jpeg')
    
    return "Aligned frame not available", 503

@app.route('/save_stacked_image', methods=['POST'])
def save_stacked_image():
    """Save a stacked image to disk"""
    if not image_processor:
        return jsonify({"success": False, "error": "Image processor not available"})
    
    try:
        from datetime import datetime
        import os
        
        # Get parameters from request
        data = request.get_json()
        camera_type = data.get('camera_type', 'ir')
        stack_count = data.get('stack_count', 5)
        
        # Ensure detections directory exists
        os.makedirs('detections', exist_ok=True)
        
        stacked = image_processor.stack_images(camera_type, stack_count)
        
        if stacked is not None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"stacked_{camera_type}_{timestamp}.jpg"
            filepath = os.path.join('detections', filename)
            
            import cv2
            cv2.imwrite(filepath, stacked)
            
            return jsonify({"success": True, "filename": filename, "camera_type": camera_type})
        else:
            return jsonify({"success": False, "error": f"No stacked image available for {camera_type} camera"})
    except Exception as e:
        logger.error(f"Error saving stacked image: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/save_aligned_image', methods=['POST'])
def save_aligned_image():
    """Save current aligned image"""
    if image_processor:
        try:
            from datetime import datetime
            import os
            
            # Ensure detections directory exists
            os.makedirs('detections', exist_ok=True)
            
            data = request.get_json() or {}
            method = data.get('method', 'orb')
            show_features = data.get('show_features', False)
            
            aligned = image_processor.align_cameras(method, show_features)
            
            if aligned is not None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"aligned_{method}_{timestamp}.jpg"
                filepath = os.path.join('detections', filename)
                
                import cv2
                cv2.imwrite(filepath, aligned)
                
                return jsonify({"success": True, "filename": filename})
            else:
                return jsonify({"success": False, "error": "No aligned image available"})
                
        except Exception as e:
            logger.error(f"Error saving aligned image: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    return jsonify({"success": False, "error": "Image processor not available"})

@app.route('/api/image_processor_status')
def image_processor_status():
    """Get image processor status"""
    if image_processor:
        return jsonify(image_processor.get_stack_info())
    else:
        return jsonify({"error": "Image processor not available"})

@app.route('/api/detection_images')
def detection_images():
    """Get list of detection images"""
    try:
        import os
        from pathlib import Path
        
        detections_dir = "/home/mark/ufo-tracker/detections"
        if not os.path.exists(detections_dir):
            return jsonify({"images": []})
        
        images = []
        for filename in os.listdir(detections_dir):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                filepath = os.path.join(detections_dir, filename)
                stat = os.stat(filepath)
                
                # Parse image type from filename
                image_type = "unknown"
                if filename.startswith("detection_"):
                    image_type = "motion_detection"
                elif filename.startswith("stacked_"):
                    image_type = "stacked"
                elif filename.startswith("aligned_"):
                    image_type = "aligned"
                
                images.append({
                    "filename": filename,
                    "type": image_type,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "url": f"/detection_image/{filename}"
                })
        
        # Sort by modification time (newest first)
        images.sort(key=lambda x: x["modified"], reverse=True)
        
        return jsonify({"images": images})
        
    except Exception as e:
        logger.error(f"Error listing detection images: {e}")
        return jsonify({"error": str(e)})

@app.route('/detection_image/<filename>')
def serve_detection_image(filename):
    """Serve a detection image"""
    try:
        import os
        from flask import send_file
        
        # Security: ensure filename doesn't contain path traversal
        if '..' in filename or '/' in filename:
            return "Invalid filename", 400
        
        detections_dir = "/home/mark/ufo-tracker/detections"
        filepath = os.path.join(detections_dir, filename)
        
        if not os.path.exists(filepath):
            return "Image not found", 404
        
        return send_file(filepath, mimetype='image/jpeg')
        
    except Exception as e:
        logger.error(f"Error serving detection image {filename}: {e}")
        return "Server error", 500

@app.route('/api/delete_detection_image/<filename>', methods=['DELETE'])
def delete_detection_image(filename):
    """Delete a detection image"""
    try:
        import os
        
        # Security: ensure filename doesn't contain path traversal
        if '..' in filename or '/' in filename:
            return jsonify({"success": False, "error": "Invalid filename"})
        
        detections_dir = "/home/mark/ufo-tracker/detections"
        filepath = os.path.join(detections_dir, filename)
        
        if not os.path.exists(filepath):
            return jsonify({"success": False, "error": "Image not found"})
        
        os.remove(filepath)
        return jsonify({"success": True, "message": f"Deleted {filename}"})
        
    except Exception as e:
        logger.error(f"Error deleting detection image {filename}: {e}")
        return jsonify({"success": False, "error": str(e)}), 503

@app.route('/api/clear_all_detection_images', methods=['DELETE'])
def clear_all_detection_images():
    """Delete all detection images"""
    try:
        import os
        import glob
        
        detections_dir = "/home/mark/ufo-tracker/detections"
        
        # Get all jpg files in detections directory
        pattern = os.path.join(detections_dir, "*.jpg")
        image_files = glob.glob(pattern)
        
        deleted_count = 0
        for filepath in image_files:
            try:
                os.remove(filepath)
                deleted_count += 1
            except Exception as e:
                logger.error(f"Error deleting {filepath}: {e}")
        
        return jsonify({
            "success": True, 
            "message": f"Deleted {deleted_count} detection images"
        })
        
    except Exception as e:
        logger.error(f"Error clearing all detection images: {e}")
        return jsonify({"success": False, "error": str(e)}), 503

# ============= CAPTURE ENDPOINTS =============

@app.route('/api/capture/<camera_type>', methods=['POST'])
def api_capture_frame(camera_type):
    """Capture a single frame from the specified camera"""
    try:
        from datetime import datetime
        import os
        
        # Validate camera type
        if camera_type not in ['ir', 'hq']:
            return jsonify({
                'success': False,
                'error': 'Invalid camera type. Use "ir" or "hq"'
            }), 400
        
        # Get the appropriate camera
        camera = None
        if camera_type == 'ir':
            camera = camera_manager.ir_camera
        else:
            camera = camera_manager.hq_camera
        
        if not camera or not camera.is_active():
            return jsonify({
                'success': False,
                'error': f'{camera_type.upper()} camera not available'
            }), 503
        
        # Get a frame from the camera
        frame = camera.get_frame()
        if frame is None:
            return jsonify({
                'success': False,
                'error': 'Failed to capture frame'
            }), 500
        
        # Save to gallery/images directory
        save_path = 'static/gallery/images'
        os.makedirs(save_path, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'{camera_type}_capture_{timestamp}.jpg'
        filepath = os.path.join(save_path, filename)
        
        # Save the frame
        success = cv2.imwrite(filepath, frame)
        
        if success:
            logger.info(f"Captured frame from {camera_type} camera: {filename}")
            return jsonify({
                'success': True,
                'filename': filename,
                'path': filepath,
                'message': f'Image captured successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save image'
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
        
        # Save to gallery/stacks directory
        save_path = 'static/gallery/stacks'
        os.makedirs(save_path, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'stacked_{camera_type}_{timestamp}.jpg'
        filepath = os.path.join(save_path, filename)
        
        # Save the image
        with open(filepath, 'wb') as f:
            f.write(image_bytes)
        
        logger.info(f"Saved stacked image: {filename}")
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
        
        # Handle filenames with subdirectory (e.g., "stacks/image.jpg")
        if '/' in filename:
            # Split into directory and filename
            parts = filename.split('/')
            if len(parts) == 2:
                subdir = parts[0]
                file = parts[1]
                # Get the absolute base directory of the app
                base_dir = os.path.dirname(os.path.abspath(__file__))
                
                # Only allow known subdirectories
                if subdir in ['images', 'stacks', 'detections']:
                    filepath = os.path.join(base_dir, 'static/gallery', subdir, file)
                    if not os.path.exists(filepath):
                        # Try without base_dir
                        filepath = os.path.join('static/gallery', subdir, file)
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Invalid directory'
                    }), 400
            else:
                return jsonify({
                    'success': False,
                    'error': 'Invalid path format'
                }), 400
        else:
            # Get the absolute base directory of the app
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Try multiple locations for backward compatibility
            possible_paths = [
                os.path.join(base_dir, 'static/gallery/images', filename),
                os.path.join(base_dir, 'static/gallery/stacks', filename),
                os.path.join(base_dir, 'detections', filename),
                os.path.join(base_dir, Config.STORAGE['save_path'], filename),
                # Also try relative paths in case app is running from correct directory
                os.path.join('static/gallery/images', filename),
                os.path.join('static/gallery/stacks', filename),
                os.path.join('detections', filename),
            ]
            
            logger.info(f"Searching for file '{filename}' in directories...")
            logger.info(f"Current working directory: {os.getcwd()}")
            logger.info(f"App base directory: {base_dir}")
            
            filepath = None
            for path in possible_paths:
                abs_path = os.path.abspath(path)
                logger.info(f"Checking path: {abs_path} - exists: {os.path.exists(abs_path)}")
                if os.path.exists(abs_path):
                    filepath = abs_path
                    logger.info(f"Found file at: {filepath}")
                    break
            
            if not filepath:
                logger.error(f"File not found in any gallery directory: {filename}")
                logger.error(f"Searched paths: {possible_paths}")
                return jsonify({
                    'success': False,
                    'error': 'File not found - check server logs'
                }), 404
        
        # Final check if file exists
        if filepath and not os.path.exists(filepath):
            logger.error(f"File not found at final check: {filepath}")
            return jsonify({
                'success': False,
                'error': 'File not found at final check'
            }), 404
        
        if not filepath:
            return jsonify({
                'success': False,
                'error': 'File path not determined'
            }), 404
        
        # Delete the file
        os.remove(filepath)
        logger.info(f"Deleted gallery image: {filepath}")
        
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

# ============= TIMELAPSE ENDPOINTS (DISABLED) =============

@app.route('/api/timelapses')
def list_timelapses():
    """Timelapse feature disabled"""
    return jsonify({"error": "Timelapse feature disabled"}), 404

@app.route('/api/create_timelapse', methods=['POST'])
def create_timelapse():
    """Timelapse feature disabled"""
    return jsonify({"error": "Timelapse feature disabled"}), 404

@app.route('/api/delete_timelapse/<filename>', methods=['DELETE'])
def delete_timelapse(filename):
    """Timelapse feature disabled"""
    return jsonify({"error": "Timelapse feature disabled"}), 404

@app.route('/timelapse/<filename>')
def serve_timelapse(filename):
    """Timelapse feature disabled"""
    return "Timelapse feature disabled", 404

@app.route('/timelapse/thumbnails/<filename>')
def serve_timelapse_thumbnail(filename):
    """Timelapse feature disabled"""
    return "Timelapse feature disabled", 404

@app.route('/api/cleanup_timelapses', methods=['POST'])
def cleanup_timelapses():
    """Timelapse feature disabled"""
    return jsonify({"error": "Timelapse feature disabled"}), 404

@app.route('/favicon.ico')
def favicon():
    """Return empty favicon to prevent 404 errors"""
    return Response(status=204)

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return render_template('error.html', error="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}")
    return render_template('error.html', error="Internal server error"), 500

def cleanup():
    """Cleanup function called on shutdown"""
    logger.info("Shutting down UFO Tracker...")
    
    if auto_tracker:
        auto_tracker.cleanup()
    
    if motion_detector:
        motion_detector.stop()
    
    if image_processor:
        image_processor.clear_stacks()
    
    if camera_manager:
        camera_manager.cleanup()
    
    if pan_tilt:
        pan_tilt.cleanup()

if __name__ == '__main__':
    try:
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        # Initialize components
        initialize_components()
        
        logger.info("Starting UFO Tracker application...")
        
        # Run the Flask app with threading for multiple users
        app.run(
            host=Config.HOST,
            port=Config.PORT,
            debug=Config.DEBUG,
            threaded=True,
            processes=1,
            use_reloader=False,
            use_debugger=False
        )
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Application error: {e}")
    finally:
        cleanup()
