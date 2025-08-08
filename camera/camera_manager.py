"""
Camera Manager for UFO Tracker
Manages both IR and HQ cameras with streaming objects
"""

import logging
import threading
import time
from typing import Optional, Dict, Tuple

from picamera2 import Picamera2
from .ir_camera import IRCamera
from .hq_camera import HQCamera
from config.config import Config

logger = logging.getLogger(__name__)

class CameraManager:
    """Manages both cameras and their streaming objects"""
    
    def __init__(self):
        """Initialize camera manager with automatic camera detection"""
        self.ir_camera: Optional[IRCamera] = None
        self.hq_camera: Optional[HQCamera] = None
        self._lock = threading.Lock()
        self._running = False
        
        # Auto-detect and assign cameras
        self._auto_detect_and_initialize_cameras()
    
    def _probe_camera_capabilities(self, index: int) -> Optional[Dict]:
        """Probe a camera to determine its capabilities"""
        try:
            logger.info(f"Probing camera {index} for capabilities...")
            camera = Picamera2(index)
            
            # Get sensor modes to determine maximum resolution
            sensor_modes = camera.sensor_modes
            max_resolution = (0, 0)
            max_area = 0
            
            for mode in sensor_modes:
                size = mode.get('size', (0, 0))
                area = size[0] * size[1]
                if area > max_area:
                    max_area = area
                    max_resolution = size
            
            # Get camera properties
            try:
                properties = camera.camera_properties
                model = properties.get('Model', 'Unknown')
            except Exception:
                model = 'Unknown'
            
            camera.close()
            
            result = {
                'index': index,
                'model': model,
                'max_resolution': max_resolution,
                'max_area': max_area,
                'sensor_modes': len(sensor_modes)
            }
            
            logger.info(f"Camera {index}: {model} - Max Resolution: {max_resolution[0]}x{max_resolution[1]} ({max_area:,} pixels)")
            return result
            
        except Exception as e:
            logger.debug(f"Camera {index} not available: {e}")
            return None
    
    def _auto_detect_and_initialize_cameras(self):
        """Automatically detect cameras and assign them to appropriate roles"""
        logger.info("Auto-detecting available cameras...")
        
        # Probe cameras 0 and 1
        cameras_info = {}
        for index in [0, 1]:
            info = self._probe_camera_capabilities(index)
            if info:
                cameras_info[index] = info
        
        if not cameras_info:
            logger.error("No cameras detected - system will run without cameras")
            self._running = True
            return
        
        # Determine which camera should be IR (lower resolution) and HQ (higher resolution)
        if len(cameras_info) == 1:
            # Only one camera available - use it as both IR and HQ
            index = list(cameras_info.keys())[0]
            logger.warning(f"Only one camera detected at index {index} - using for both IR and HQ")
            ir_index = hq_index = index
        else:
            # Two cameras - assign based on resolution
            sorted_cameras = sorted(cameras_info.items(), key=lambda x: x[1]['max_area'])
            ir_index = sorted_cameras[0][0]  # Lower resolution for IR
            hq_index = sorted_cameras[1][0]  # Higher resolution for HQ
            
            logger.info(f"Camera assignment: IR={ir_index} ({cameras_info[ir_index]['model']}) - {cameras_info[ir_index]['max_resolution'][0]}x{cameras_info[ir_index]['max_resolution'][1]}")
            logger.info(f"Camera assignment: HQ={hq_index} ({cameras_info[hq_index]['model']}) - {cameras_info[hq_index]['max_resolution'][0]}x{cameras_info[hq_index]['max_resolution'][1]}")
        
        # Initialize cameras with detected indices
        self._initialize_cameras_with_indices(ir_index, hq_index)
    
    def _initialize_cameras_with_indices(self, ir_index: int, hq_index: int):
        """Initialize cameras with specific indices"""
        ir_initialized = False
        hq_initialized = False
        
        # Initialize IR Camera
        try:
            ir_config = Config.CAMERA_SETTINGS['ir_camera']
            logger.info(f"Initializing IR camera at detected index {ir_index}")
            self.ir_camera = IRCamera(
                camera_index=ir_index,
                resolution=ir_config['resolution'],
                framerate=ir_config['framerate']
            )
            ir_initialized = True
            logger.info("IR camera initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize IR camera at index {ir_index}: {e}")
            self.ir_camera = None
        
        # Initialize HQ Camera
        try:
            hq_config = Config.CAMERA_SETTINGS['hq_camera']
            logger.info(f"Initializing HQ camera at detected index {hq_index}")
            self.hq_camera = HQCamera(
                camera_index=hq_index,
                resolution=hq_config['resolution'],
                framerate=hq_config['framerate']
            )
            hq_initialized = True
            logger.info("HQ camera initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize HQ camera at index {hq_index}: {e}")
            self.hq_camera = None
        
        # Check final status
        if not ir_initialized and not hq_initialized:
            logger.error("No cameras could be initialized - system will run in limited mode")
        elif not ir_initialized:
            logger.warning("IR camera unavailable - motion detection disabled")
        elif not hq_initialized:
            logger.warning("HQ camera unavailable - high-quality capture disabled")
        
        self._running = True
        logger.info(f"Camera manager initialized with auto-detection: IR={ir_initialized}, HQ={hq_initialized}")

    def get_detected_camera_assignments(self) -> Dict:
        """Get information about the detected camera assignments"""
        return {
            'ir_camera': {
                'index': self.ir_camera.camera_index if self.ir_camera else None,
                'active': self.ir_camera.is_active() if self.ir_camera else False,
                'resolution': self.ir_camera.resolution if self.ir_camera else None
            },
            'hq_camera': {
                'index': self.hq_camera.camera_index if self.hq_camera else None,
                'active': self.hq_camera.is_active() if self.hq_camera else False,
                'resolution': self.hq_camera.resolution if self.hq_camera else None
            },
            'auto_detected': True
        }

    def _initialize_cameras(self):
        """Legacy initialization method - replaced by auto-detection"""
        logger.warning("Legacy _initialize_cameras() called - using auto-detection instead")
        return
        
        # Try to initialize IR Camera
        try:
            ir_config = Config.CAMERA_SETTINGS['ir_camera']
            logger.info(f"Attempting to initialize IR camera at index {ir_config['index']}")
            self.ir_camera = IRCamera(
                camera_index=ir_config['index'],
                resolution=ir_config['resolution'],
                framerate=ir_config['framerate']
            )
            ir_initialized = True
            logger.info("IR camera initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize IR camera: {e}")
            self.ir_camera = None
        
        # Try to initialize HQ Camera
        try:
            hq_config = Config.CAMERA_SETTINGS['hq_camera']
            logger.info(f"Attempting to initialize HQ camera at index {hq_config['index']}")
            self.hq_camera = HQCamera(
                camera_index=hq_config['index'],
                resolution=hq_config['resolution'],
                framerate=hq_config['framerate']
            )
            hq_initialized = True
            logger.info("HQ camera initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize HQ camera: {e}")
            self.hq_camera = None
        
        # Check if at least one camera is available
        if not ir_initialized and not hq_initialized:
            logger.error("No cameras could be initialized - system will run in limited mode")
            # Don't raise exception, allow system to run without cameras
        elif not ir_initialized:
            logger.warning("IR camera unavailable - motion detection disabled")
        elif not hq_initialized:
            logger.warning("HQ camera unavailable - high-quality capture disabled")
        
        self._running = True
        logger.info(f"Camera manager initialized: IR={ir_initialized}, HQ={hq_initialized}")
    
    def start_streaming(self):
        """Start streaming from both cameras"""
        with self._lock:
            if not self._running:
                logger.warning("Camera manager not running, cannot start streaming")
                return False
            
            try:
                if self.ir_camera:
                    self.ir_camera.start_streaming()
                    logger.info("IR camera streaming started")
                
                if self.hq_camera:
                    self.hq_camera.start_streaming()
                    logger.info("HQ camera streaming started")
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to start streaming: {e}")
                return False
    
    def stop_streaming(self):
        """Stop streaming from both cameras"""
        with self._lock:
            try:
                if self.ir_camera:
                    self.ir_camera.stop_streaming()
                    logger.info("IR camera streaming stopped")
                
                if self.hq_camera:
                    self.hq_camera.stop_streaming()
                    logger.info("HQ camera streaming stopped")
                
            except Exception as e:
                logger.error(f"Error stopping streaming: {e}")
    
    def get_frame_ir(self):
        """Get current frame from IR camera"""
        if self.ir_camera and self._running:
            return self.ir_camera.get_frame()
        return None
    
    def get_frame_hq(self):
        """Get current frame from HQ camera"""
        if self.hq_camera and self._running:
            return self.hq_camera.get_frame()
        return None
    
    def set_hq_roi(self, x, y, width, height):
        """Set region of interest for HQ camera (for zooming on detected objects)"""
        if self.hq_camera and self._running:
            return self.hq_camera.set_roi(x, y, width, height)
        return False
    
    def reset_hq_roi(self):
        """Reset HQ camera to full view"""
        if self.hq_camera and self._running:
            return self.hq_camera.reset_roi()
        return False
    
    def capture_still_hq(self, filepath: str, high_quality: bool = True) -> bool:
        """Capture a still image from HQ camera outside of preview stream"""
        if self.hq_camera and self._running:
            return self.hq_camera.capture_still(filepath, high_quality)
        return False

    def capture_still_ir(self, filepath: str, high_quality: bool = True) -> bool:
        """Capture a still image from IR camera outside of preview stream"""
        if self.ir_camera and self._running:
            return self.ir_camera.capture_still(filepath, high_quality)
        return False

    def get_camera_status(self):
        """Get status of both cameras"""
        return {
            'ir_camera': {
                'active': self.ir_camera.is_active() if self.ir_camera else False,
                'streaming': self.ir_camera.is_streaming() if self.ir_camera else False,
                'resolution': self.ir_camera.resolution if self.ir_camera else None,
                'framerate': self.ir_camera.framerate if self.ir_camera else None
            },
            'hq_camera': {
                'active': self.hq_camera.is_active() if self.hq_camera else False,
                'streaming': self.hq_camera.is_streaming() if self.hq_camera else False,
                'resolution': self.hq_camera.resolution if self.hq_camera else None,
                'framerate': self.hq_camera.framerate if self.hq_camera else None,
                'roi_active': self.hq_camera.has_roi() if self.hq_camera else False
            },
            'manager_running': self._running
        }
    
    def cleanup(self):
        """Cleanup cameras and resources"""
        logger.info("Cleaning up camera manager...")
        
        with self._lock:
            self._running = False
            
            if self.ir_camera:
                try:
                    self.ir_camera.cleanup()
                    logger.info("IR camera cleaned up")
                except Exception as e:
                    logger.error(f"Error cleaning up IR camera: {e}")
                finally:
                    self.ir_camera = None
            
            if self.hq_camera:
                try:
                    self.hq_camera.cleanup()
                    logger.info("HQ camera cleaned up")
                except Exception as e:
                    logger.error(f"Error cleaning up HQ camera: {e}")
                finally:
                    self.hq_camera = None
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.cleanup()
