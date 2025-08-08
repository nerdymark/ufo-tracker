"""
High-Quality Camera Handler for UFO Tracker
Handles the HQ camera for detailed zoom captures
"""

import logging
import threading
import time
import cv2
import numpy as np
from typing import Optional, Tuple
from picamera2 import Picamera2

from .streaming import StreamingOutput
from config.config import Config

logger = logging.getLogger(__name__)

class HQCamera:
    """High-quality camera handler for detailed captures"""
    
    def __init__(self, camera_index: int = 1, resolution: Tuple[int, int] = (1920, 1080), framerate: int = 15):
        """Initialize HQ camera"""
        self.camera_index = camera_index
        self.resolution = resolution
        self.framerate = framerate
        
        self._camera: Optional[Picamera2] = None
        self._streaming_output: Optional[StreamingOutput] = None
        self._lock = threading.Lock()
        self._active = False
        self._streaming = False
        self._capture_thread: Optional[threading.Thread] = None
        self._latest_frame: Optional[np.ndarray] = None
        self._is_auto_exposure = Config.CAMERA_SETTINGS['hq_camera']['auto_exposure']
        
        # ROI (Region of Interest) for zooming
        self._roi_active = False
        self._roi_coords = None
        self._full_resolution = resolution
        
        self._initialize_camera()
    
    def _initialize_camera(self):
        """Initialize the camera hardware"""
        try:
            self._camera = Picamera2(self.camera_index)
            
            # Configure camera for high quality
            controls = {
                # Don't set fixed FrameRate to allow manual exposure control
                "ExposureTime": Config.CAMERA_SETTINGS['hq_camera']['exposure_time'],
                "AnalogueGain": Config.CAMERA_SETTINGS['hq_camera']['gain'],
                # Extend frame duration limits to allow longer exposures
                # Default is 33ms-120ms, we extend to 1ms-1000ms (1 second)
                "FrameDurationLimits": (1000, 1000000)  # microseconds
            }
            
            # Set auto exposure mode - must be explicitly disabled for manual control
            if not Config.CAMERA_SETTINGS['hq_camera']['auto_exposure']:
                controls["AeEnable"] = False
                # AeConstraintMode: 0=Normal, 1=Highlight, 2=Shadows, 3=Manual
                controls["AeConstraintMode"] = 3  # Manual mode
            else:
                controls["AeEnable"] = True
            
            # Configure for both streaming (lores) and still capture (main)
            # For HQ camera (IMX477): max resolution 4056x3040, streaming at configured resolution
            max_resolution = (4056, 3040)  # IMX477 max resolution
            config = self._camera.create_video_configuration(
                main={"format": "RGB888", "size": max_resolution},  # High-res for still capture
                lores={"format": "RGB888", "size": self.resolution},  # Lower res for streaming
                controls=controls
            )
            
            self._camera.configure(config)
            self._camera.start()
            
            # Initialize streaming output
            self._streaming_output = StreamingOutput()
            
            self._active = True
            logger.info(f"HQ camera {self.camera_index} initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize HQ camera {self.camera_index}: {e}")
            self.cleanup()
            raise
    
    def start_streaming(self):
        """Start streaming from the camera"""
        if not self._active:
            logger.warning("Camera not active, cannot start streaming")
            return False
        
        with self._lock:
            if self._streaming:
                logger.info("HQ camera already streaming")
                return True
            
            try:
                # Set streaming flag BEFORE starting thread to avoid race condition
                self._streaming = True
                
                # Start capture thread
                self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
                self._capture_thread.start()
                
                logger.info("HQ camera streaming started")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start HQ camera streaming: {e}")
                self._streaming = False
                return False
    
    def stop_streaming(self):
        """Stop streaming from the camera"""
        with self._lock:
            if not self._streaming:
                return
            
            self._streaming = False
            
            if self._capture_thread and self._capture_thread.is_alive():
                self._capture_thread.join(timeout=5.0)
            
            logger.info("HQ camera streaming stopped")
    
    def _capture_loop(self):
        """Main capture loop for streaming"""
        logger.info("HQ camera capture loop started")
        
        while self._streaming and self._active:
            try:
                # Capture frame from lores stream for streaming
                frame = self._camera.capture_array("lores")
                
                if frame is not None:
                    # Frame is in RGB format from Picamera2
                    # Apply ROI if active
                    if self._roi_active and self._roi_coords:
                        frame = self._apply_roi(frame)
                    
                    # Cache the latest frame for get_frame() calls
                    with self._lock:
                        self._latest_frame = frame.copy()
                    
                    # Pass to streaming output which will handle conversion for JPEG encoding
                    if self._streaming_output:
                        self._streaming_output.write_frame(frame)
                
                # Dynamic frame timing - don't force fixed FPS
                # The camera will naturally pace based on exposure time
                # Just prevent CPU spinning with minimal sleep
                time.sleep(0.001)  # 1ms minimal sleep
                
            except Exception as e:
                logger.error(f"Error in HQ camera capture loop: {e}")
                time.sleep(0.1)
        
        logger.info("HQ camera capture loop ended")
    
    def _apply_roi(self, frame: np.ndarray) -> np.ndarray:
        """Apply region of interest (crop and zoom)"""
        if not self._roi_coords:
            return frame
        
        x, y, w, h = self._roi_coords
        height, width = frame.shape[:2]
        
        # Ensure ROI is within frame bounds
        x = max(0, min(x, width - 1))
        y = max(0, min(y, height - 1))
        w = max(1, min(w, width - x))
        h = max(1, min(h, height - y))
        
        # Crop the frame
        roi_frame = frame[y:y+h, x:x+w]
        
        # Resize back to original resolution for consistent output
        zoom_factor = Config.TRACKING['zoom_factor']
        new_width = int(w * zoom_factor)
        new_height = int(h * zoom_factor)
        
        if new_width > 0 and new_height > 0:
            roi_frame = cv2.resize(roi_frame, (new_width, new_height))
        
        return roi_frame
    
    def get_frame(self) -> Optional[np.ndarray]:
        """Get the current cached frame (NEVER captures directly to avoid blocking)"""
        if not self._active:
            return None
        
        with self._lock:
            if self._latest_frame is not None:
                return self._latest_frame.copy()
        
        # DO NOT fallback to direct capture when streaming - this causes blocking!
        # If no cached frame is available, return None - streaming must be started first
        if self._streaming:
            logger.debug("HQ camera: No cached frame available while streaming")
        else:
            logger.warning("HQ camera: get_frame() called but streaming not active")
        
        return None
    
    def get_stream(self):
        """Get the streaming generator for Flask"""
        if self._streaming_output:
            return self._streaming_output.get_stream()
        else:
            # Return empty stream if not available
            return iter([])
    
    def set_roi(self, x: int, y: int, width: int, height: int) -> bool:
        """Set region of interest for zooming"""
        try:
            with self._lock:
                self._roi_coords = (x, y, width, height)
                self._roi_active = True
                logger.info(f"HQ camera ROI set to ({x}, {y}, {width}, {height})")
                return True
        except Exception as e:
            logger.error(f"Failed to set ROI: {e}")
            return False
    
    def reset_roi(self) -> bool:
        """Reset to full view"""
        try:
            with self._lock:
                self._roi_active = False
                self._roi_coords = None
                logger.info("HQ camera ROI reset to full view")
                return True
        except Exception as e:
            logger.error(f"Failed to reset ROI: {e}")
            return False
    
    def has_roi(self) -> bool:
        """Check if ROI is active"""
        return self._roi_active
    
    def get_roi(self) -> Optional[Tuple[int, int, int, int]]:
        """Get current ROI coordinates"""
        return self._roi_coords if self._roi_active else None
    
    def set_exposure(self, exposure_time: int):
        """Set exposure time in microseconds"""
        if self._camera and self._active:
            try:
                # Only switch to manual mode if we're currently in auto mode
                if self._is_auto_exposure:
                    self._camera.set_controls({
                        "AeEnable": False,
                        "AeConstraintMode": 3  # Manual mode
                    })
                    self._is_auto_exposure = False
                    Config.CAMERA_SETTINGS['hq_camera']['auto_exposure'] = False
                    # Give camera time to switch modes
                    import time
                    time.sleep(0.1)
                
                # Set exposure time WITHOUT frame duration limits
                self._camera.set_controls({
                    "ExposureTime": exposure_time
                })
                
                logger.info(f"HQ camera exposure set to {exposure_time}μs")
                return True
            except Exception as e:
                logger.error(f"Failed to set HQ camera exposure: {e}")
        return False
    
    def set_gain(self, gain: float):
        """Set analogue gain"""
        if self._camera and self._active:
            try:
                # Only switch to manual mode if we're currently in auto mode
                if self._is_auto_exposure:
                    self._camera.set_controls({
                        "AeEnable": False,
                        "AeConstraintMode": 3  # Manual mode
                    })
                    self._is_auto_exposure = False
                    Config.CAMERA_SETTINGS['hq_camera']['auto_exposure'] = False
                    # Give camera time to switch modes
                    import time
                    time.sleep(0.1)
                
                # Set the gain
                self._camera.set_controls({
                    "AnalogueGain": gain
                })
                logger.info(f"HQ camera gain set to {gain}")
                return True
            except Exception as e:
                logger.error(f"Failed to set HQ camera gain: {e}")
        return False
    
    def is_active(self) -> bool:
        """Check if camera is active"""
        return self._active
    
    def is_streaming(self) -> bool:
        """Check if camera is streaming"""
        return self._streaming
    
    def get_stats(self) -> dict:
        """Get camera statistics"""
        return {
            'camera_index': self.camera_index,
            'resolution': self.resolution,
            'framerate': self.framerate,
            'active': self._active,
            'streaming': self._streaming,
            'roi_active': self._roi_active,
            'roi_coords': self._roi_coords,
            'viewer_count': self._streaming_output.get_viewer_count() if self._streaming_output else 0
        }
    
    def get_exposure_time(self) -> int:
        """Get current exposure time in microseconds"""
        if self._camera and self._active:
            try:
                metadata = self._camera.capture_metadata()
                return metadata.get('ExposureTime', Config.CAMERA_SETTINGS['hq_camera']['exposure_time'])
            except Exception:
                return Config.CAMERA_SETTINGS['hq_camera']['exposure_time']
        return Config.CAMERA_SETTINGS['hq_camera']['exposure_time']
    
    def get_gain(self) -> float:
        """Get current analogue gain"""
        if self._camera and self._active:
            try:
                metadata = self._camera.capture_metadata()
                return metadata.get('AnalogueGain', Config.CAMERA_SETTINGS['hq_camera']['gain'])
            except Exception:
                return Config.CAMERA_SETTINGS['hq_camera']['gain']
        return Config.CAMERA_SETTINGS['hq_camera']['gain']
    
    def get_auto_exposure(self) -> bool:
        """Get auto exposure status"""
        return Config.CAMERA_SETTINGS['hq_camera']['auto_exposure']
    
    def set_auto_exposure(self, enabled: bool) -> bool:
        """Enable or disable auto exposure"""
        if self._camera and self._active:
            try:
                # Only change mode if necessary
                if enabled and not self._is_auto_exposure:
                    # Enable auto exposure without frame duration limits
                    self._camera.set_controls({
                        "AeEnable": True,
                        "AeConstraintMode": 0  # Normal mode
                        # NO FrameDurationLimits - this interferes with camera operation
                    })
                    self._is_auto_exposure = True
                    Config.CAMERA_SETTINGS['hq_camera']['auto_exposure'] = True
                    logger.info("HQ camera auto exposure enabled")
                elif not enabled and self._is_auto_exposure:
                    # Switch to manual mode with day/night defaults
                    import datetime
                    current_hour = datetime.datetime.now().hour
                    
                    if 6 <= current_hour <= 20:  # Daytime (6 AM to 8 PM)
                        exposure_time = 3000   # 3ms - minimal for daytime HQ
                        gain = 1.0            # Minimal gain
                        brightness = 0.0      # No brightness boost
                        contrast = 0.9        # Slightly reduced contrast for day
                        logger.info("HQ camera switching to manual mode with daytime defaults")
                    else:  # Nighttime
                        exposure_time = 40000  # 40ms - longer for night
                        gain = 6.0            # Higher gain for night (less than IR)
                        brightness = 0.1      # Slight brightness boost
                        contrast = 1.1        # Higher contrast for night
                        logger.info("HQ camera switching to manual mode with nighttime defaults")
                    
                    # Switch to manual mode WITHOUT frame duration limits
                    self._camera.set_controls({
                        "AeEnable": False,
                        "AeConstraintMode": 3,  # Manual mode
                        "ExposureTime": exposure_time,
                        "AnalogueGain": gain,
                        "Brightness": brightness,
                        "Contrast": contrast
                        # NO FrameDurationLimits - this interferes with manual settings
                    })
                    self._is_auto_exposure = False
                    Config.CAMERA_SETTINGS['hq_camera']['auto_exposure'] = False
                    logger.info(f"HQ camera manual mode: exposure={exposure_time}μs, gain={gain}, brightness={brightness}, contrast={contrast}")
                else:
                    # Already in the requested mode
                    logger.debug(f"HQ camera already in {'auto' if enabled else 'manual'} exposure mode")
                return True
            except Exception as e:
                logger.error(f"Failed to set HQ camera auto exposure: {e}")
        return False

    def set_brightness(self, brightness: float) -> bool:
        """Set brightness (-1.0 to 1.0)"""
        if self._camera and self._active:
            try:
                # Clamp brightness to valid range
                brightness = max(-1.0, min(1.0, brightness))
                self._camera.set_controls({"Brightness": brightness})
                logger.info(f"HQ camera brightness set to {brightness}")
                return True
            except Exception as e:
                logger.error(f"Failed to set HQ camera brightness: {e}")
        return False

    def get_brightness(self) -> float:
        """Get current brightness"""
        if self._camera and self._active:
            try:
                metadata = self._camera.capture_metadata()
                return metadata.get('Brightness', 0.0)
            except Exception:
                return 0.0
        return 0.0

    def set_contrast(self, contrast: float) -> bool:
        """Set contrast (0.0 to 2.0, 1.0 is default)"""
        if self._camera and self._active:
            try:
                # Clamp contrast to valid range
                contrast = max(0.0, min(2.0, contrast))
                self._camera.set_controls({"Contrast": contrast})
                logger.info(f"HQ camera contrast set to {contrast}")
                return True
            except Exception as e:
                logger.error(f"Failed to set HQ camera contrast: {e}")
        return False
    
    def get_settings(self) -> dict:
        """Get current camera settings"""
        try:
            if not self._camera:
                return {'error': 'Camera not initialized'}
            
            # Get current controls from camera
            controls = self._camera.camera_controls
            
            # Extract current values from controls (they return tuples with min,max,default)
            exposure_time = 33000
            gain = 4.0
            brightness = 0.0
            contrast = 1.0
            
            try:
                # Get actual current values using capture_metadata
                metadata = self._camera.capture_metadata()
                exposure_time = int(metadata.get('ExposureTime', 33000))
                gain = float(metadata.get('AnalogueGain', 4.0))
                brightness = float(metadata.get('Brightness', 0.0)) 
                contrast = float(metadata.get('Contrast', 1.0))
            except Exception as e:
                logger.debug(f"Could not get current values from metadata: {e}")
            
            return {
                'camera': 'hq',
                'auto_exposure': self.get_auto_exposure(),
                'exposure_time': exposure_time,
                'gain': gain,
                'brightness': brightness,
                'contrast': contrast
            }
        except Exception as e:
            logger.error(f"Error getting HQ camera settings: {e}")
            return {
                'camera': 'hq',
                'auto_exposure': self.get_auto_exposure(),
                'exposure_time': 33000,
                'gain': 4.0,
                'brightness': 0.0,
                'contrast': 1.0,
                'error': str(e)
            }

    def analyze_exposure_histogram(self) -> dict:
        """Analyze current frame histogram and suggest exposure settings"""
        try:
            if not self._camera or not self._active:
                return {'error': 'Camera not available'}
            
            # Get frame from cached data to avoid direct capture blocking
            frame = self.get_frame()
            if frame is None:
                return {'error': 'Could not get frame - ensure streaming is active'}
            
            import cv2
            import numpy as np
            
            # Convert to grayscale for histogram analysis
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            else:
                gray = frame
            
            # Calculate histogram
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
            
            # Analyze histogram statistics
            total_pixels = gray.shape[0] * gray.shape[1]
            cumulative = np.cumsum(hist)
            
            # Find percentiles
            p1 = np.searchsorted(cumulative, total_pixels * 0.01)  # 1st percentile
            p99 = np.searchsorted(cumulative, total_pixels * 0.99)  # 99th percentile
            mean_brightness = np.mean(gray)
            
            # Determine exposure adjustments
            current_exposure = self.get_exposure_time()
            current_gain = self.get_gain()
            
            # Target brightness range: 80-160 (out of 255)
            target_brightness = 120
            
            if mean_brightness < 60:  # Too dark
                if current_exposure < 60000:  # Under 60ms, increase exposure (HQ needs less than IR)
                    suggested_exposure = min(current_exposure * 1.5, 80000)
                    suggested_gain = current_gain
                else:  # Max exposure reached, increase gain
                    suggested_exposure = current_exposure
                    suggested_gain = min(current_gain * 1.3, 22.3)  # IMX477 max gain
                adjustment = "increase"
            elif mean_brightness > 180:  # Too bright
                if current_gain > 1.5:  # Reduce gain first
                    suggested_exposure = current_exposure
                    suggested_gain = max(current_gain * 0.7, 1.0)
                else:  # Min gain reached, reduce exposure
                    suggested_exposure = max(current_exposure * 0.7, 1000)
                    suggested_gain = current_gain
                adjustment = "decrease"
            else:  # Good exposure
                suggested_exposure = current_exposure
                suggested_gain = current_gain
                adjustment = "maintain"
            
            # Suggest brightness and contrast based on histogram spread
            brightness_adjust = 0.0
            if p99 - p1 < 100:  # Low contrast
                contrast_adjust = 1.1  # Less contrast boost for HQ
                if mean_brightness < target_brightness:
                    brightness_adjust = 0.05  # Less brightness boost for HQ
            else:  # Good contrast
                contrast_adjust = 1.0
            
            return {
                'mean_brightness': float(mean_brightness),
                'p1': int(p1),
                'p99': int(p99),
                'histogram_spread': int(p99 - p1),
                'adjustment': adjustment,
                'suggested_exposure': int(suggested_exposure),
                'suggested_gain': float(suggested_gain),
                'suggested_brightness': float(brightness_adjust),
                'suggested_contrast': float(contrast_adjust),
                'current_exposure': int(current_exposure),
                'current_gain': float(current_gain)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing HQ camera histogram: {e}")
            return {'error': str(e)}
    
    def apply_dynamic_exposure(self) -> dict:
        """Apply dynamic exposure based on histogram analysis"""
        analysis = self.analyze_exposure_histogram()
        if 'error' in analysis:
            return analysis
        
        try:
            # Apply suggested settings
            self.set_exposure(analysis['suggested_exposure'])
            self.set_gain(analysis['suggested_gain'])
            self.set_brightness(analysis['suggested_brightness'])
            self.set_contrast(analysis['suggested_contrast'])
            
            logger.info(f"HQ dynamic exposure applied: {analysis['adjustment']} - "
                       f"exp={analysis['suggested_exposure']}μs, gain={analysis['suggested_gain']}")
            
            return {
                'success': True,
                'adjustment': analysis['adjustment'],
                'applied_settings': {
                    'exposure_time': analysis['suggested_exposure'],
                    'gain': analysis['suggested_gain'],
                    'brightness': analysis['suggested_brightness'],
                    'contrast': analysis['suggested_contrast']
                },
                'analysis': analysis
            }
            
        except Exception as e:
            logger.error(f"Error applying dynamic exposure: {e}")
            return {'error': str(e)}
    
    def set_day_mode(self) -> dict:
        """Set camera to day mode settings"""
        try:
            self.set_auto_exposure(False)  # Switch to manual
            self.set_exposure(3000)        # 3ms
            self.set_gain(1.0)            # Minimal gain
            self.set_brightness(0.0)       # No brightness boost
            self.set_contrast(0.9)         # Slightly reduced contrast
            
            logger.info("HQ camera set to day mode")
            return {
                'success': True,
                'mode': 'day',
                'settings': {'exposure_time': 3000, 'gain': 1.0, 'brightness': 0.0, 'contrast': 0.9}
            }
        except Exception as e:
            logger.error(f"Error setting day mode: {e}")
            return {'error': str(e)}
    
    def set_night_mode(self) -> dict:
        """Set camera to night mode settings"""
        try:
            self.set_auto_exposure(False)  # Switch to manual
            self.set_exposure(40000)       # 40ms
            self.set_gain(6.0)            # Higher gain (less than IR)
            self.set_brightness(0.1)       # Slight brightness boost
            self.set_contrast(1.1)         # Higher contrast
            
            logger.info("HQ camera set to night mode")
            return {
                'success': True,
                'mode': 'night',
                'settings': {'exposure_time': 40000, 'gain': 6.0, 'brightness': 0.1, 'contrast': 1.1}
            }
        except Exception as e:
            logger.error(f"Error setting night mode: {e}")
            return {'error': str(e)}

    def get_contrast(self) -> float:
        """Get current contrast"""
        if self._camera and self._active:
            try:
                metadata = self._camera.capture_metadata()
                return metadata.get('Contrast', 1.0)
            except Exception:
                return 1.0
        return 1.0

    def capture_still(self, filepath: str, high_quality: bool = True) -> bool:
        """Capture a high-quality still image outside of the preview stream"""
        if not self._active or not self._camera:
            logger.error("Camera not active for still capture")
            return False
        
        try:
            # Configure for still capture if high quality requested
            if high_quality:
                # Temporarily switch to still configuration for maximum quality
                still_config = self._camera.create_still_configuration(
                    main={"size": (2592, 1944)},  # Maximum sensor resolution
                    raw={"size": (2592, 1944)}
                )
                
                # Capture with the still configuration
                self._camera.switch_mode_and_capture_file(still_config, filepath)
                logger.info(f"High-quality still captured to {filepath}")
            else:
                # Use current video configuration for faster capture
                self._camera.capture_file(filepath)
                logger.info(f"Still captured to {filepath}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to capture still image: {e}")
            return False

    def restart_streaming(self) -> bool:
        """Restart camera streaming to recover from bad states"""
        if not self._active:
            return False
        
        try:
            logger.info("Restarting HQ camera streaming to recover from bad state")
            
            # Stop current streaming
            self.stop_streaming()
            
            # Give camera time to stabilize
            import time
            time.sleep(0.5)
            
            # Restart streaming
            result = self.start_streaming()
            
            if result:
                logger.info("HQ camera streaming restarted successfully")
            else:
                logger.error("Failed to restart HQ camera streaming")
            
            return result
            
        except Exception as e:
            logger.error(f"Error restarting HQ camera streaming: {e}")
            return False

    def cleanup(self):
        """Cleanup camera resources"""
        logger.info(f"Cleaning up HQ camera {self.camera_index}...")
        
        # Stop streaming first
        self.stop_streaming()
        
        with self._lock:
            self._active = False
            
            if self._streaming_output:
                try:
                    self._streaming_output.cleanup()
                except Exception as e:
                    logger.error(f"Error cleaning up streaming output: {e}")
                finally:
                    self._streaming_output = None
            
            if self._camera:
                try:
                    self._camera.stop()
                    self._camera.close()
                    logger.info(f"HQ camera {self.camera_index} closed")
                except Exception as e:
                    logger.error(f"Error closing HQ camera: {e}")
                finally:
                    self._camera = None
