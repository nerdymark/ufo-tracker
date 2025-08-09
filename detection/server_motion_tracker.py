#!/usr/bin/env python3
"""
Server-side motion detection and pan-tilt tracking
Detects motion and automatically centers the pan-tilt mechanism on detected objects
"""

import cv2
import numpy as np
import logging
import threading
import time
from typing import Optional, Tuple, Dict, List
from dataclasses import dataclass
from collections import deque

logger = logging.getLogger(__name__)

@dataclass
class MotionRegion:
    """Represents a detected motion region"""
    x: int
    y: int
    width: int
    height: int
    center_x: int
    center_y: int
    area: int
    timestamp: float

class ServerMotionTracker:
    """
    Server-side motion detection with pan-tilt integration
    """
    
    def __init__(self, camera_manager=None, pan_tilt_controller=None):
        """
        Initialize the server motion tracker
        
        Args:
            camera_manager: Camera manager instance for accessing camera feeds
            pan_tilt_controller: Pan-tilt controller for moving the camera
        """
        self.camera_manager = camera_manager
        self.pan_tilt = pan_tilt_controller
        
        # Motion detection parameters
        self.motion_threshold = 30  # Pixel difference threshold
        self.min_area = 500  # Minimum area for valid motion
        self.max_area = 50000  # Maximum area (to filter out full-frame changes)
        
        # Background subtractor for motion detection
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            detectShadows=True,
            varThreshold=16
        )
        
        # Tracking state
        self.tracking_enabled = False
        self.auto_center_enabled = False
        self.last_motion_time = 0
        self.motion_regions = []
        self.tracking_thread = None
        self.stop_event = threading.Event()
        
        # Auto-centering settings
        self.auto_center_timeout = 2.0  # Return to center after 2 seconds of no motion
        self.last_center_time = 0
        
        # Camera field of view (in degrees)
        # These should be calibrated for your specific camera
        self.camera_fov_h = 62  # Horizontal field of view
        self.camera_fov_v = 48  # Vertical field of view
        
        # Frame dimensions (will be updated from actual frames)
        self.frame_width = 640
        self.frame_height = 480
        
        # Dead zone for centering (pixels from center)
        self.dead_zone = 50
        
        # Movement smoothing
        self.movement_history = deque(maxlen=5)
        self.last_pan_command = 0
        self.last_tilt_command = 0
        
        # PID controller parameters for smooth tracking
        self.kp = 0.3  # Proportional gain
        self.ki = 0.01  # Integral gain
        self.kd = 0.1  # Derivative gain
        self.integral_error = {'pan': 0, 'tilt': 0}
        self.last_error = {'pan': 0, 'tilt': 0}
        
        logger.info("Server motion tracker initialized")
    
    def start_tracking(self):
        """Start the motion tracking thread"""
        if self.tracking_enabled:
            logger.warning("Tracking already running")
            return False
        
        # Enable motors if pan-tilt is available
        if self.pan_tilt:
            try:
                self.pan_tilt.enable_motors()
                logger.info("Motors enabled for tracking")
            except Exception as e:
                logger.warning(f"Failed to enable motors: {e}")
        
        self.tracking_enabled = True
        self.stop_event.clear()
        
        # Start tracking thread
        self.tracking_thread = threading.Thread(target=self._tracking_loop)
        self.tracking_thread.daemon = True
        self.tracking_thread.start()
        
        logger.info("Motion tracking started")
        return True
    
    def stop_tracking(self):
        """Stop the motion tracking thread"""
        if not self.tracking_enabled:
            return False
        
        self.tracking_enabled = False
        self.stop_event.set()
        
        if self.tracking_thread:
            self.tracking_thread.join(timeout=2)
        
        logger.info("Motion tracking stopped")
        return True
    
    def _tracking_loop(self):
        """Main tracking loop that runs in a separate thread"""
        logger.info("Tracking loop started")
        
        while not self.stop_event.is_set():
            try:
                # Get frame from IR camera (better for motion detection)
                frame = self._get_camera_frame('ir')
                
                if frame is not None:
                    # Detect motion
                    motion_regions = self._detect_motion(frame)
                    
                    if motion_regions:
                        self.motion_regions = motion_regions
                        self.last_motion_time = time.time()
                        
                        # Auto-center on largest motion if enabled
                        if self.auto_center_enabled and self.pan_tilt:
                            self._center_on_motion(motion_regions[0])
                    else:
                        # No motion detected - check if we should return to center
                        self.motion_regions = []
                        if self.auto_center_enabled and self.pan_tilt:
                            current_time = time.time()
                            # Return to center if no motion for auto_center_timeout seconds
                            if (self.last_motion_time > 0 and 
                                current_time - self.last_motion_time >= self.auto_center_timeout and
                                current_time - self.last_center_time >= self.auto_center_timeout):
                                self._return_to_center()
                                self.last_center_time = current_time
                
                # Small delay to prevent CPU overload
                time.sleep(0.1)  # 10 FPS
                
            except Exception as e:
                logger.error(f"Error in tracking loop: {e}")
                time.sleep(1)
        
        logger.info("Tracking loop stopped")
    
    def _get_camera_frame(self, camera_type='ir'):
        """Get a frame from the specified camera"""
        try:
            # If we have direct camera access, use it
            if self.camera_manager:
                # Get camera instance
                if camera_type == 'ir':
                    camera = self.camera_manager.ir_camera
                else:
                    camera = self.camera_manager.hq_camera
                
                if camera:
                    # Capture a frame
                    frame = camera.capture_frame()
                    
                    # Convert to grayscale for motion detection
                    if frame is not None and len(frame.shape) == 3:
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    
                    # Update frame dimensions
                    if frame is not None:
                        self.frame_height, self.frame_width = frame.shape[:2]
                    
                    return frame
            else:
                # Fetch frame via HTTP from camera service
                return self._fetch_frame_http(camera_type)
                
        except Exception as e:
            logger.error(f"Error getting camera frame: {e}")
            return None
    
    def _fetch_frame_http(self, camera_type='ir'):
        """Fetch frame from camera service via HTTP"""
        try:
            import requests
            
            # Get frame from camera service
            response = requests.get(
                f'http://localhost:5001/{camera_type}_frame',
                timeout=2
            )
            
            if response.status_code == 200:
                # Convert response to numpy array
                import numpy as np
                from io import BytesIO
                
                # Decode JPEG image
                image_bytes = BytesIO(response.content)
                
                # Read with OpenCV
                file_bytes = np.frombuffer(response.content, np.uint8)
                frame = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                
                if frame is not None:
                    # Convert to grayscale for motion detection
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    
                    # Update frame dimensions
                    self.frame_height, self.frame_width = frame.shape[:2]
                    
                    return frame
            else:
                logger.warning(f"HTTP {response.status_code} fetching {camera_type} frame")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching frame via HTTP: {e}")
            return None
    
    def _detect_motion(self, frame) -> List[MotionRegion]:
        """
        Detect motion in the frame
        
        Args:
            frame: Grayscale frame from camera
            
        Returns:
            List of detected motion regions, sorted by area (largest first)
        """
        if frame is None:
            return []
        
        # Apply background subtraction
        motion_mask = self.bg_subtractor.apply(frame)
        
        # Remove shadows (shadows are gray, motion is white)
        _, motion_mask = cv2.threshold(motion_mask, 250, 255, cv2.THRESH_BINARY)
        
        # Morphological operations to reduce noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        motion_mask = cv2.morphologyEx(motion_mask, cv2.MORPH_OPEN, kernel)
        motion_mask = cv2.morphologyEx(motion_mask, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(
            motion_mask, 
            cv2.RETR_EXTERNAL, 
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        # Process contours into motion regions
        motion_regions = []
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Filter by area
            if self.min_area <= area <= self.max_area:
                x, y, w, h = cv2.boundingRect(contour)
                
                # Calculate center
                center_x = x + w // 2
                center_y = y + h // 2
                
                motion_regions.append(MotionRegion(
                    x=x, y=y, width=w, height=h,
                    center_x=center_x, center_y=center_y,
                    area=area,
                    timestamp=time.time()
                ))
        
        # Sort by area (largest first)
        motion_regions.sort(key=lambda r: r.area, reverse=True)
        
        return motion_regions
    
    def _center_on_motion(self, motion_region: MotionRegion):
        """
        Center the pan-tilt mechanism on the detected motion
        
        Args:
            motion_region: The motion region to center on
        """
        if not self.pan_tilt or not self.pan_tilt.is_connected():
            return
        
        # Ensure motors are enabled for movement
        if not self.pan_tilt.get_motors_enabled():
            try:
                self.pan_tilt.enable_motors()
                logger.debug("Motors enabled for centering motion")
            except Exception as e:
                logger.warning(f"Failed to enable motors for centering: {e}")
                return
        
        # Calculate offset from frame center
        frame_center_x = self.frame_width / 2
        frame_center_y = self.frame_height / 2
        
        offset_x = motion_region.center_x - frame_center_x
        offset_y = motion_region.center_y - frame_center_y
        
        # Check if motion is within dead zone
        if abs(offset_x) < self.dead_zone and abs(offset_y) < self.dead_zone:
            return  # Already centered enough
        
        # Convert pixel offset to degrees using PID controller
        pan_adjustment = self._calculate_pid_adjustment(offset_x, 'pan', self.frame_width)
        tilt_adjustment = self._calculate_pid_adjustment(offset_y, 'tilt', self.frame_height)
        
        # Apply movement smoothing
        self.movement_history.append((pan_adjustment, tilt_adjustment))
        if len(self.movement_history) > 2:
            # Average recent movements for smoothing
            pan_adjustment = np.mean([m[0] for m in self.movement_history])
            tilt_adjustment = np.mean([m[1] for m in self.movement_history])
        
        # Get current position
        try:
            status = self.pan_tilt.get_status()
            current_pan = status.get('pan_position', 0)
            current_tilt = status.get('tilt_position', 0)
            
            # Calculate new position
            new_pan = current_pan + pan_adjustment
            new_tilt = current_tilt - tilt_adjustment  # Invert for correct direction
            
            # Apply limits
            pan_limits = status.get('limits', {}).get('pan_range', [-90, 90])
            tilt_limits = status.get('limits', {}).get('tilt_range', [-45, 45])
            
            new_pan = np.clip(new_pan, pan_limits[0], pan_limits[1])
            new_tilt = np.clip(new_tilt, tilt_limits[0], tilt_limits[1])
            
            # Move to new position
            self.pan_tilt.move_to(new_pan, new_tilt)
            
            logger.debug(f"Centering on motion: pan={new_pan:.1f}, tilt={new_tilt:.1f}")
            
        except Exception as e:
            logger.error(f"Error centering on motion: {e}")
    
    def _return_to_center(self):
        """
        Return the pan-tilt mechanism to center position after no motion detected
        """
        if not self.pan_tilt or not self.pan_tilt.is_connected():
            return
        
        # Ensure motors are enabled for movement
        if not self.pan_tilt.get_motors_enabled():
            try:
                self.pan_tilt.enable_motors()
                logger.debug("Motors enabled for returning to center")
            except Exception as e:
                logger.warning(f"Failed to enable motors for centering: {e}")
                return
        
        try:
            logger.info("No motion detected for 2 seconds - returning to center")
            self.pan_tilt.home()  # Return to center position (0, 0)
        except Exception as e:
            logger.error(f"Error returning to center: {e}")
    
    def _calculate_pid_adjustment(self, error: float, axis: str, frame_dimension: int) -> float:
        """
        Calculate PID adjustment for smooth tracking
        
        Args:
            error: Pixel offset from center
            axis: 'pan' or 'tilt'
            frame_dimension: Width or height of frame
            
        Returns:
            Adjustment in degrees
        """
        # Normalize error to -1 to 1 range
        normalized_error = error / (frame_dimension / 2)
        
        # PID calculations
        self.integral_error[axis] += normalized_error
        self.integral_error[axis] = np.clip(self.integral_error[axis], -1, 1)  # Prevent windup
        
        derivative = normalized_error - self.last_error[axis]
        self.last_error[axis] = normalized_error
        
        # Calculate PID output
        output = (
            self.kp * normalized_error +
            self.ki * self.integral_error[axis] +
            self.kd * derivative
        )
        
        # Convert to degrees based on field of view
        if axis == 'pan':
            degrees = output * (self.camera_fov_h / 2)
        else:
            degrees = output * (self.camera_fov_v / 2)
        
        # Limit maximum adjustment per step
        max_adjustment = 5  # degrees
        degrees = np.clip(degrees, -max_adjustment, max_adjustment)
        
        return degrees
    
    def set_auto_center(self, enabled: bool):
        """Enable or disable auto-centering on motion"""
        self.auto_center_enabled = enabled
        
        # Enable motors when auto-centering is enabled and tracking is running
        if enabled and self.tracking_enabled and self.pan_tilt:
            try:
                self.pan_tilt.enable_motors()
                logger.info("Motors enabled for auto-centering")
            except Exception as e:
                logger.warning(f"Failed to enable motors for auto-centering: {e}")
        
        logger.info(f"Auto-centering {'enabled' if enabled else 'disabled'}")
    
    def set_sensitivity(self, threshold: int):
        """
        Set motion detection sensitivity
        
        Args:
            threshold: Motion threshold (lower = more sensitive)
        """
        self.motion_threshold = max(10, min(100, threshold))
        self.bg_subtractor.setVarThreshold(self.motion_threshold)
        logger.info(f"Motion sensitivity set to {self.motion_threshold}")
    
    def get_status(self) -> Dict:
        """Get current tracker status"""
        return {
            'tracking_enabled': self.tracking_enabled,
            'auto_center_enabled': self.auto_center_enabled,
            'motion_detected': len(self.motion_regions) > 0,
            'motion_regions': len(self.motion_regions),
            'last_motion_time': self.last_motion_time,
            'sensitivity': self.motion_threshold,
            'frame_size': f"{self.frame_width}x{self.frame_height}",
            'camera_fov': f"{self.camera_fov_h}°x{self.camera_fov_v}°"
        }
    
    def get_motion_regions(self) -> List[Dict]:
        """Get current motion regions as dictionaries"""
        return [
            {
                'x': r.x,
                'y': r.y,
                'width': r.width,
                'height': r.height,
                'center_x': r.center_x,
                'center_y': r.center_y,
                'area': r.area
            }
            for r in self.motion_regions
        ]