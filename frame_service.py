#!/usr/bin/env python3
"""
UFO Tracker - Frame Service
Lightweight service dedicated only to serving single frames (port 5002)
Separate from streaming service (port 5001) to avoid browser connection limits
Serves frames that are periodically captured by the camera service
"""

import logging
import os
from flask import Flask, Response, send_file
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

# Fixed paths for latest frames (must match camera_service.py)
IR_FRAME_PATH = '/home/mark/ufo-tracker/temp/ir_latest.jpg'
HQ_FRAME_PATH = '/home/mark/ufo-tracker/temp/hq_latest.jpg'

@app.route('/ir_frame')
def ir_frame():
    """Serve the latest IR camera frame"""
    try:
        if os.path.exists(IR_FRAME_PATH):
            # Get file modification time for cache control
            mtime = os.path.getmtime(IR_FRAME_PATH)
            
            response = send_file(
                IR_FRAME_PATH,
                mimetype='image/jpeg',
                as_attachment=False,
                download_name='ir_frame.jpg'
            )
            
            # Add headers for no caching
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Last-Modified'] = str(mtime)
            
            return response
        else:
            logger.warning(f"IR frame not found at {IR_FRAME_PATH}")
            return Response("IR camera frame not available", status=503, mimetype='text/plain')
            
    except Exception as e:
        logger.error(f"Error serving IR frame: {e}")
        return Response("IR camera frame error", status=503, mimetype='text/plain')

@app.route('/hq_frame')
def hq_frame():
    """Serve the latest HQ camera frame"""
    try:
        if os.path.exists(HQ_FRAME_PATH):
            # Get file modification time for cache control
            mtime = os.path.getmtime(HQ_FRAME_PATH)
            
            response = send_file(
                HQ_FRAME_PATH,
                mimetype='image/jpeg',
                as_attachment=False,
                download_name='hq_frame.jpg'
            )
            
            # Add headers for no caching
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Last-Modified'] = str(mtime)
            
            return response
        else:
            logger.warning(f"HQ frame not found at {HQ_FRAME_PATH}")
            return Response("HQ camera frame not available", status=503, mimetype='text/plain')
            
    except Exception as e:
        logger.error(f"Error serving HQ frame: {e}")
        return Response("HQ camera frame error", status=503, mimetype='text/plain')

@app.route('/health')
def health_check():
    """Health check endpoint"""
    ir_exists = os.path.exists(IR_FRAME_PATH)
    hq_exists = os.path.exists(HQ_FRAME_PATH)
    
    # Check how recent the frames are
    ir_age = None
    hq_age = None
    
    if ir_exists:
        try:
            import time
            ir_age = time.time() - os.path.getmtime(IR_FRAME_PATH)
        except:
            pass
    
    if hq_exists:
        try:
            import time
            hq_age = time.time() - os.path.getmtime(HQ_FRAME_PATH)
        except:
            pass
    
    return {
        'status': 'ok',
        'service': 'frame-service',
        'ir_frame_available': ir_exists,
        'hq_frame_available': hq_exists,
        'ir_frame_age_seconds': ir_age,
        'hq_frame_age_seconds': hq_age
    }

if __name__ == '__main__':
    try:
        logger.info("Starting UFO Tracker Frame Service on port 5002...")
        logger.info(f"Serving frames from: IR={IR_FRAME_PATH}, HQ={HQ_FRAME_PATH}")
        
        # Ensure temp directory exists
        os.makedirs('/home/mark/ufo-tracker/temp', exist_ok=True)
        
        # Run Flask app on port 5002 (separate from streaming service on 5001)
        app.run(
            host='0.0.0.0',
            port=5002,
            debug=False,
            threaded=True
        )
        
    except Exception as e:
        logger.error(f"Frame service error: {e}")