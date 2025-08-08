"""
Simple Streaming Output Handler for UFO Tracker
Minimal implementation without viewer management for testing
"""

import logging
import threading
import time
import cv2
from typing import Generator, Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class SimpleStreamingOutput:
    """Simple streaming output without viewer management"""
    
    def __init__(self):
        """Initialize streaming output"""
        self._current_frame_data: Optional[bytes] = None
        self._frame_lock = threading.RLock()
        self._active = True
        
        # Frame encoding settings
        self._jpeg_quality = 85
        self._encode_params = [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality]
        
        logger.info("Simple streaming output initialized")
    
    def write_frame(self, frame):
        """Write a new frame to the stream"""
        if not self._active:
            return
        
        try:
            # Convert RGB to BGR for OpenCV (Picamera2 returns RGB)
            if len(frame.shape) == 3 and frame.shape[2] == 3:
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            else:
                frame_bgr = frame
                
            # Encode frame to JPEG
            success, buffer = cv2.imencode('.jpg', frame_bgr, self._encode_params)
            if success:
                # Store frame data directly as bytes
                with self._frame_lock:
                    self._current_frame_data = buffer.tobytes()
                    if len(self._current_frame_data) > 0:
                        logger.debug(f"Frame written: {len(self._current_frame_data)} bytes")
        
        except Exception as e:
            logger.error(f"Error writing frame to stream: {e}")
    
    def get_stream(self) -> Generator[bytes, None, None]:
        """Get streaming generator for Flask Response"""
        logger.info(f"New stream connection")
        
        try:
            while self._active:
                # Get current frame data
                frame_data = None
                with self._frame_lock:
                    if self._current_frame_data:
                        frame_data = self._current_frame_data
                
                if frame_data:
                    # Send frame using proper MJPEG format
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + 
                           frame_data + b'\r\n')
                    logger.debug(f"Frame sent: {len(frame_data)} bytes")
                else:
                    logger.debug("No frame data available")
                
                # Control frame rate
                time.sleep(0.1)  # 10 FPS
        
        finally:
            logger.info(f"Stream connection closed")
    
    def cleanup(self):
        """Cleanup streaming resources"""
        logger.info("Cleaning up simple streaming output...")
        self._active = False
        with self._frame_lock:
            self._current_frame_data = None