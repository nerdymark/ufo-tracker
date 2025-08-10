#!/usr/bin/env python3
"""
UFO Tracker - Camera Streaming Service
Dedicated service for camera streaming to avoid blocking API calls
"""

import logging
import os
import sys
import time
import threading
from flask import Flask, Response, jsonify, request
from config.config import Config

# Setup logging
logging.basicConfig(
    level=getattr(logging, Config.LOGGING['level']),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY

# Global camera manager
camera_manager = None
ir_camera = None
hq_camera = None

# Frame capture thread
frame_capture_thread = None
frame_capture_running = False

# Fixed paths for latest frames
IR_FRAME_PATH = '/home/mark/ufo-tracker/temp/ir_latest.jpg'
HQ_FRAME_PATH = '/home/mark/ufo-tracker/temp/hq_latest.jpg'

def periodic_frame_capture():
    """Periodically capture frames from cameras and save to temp files"""
    global frame_capture_running, ir_camera, hq_camera
    
    # Ensure temp directory exists
    os.makedirs('/home/mark/ufo-tracker/temp', exist_ok=True)
    
    logger.info("Starting periodic frame capture thread")
    
    import cv2
    
    while frame_capture_running:
        try:
            # Capture IR frame
            if ir_camera and ir_camera.is_active():
                try:
                    # Capture to a temp file with .jpg extension
                    temp_ir_path = IR_FRAME_PATH.replace('.jpg', '_tmp.jpg')
                    ir_camera._camera.capture_file(temp_ir_path)
                    
                    # No color conversion needed - Picamera2 output is already correct for web display
                    
                    # Atomic move to avoid partial reads
                    os.rename(temp_ir_path, IR_FRAME_PATH)
                    logger.debug("Captured IR frame")
                except Exception as e:
                    logger.error(f"Error capturing IR frame: {e}")
            
            # Capture HQ frame
            if hq_camera and hq_camera.is_active():
                try:
                    # Capture to a temp file with .jpg extension
                    temp_hq_path = HQ_FRAME_PATH.replace('.jpg', '_tmp.jpg')
                    hq_camera._camera.capture_file(temp_hq_path)
                    
                    # No color conversion needed - Picamera2 output is already correct for web display
                    
                    # Atomic move to avoid partial reads
                    os.rename(temp_hq_path, HQ_FRAME_PATH)
                    logger.debug("Captured HQ frame")
                except Exception as e:
                    logger.error(f"Error capturing HQ frame: {e}")
            
            # Wait before next capture - 2 frames per second (0.5 second intervals)
            time.sleep(0.5)  # Capture 2 frames per second
            
        except Exception as e:
            logger.error(f"Error in periodic frame capture: {e}")
            time.sleep(1)
    
    logger.info("Periodic frame capture thread stopped")

def initialize_cameras():
    """Initialize cameras using auto-detection camera manager"""
    global camera_manager, ir_camera, hq_camera, frame_capture_thread, frame_capture_running
    
    try:
        from camera.camera_manager import CameraManager
        camera_manager = CameraManager()
        
        # Get references to individual cameras for compatibility
        ir_camera = camera_manager.ir_camera
        hq_camera = camera_manager.hq_camera
        
        # Start streaming immediately after initialization
        camera_manager.start_streaming()
        logger.info("Camera manager initialized with auto-detection and streaming started")
        
        # Log detected assignments
        assignments = camera_manager.get_detected_camera_assignments()
        logger.info(f"Camera assignments: IR=index {assignments['ir_camera']['index']}, HQ=index {assignments['hq_camera']['index']}")
        
        # Start periodic frame capture thread
        frame_capture_running = True
        frame_capture_thread = threading.Thread(target=periodic_frame_capture, daemon=True)
        frame_capture_thread.start()
        logger.info("Started periodic frame capture thread")
        
    except Exception as e:
        logger.error(f"Failed to initialize camera manager: {e}")
        camera_manager = None
        ir_camera = None
        hq_camera = None

def cleanup_cameras():
    """Cleanup camera resources"""
    global camera_manager, ir_camera, hq_camera, frame_capture_running, frame_capture_thread
    
    # Stop frame capture thread
    frame_capture_running = False
    if frame_capture_thread and frame_capture_thread.is_alive():
        frame_capture_thread.join(timeout=2)
        logger.info("Frame capture thread stopped")
    
    if camera_manager:
        try:
            camera_manager.cleanup()
            logger.info("Camera manager cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up camera manager: {e}")
    
    camera_manager = None
    ir_camera = None
    hq_camera = None

# Old stream generators removed - now using camera streaming objects directly

# Camera streaming endpoints
@app.route('/ir_feed')
def ir_feed():
    """IR camera MJPEG stream endpoint"""
    if not ir_camera or not ir_camera.is_active():
        return jsonify({'error': 'IR camera not available'}), 503
    
    # Use the camera's streaming object directly
    stream = ir_camera.get_stream()
    response = Response(stream, mimetype='multipart/x-mixed-replace; boundary=frame')
    response.headers['Connection'] = 'close'
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,OPTIONS'
    return response

@app.route('/hq_feed')
def hq_feed():
    """HQ camera MJPEG stream endpoint"""
    if not hq_camera or not hq_camera.is_active():
        return jsonify({'error': 'HQ camera not available'}), 503
    
    # Use the camera's streaming object directly
    stream = hq_camera.get_stream()
    response = Response(stream, mimetype='multipart/x-mixed-replace; boundary=frame')
    response.headers['Connection'] = 'close'
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,OPTIONS'
    return response

@app.route('/ir_frame')
def ir_frame():
    """Single IR camera frame as JPEG with proper colorspace conversion"""
    try:
        if ir_camera and ir_camera.is_active():
            import tempfile
            import os
            import cv2
            
            # Create temporary file for capture
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                temp_filename = temp_file.name
            
            try:
                # Capture still image to file
                ir_camera._camera.capture_file(temp_filename)
                
                # Fix colorspace: load, convert, and re-save
                img = cv2.imread(temp_filename)
                if img is not None:
                    # OpenCV loads as BGR, but Picamera2 saved as RGB interpreted as BGR
                    # So we need to convert BGR->RGB to fix the swapped channels
                    img_fixed = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    # Encode to JPEG
                    success, buffer = cv2.imencode('.jpg', img_fixed, [cv2.IMWRITE_JPEG_QUALITY, 90])
                    if success:
                        image_data = buffer.tobytes()
                    else:
                        # Fallback to original file if conversion fails
                        with open(temp_filename, 'rb') as f:
                            image_data = f.read()
                else:
                    # Fallback to original file if loading fails
                    with open(temp_filename, 'rb') as f:
                        image_data = f.read()
                
                response = Response(image_data, mimetype='image/jpeg')
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
                response.headers['Access-Control-Allow-Origin'] = '*'
                response.headers['Connection'] = 'close'
                return response
                
            finally:
                # Clean up temp file
                if os.path.exists(temp_filename):
                    os.unlink(temp_filename)
                    
    except Exception as e:
        logger.error(f"Error serving IR frame: {e}")
    
    return Response("IR camera frame not available", status=503, mimetype='text/plain')

@app.route('/hq_frame')
def hq_frame():
    """Single HQ camera frame as JPEG with proper colorspace conversion"""
    try:
        if hq_camera and hq_camera.is_active():
            import tempfile
            import os
            import cv2
            
            # Create temporary file for capture
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                temp_filename = temp_file.name
            
            try:
                # Capture still image to file
                hq_camera._camera.capture_file(temp_filename)
                
                # Fix colorspace: load, convert, and re-save
                img = cv2.imread(temp_filename)
                if img is not None:
                    # OpenCV loads as BGR, but Picamera2 saved as RGB interpreted as BGR
                    # So we need to convert BGR->RGB to fix the swapped channels
                    img_fixed = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    # Encode to JPEG
                    success, buffer = cv2.imencode('.jpg', img_fixed, [cv2.IMWRITE_JPEG_QUALITY, 90])
                    if success:
                        image_data = buffer.tobytes()
                    else:
                        # Fallback to original file if conversion fails
                        with open(temp_filename, 'rb') as f:
                            image_data = f.read()
                else:
                    # Fallback to original file if loading fails
                    with open(temp_filename, 'rb') as f:
                        image_data = f.read()
                
                response = Response(image_data, mimetype='image/jpeg')
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
                response.headers['Access-Control-Allow-Origin'] = '*'
                response.headers['Connection'] = 'close'
                return response
                
            finally:
                # Clean up temp file
                if os.path.exists(temp_filename):
                    os.unlink(temp_filename)
                    
    except Exception as e:
        logger.error(f"Error serving HQ frame: {e}")
    
    return Response("HQ camera frame not available", status=503, mimetype='text/plain')

@app.route('/api/camera_settings/<camera>', methods=['GET', 'POST'])
def camera_settings(camera):
    """Camera settings endpoint"""
    global ir_camera, hq_camera
    
    # Get the appropriate camera object
    camera_obj = None
    if camera == 'ir' and ir_camera:
        camera_obj = ir_camera
    elif camera == 'hq' and hq_camera:
        camera_obj = hq_camera
    else:
        return jsonify({'error': f'Camera {camera} not available'}), 404
    
    try:
        if request.method == 'GET':
            # Get current settings
            if hasattr(camera_obj, 'get_settings'):
                settings = camera_obj.get_settings()
                return jsonify(settings)
            else:
                # Return default settings if get_settings not implemented
                return jsonify({
                    'camera': camera,
                    'auto_exposure': True,
                    'exposure_time': 33000,
                    'gain': 4.0,
                    'brightness': 0.0,
                    'contrast': 1.0
                })
        
        elif request.method == 'POST':
            # Apply new settings
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No JSON data provided'}), 400
            
            success_count = 0
            total_settings = 0
            applied_settings = {}
            failed_settings = []
            
            # Map frontend setting names to camera method names
            setting_mapping = {
                'exposure_time': 'exposure',
                'auto_exposure': 'auto_exposure',
                'gain': 'gain',
                'brightness': 'brightness',
                'contrast': 'contrast'
            }
            
            # Try batch application first for better camera stability
            if hasattr(camera_obj, 'apply_settings_batch'):
                try:
                    result = camera_obj.apply_settings_batch(data)
                    if result:
                        # Batch application successful
                        success_count = len(data)
                        total_settings = len(data)
                        applied_settings = data.copy()
                        logger.info(f"Applied batch settings to {camera} camera: {data}")
                    else:
                        # Fall back to individual settings
                        raise Exception("Batch application failed")
                except Exception as e:
                    logger.warning(f"Batch settings failed for {camera}, falling back to individual: {e}")
                    # Fall through to individual settings application
            
            # Individual settings application (fallback or if batch not supported)
            if success_count == 0:
                for setting, value in data.items():
                    total_settings += 1
                    try:
                        # Map frontend setting name to camera method name
                        method_name = setting_mapping.get(setting, setting)
                        
                        if hasattr(camera_obj, 'set_' + method_name):
                            method = getattr(camera_obj, 'set_' + method_name)
                            result = method(value)
                            if result is not False:  # Some methods return None for success
                                applied_settings[setting] = value
                                success_count += 1
                                logger.info(f"Applied {camera} {setting}={value}")
                            else:
                                failed_settings.append(f"{setting} (method returned False)")
                        else:
                            failed_settings.append(f"{setting} (method set_{method_name} not found)")
                            logger.warning(f"Method set_{method_name} not found for {camera} camera")
                    except Exception as e:
                        failed_settings.append(f"{setting} (error: {str(e)})")
                        logger.error(f"Failed to apply {camera} {setting}={value}: {e}")
            
            # Return results
            if success_count == total_settings:
                return jsonify({
                    'success': True,
                    'message': f'All settings applied successfully',
                    'applied': applied_settings
                })
            elif success_count > 0:
                return jsonify({
                    'success': True,
                    'message': f'Applied {success_count}/{total_settings} settings',
                    'applied': applied_settings,
                    'failed': failed_settings
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Failed to apply any settings',
                    'failed': failed_settings
                }), 500
    
    except Exception as e:
        logger.error(f"Error in camera_settings for {camera}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/camera_dynamic_exposure/<camera>', methods=['POST'])
def dynamic_exposure(camera):
    """Apply dynamic exposure based on histogram analysis"""
    global ir_camera, hq_camera
    
    # Get the appropriate camera object
    camera_obj = None
    if camera == 'ir' and ir_camera:
        camera_obj = ir_camera
    elif camera == 'hq' and hq_camera:
        camera_obj = hq_camera
    else:
        return jsonify({'error': f'Camera {camera} not available'}), 404
    
    try:
        if hasattr(camera_obj, 'apply_dynamic_exposure'):
            result = camera_obj.apply_dynamic_exposure()
            return jsonify(result)
        else:
            return jsonify({'error': 'Dynamic exposure not supported for this camera'}), 400
    except Exception as e:
        logger.error(f"Error applying dynamic exposure for {camera}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/camera_day_mode/<camera>', methods=['POST'])
def day_mode(camera):
    """Set camera to day mode"""
    global ir_camera, hq_camera
    
    # Get the appropriate camera object
    camera_obj = None
    if camera == 'ir' and ir_camera:
        camera_obj = ir_camera
    elif camera == 'hq' and hq_camera:
        camera_obj = hq_camera
    else:
        return jsonify({'error': f'Camera {camera} not available'}), 404
    
    try:
        if hasattr(camera_obj, 'set_day_mode'):
            result = camera_obj.set_day_mode()
            return jsonify(result)
        else:
            return jsonify({'error': 'Day mode not supported for this camera'}), 400
    except Exception as e:
        logger.error(f"Error setting day mode for {camera}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/camera_night_mode/<camera>', methods=['POST'])
def night_mode(camera):
    """Set camera to night mode"""
    global ir_camera, hq_camera
    
    # Get the appropriate camera object
    camera_obj = None
    if camera == 'ir' and ir_camera:
        camera_obj = ir_camera
    elif camera == 'hq' and hq_camera:
        camera_obj = hq_camera
    else:
        return jsonify({'error': f'Camera {camera} not available'}), 404
    
    try:
        if hasattr(camera_obj, 'set_night_mode'):
            result = camera_obj.set_night_mode()
            return jsonify(result)
        else:
            return jsonify({'error': 'Night mode not supported for this camera'}), 400
    except Exception as e:
        logger.error(f"Error setting night mode for {camera}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/camera_restart_streaming/<camera>', methods=['POST'])
def restart_streaming(camera):
    """Restart camera streaming to recover from bad states"""
    global ir_camera, hq_camera
    
    # Get the appropriate camera object
    camera_obj = None
    if camera == 'ir' and ir_camera:
        camera_obj = ir_camera
    elif camera == 'hq' and hq_camera:
        camera_obj = hq_camera
    else:
        return jsonify({'error': f'Camera {camera} not available'}), 404
    
    try:
        if hasattr(camera_obj, 'restart_streaming'):
            result = camera_obj.restart_streaming()
            if result:
                return jsonify({
                    'success': True,
                    'message': f'{camera.upper()} camera streaming restarted successfully'
                })
            else:
                return jsonify({'error': 'Failed to restart streaming'}), 500
        else:
            return jsonify({'error': 'Restart streaming not supported for this camera'}), 400
    except Exception as e:
        logger.error(f"Error restarting streaming for {camera}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'service': 'camera-streaming',
        'cameras': {
            'ir_available': ir_camera is not None,
            'hq_available': hq_camera is not None
        }
    })

if __name__ == '__main__':
    try:
        logger.info("Starting UFO Tracker Camera Streaming Service...")
        
        # Initialize cameras
        initialize_cameras()
        
        # Start Flask app on port 5001
        app.run(
            host=Config.HOST,
            port=5001,
            debug=False,
            threaded=True,
            processes=1
        )
        
    except KeyboardInterrupt:
        logger.info("Camera service stopped by user")
    except Exception as e:
        logger.error(f"Camera service error: {e}")
    finally:
        cleanup_cameras()