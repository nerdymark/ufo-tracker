"""
Auto Tracking System for UFO Tracker
Correlates motion detection from IR camera to control HQ camera ROI
Uses OpenCV feature matching for camera correlation
"""

import logging
import threading
import time
import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
import math

from config.config import Config
from .fov_mapper import FOVMapper

logger = logging.getLogger(__name__)

class CameraCorrelation:
    """Handles correlation between IR and HQ cameras using feature matching"""
    
    def __init__(self):
        """Initialize camera correlation system"""
        self.homography_matrix = None
        self.correlation_points = []
        self.calibration_valid = False
        self.last_calibration = None
        
        # Feature detector for correlation
        self.detector = cv2.SIFT_create()
        self.matcher = cv2.BFMatcher()
        
        # Calibration parameters
        self.min_matches = 10
        self.max_reprojection_error = 3.0
        
        logger.info("Camera correlation system initialized")
    
    def calibrate_cameras(self, ir_frame: np.ndarray, hq_frame: np.ndarray) -> bool:
        """Calibrate camera correlation using feature matching"""
        try:
            # Convert frames to grayscale
            ir_gray = cv2.cvtColor(ir_frame, cv2.COLOR_RGB2GRAY) if len(ir_frame.shape) == 3 else ir_frame
            hq_gray = cv2.cvtColor(hq_frame, cv2.COLOR_RGB2GRAY) if len(hq_frame.shape) == 3 else hq_frame
            
            # Resize HQ frame to match IR resolution for initial correlation
            ir_h, ir_w = ir_gray.shape
            hq_resized = cv2.resize(hq_gray, (ir_w, ir_h))
            
            # Detect keypoints and descriptors
            kp1, desc1 = self.detector.detectAndCompute(ir_gray, None)
            kp2, desc2 = self.detector.detectAndCompute(hq_resized, None)
            
            if desc1 is None or desc2 is None:
                logger.warning("No features detected for camera correlation")
                return False
            
            # Match features
            matches = self.matcher.knnMatch(desc1, desc2, k=2)
            
            # Apply Lowe's ratio test
            good_matches = []
            for match_pair in matches:
                if len(match_pair) == 2:
                    m, n = match_pair
                    if m.distance < 0.7 * n.distance:
                        good_matches.append(m)
            
            if len(good_matches) < self.min_matches:
                logger.warning(f"Insufficient matches for correlation: {len(good_matches)}")
                return False
            
            # Extract point correspondences
            src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            
            # Calculate homography with RANSAC
            self.homography_matrix, mask = cv2.findHomography(
                src_pts, dst_pts, 
                cv2.RANSAC, 
                self.max_reprojection_error
            )
            
            if self.homography_matrix is not None:
                # Count inliers
                inliers = np.sum(mask)
                inlier_ratio = inliers / len(good_matches)
                
                if inlier_ratio > 0.3:  # At least 30% inliers
                    self.calibration_valid = True
                    self.last_calibration = datetime.now()
                    self.correlation_points = [(src_pts[i][0], dst_pts[i][0]) 
                                             for i in range(len(mask)) if mask[i]]
                    
                    logger.info(f"Camera correlation calibrated: {inliers}/{len(good_matches)} inliers ({inlier_ratio:.2%})")
                    return True
            
            logger.warning("Failed to calculate valid homography")
            return False
            
        except Exception as e:
            logger.error(f"Error calibrating camera correlation: {e}")
            return False
    
    def map_ir_to_hq(self, ir_point: Tuple[int, int], hq_resolution: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        """Map a point from IR camera space to HQ camera space"""
        if not self.calibration_valid or self.homography_matrix is None:
            return None
        
        try:
            # Convert point to homogeneous coordinates
            point = np.array([[ir_point]], dtype=np.float32)
            
            # Apply homography transformation
            transformed = cv2.perspectiveTransform(point, self.homography_matrix)
            
            # Extract coordinates
            x, y = transformed[0][0]
            
            # Scale to HQ camera resolution (homography was calculated for resized HQ frame)
            ir_w, ir_h = 1920, 1080  # IR camera resolution from config
            hq_w, hq_h = hq_resolution
            
            # Scale coordinates to full HQ resolution
            scaled_x = int(x * hq_w / ir_w)
            scaled_y = int(y * hq_h / ir_h)
            
            # Clamp to HQ frame bounds
            scaled_x = max(0, min(scaled_x, hq_w - 1))
            scaled_y = max(0, min(scaled_y, hq_h - 1))
            
            return (scaled_x, scaled_y)
            
        except Exception as e:
            logger.error(f"Error mapping IR point to HQ: {e}")
            return None
    
    def map_ir_bbox_to_hq(self, ir_bbox: Tuple[int, int, int, int], hq_resolution: Tuple[int, int]) -> Optional[Tuple[int, int, int, int]]:
        """Map a bounding box from IR camera space to HQ camera space"""
        if not self.calibration_valid:
            return None
        
        x, y, w, h = ir_bbox
        
        # Map all four corners
        corners = [
            (x, y),           # Top-left
            (x + w, y),       # Top-right  
            (x, y + h),       # Bottom-left
            (x + w, y + h)    # Bottom-right
        ]
        
        mapped_corners = []
        for corner in corners:
            mapped = self.map_ir_to_hq(corner, hq_resolution)
            if mapped is None:
                return None
            mapped_corners.append(mapped)
        
        # Find bounding rectangle of mapped corners
        xs = [p[0] for p in mapped_corners]
        ys = [p[1] for p in mapped_corners]
        
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        return (min_x, min_y, max_x - min_x, max_y - min_y)
    
    def is_calibrated(self) -> bool:
        """Check if cameras are calibrated"""
        return self.calibration_valid
    
    def get_calibration_age(self) -> float:
        """Get age of calibration in seconds"""
        if self.last_calibration is None:
            return -1  # Use -1 to indicate never calibrated (JSON-safe)
        return (datetime.now() - self.last_calibration).total_seconds()


class SmoothROIController:
    """Handles smooth transitions for HQ camera ROI"""
    
    def __init__(self, hq_camera):
        """Initialize smooth ROI controller"""
        self.hq_camera = hq_camera
        self.target_roi = None
        self.current_roi = None
        self.transition_speed = 0.3  # Interpolation factor (0.1 = slow, 1.0 = instant)
        self.min_roi_size = (200, 200)  # Minimum ROI size
        self.roi_padding = 100  # Padding around detected object
        
        self._lock = threading.Lock()
        self._active = False
        self._transition_thread = None
        
        logger.info("Smooth ROI controller initialized")
    
    def start(self):
        """Start smooth ROI transitions"""
        with self._lock:
            if self._active:
                return
            
            self._active = True
            self._transition_thread = threading.Thread(target=self._transition_loop, daemon=True)
            self._transition_thread.start()
            
            logger.info("Smooth ROI controller started")
    
    def stop(self):
        """Stop smooth ROI transitions"""
        with self._lock:
            if not self._active:
                return
            
            self._active = False
            
            if self._transition_thread and self._transition_thread.is_alive():
                self._transition_thread.join(timeout=1.0)
            
            # Reset camera ROI
            if self.hq_camera:
                self.hq_camera.reset_roi()
            
            logger.info("Smooth ROI controller stopped")
    
    def set_target_roi(self, bbox: Tuple[int, int, int, int], hq_resolution: Tuple[int, int]):
        """Set target ROI with padding"""
        x, y, w, h = bbox
        hq_w, hq_h = hq_resolution
        
        # Add padding
        padded_x = max(0, x - self.roi_padding)
        padded_y = max(0, y - self.roi_padding)
        padded_w = min(hq_w - padded_x, w + 2 * self.roi_padding)
        padded_h = min(hq_h - padded_y, h + 2 * self.roi_padding)
        
        # Ensure minimum size
        if padded_w < self.min_roi_size[0]:
            expand = (self.min_roi_size[0] - padded_w) // 2
            padded_x = max(0, padded_x - expand)
            padded_w = min(hq_w - padded_x, self.min_roi_size[0])
        
        if padded_h < self.min_roi_size[1]:
            expand = (self.min_roi_size[1] - padded_h) // 2
            padded_y = max(0, padded_y - expand)
            padded_h = min(hq_h - padded_y, self.min_roi_size[1])
        
        with self._lock:
            self.target_roi = (padded_x, padded_y, padded_w, padded_h)
    
    def reset_roi(self):
        """Reset to full view"""
        with self._lock:
            self.target_roi = None
    
    def _transition_loop(self):
        """Main transition loop"""
        logger.info("ROI transition loop started")
        
        while self._active:
            try:
                with self._lock:
                    target = self.target_roi
                
                if target is None:
                    # Transition to full view
                    if self.current_roi is not None:
                        self.current_roi = None
                        if self.hq_camera:
                            self.hq_camera.reset_roi()
                else:
                    # Transition to target ROI
                    if self.current_roi is None:
                        # First target, set immediately
                        self.current_roi = target
                        if self.hq_camera:
                            self.hq_camera.set_roi(*target)
                    else:
                        # Smooth transition
                        current = self.current_roi
                        
                        # Interpolate between current and target
                        new_x = int(current[0] + (target[0] - current[0]) * self.transition_speed)
                        new_y = int(current[1] + (target[1] - current[1]) * self.transition_speed)
                        new_w = int(current[2] + (target[2] - current[2]) * self.transition_speed)
                        new_h = int(current[3] + (target[3] - current[3]) * self.transition_speed)
                        
                        self.current_roi = (new_x, new_y, new_w, new_h)
                        
                        if self.hq_camera:
                            self.hq_camera.set_roi(new_x, new_y, new_w, new_h)
                
                # Control transition rate to match camera performance
                time.sleep(1.0 / 2)  # 2 FPS transitions to match camera capability
                
            except Exception as e:
                logger.error(f"Error in ROI transition loop: {e}")
                time.sleep(0.1)
        
        logger.info("ROI transition loop ended")


class AutoTracker:
    """Main auto tracking system that coordinates IR motion detection with HQ camera control"""
    
    def __init__(self, camera_manager, motion_detector=None):
        """Initialize auto tracker"""
        self.camera_manager = camera_manager
        self.motion_detector = motion_detector  # Can be None if motion detection is disabled
        
        # Core components
        self.camera_correlation = CameraCorrelation()  # Keep for backwards compatibility
        self.fov_mapper = FOVMapper()  # New parametric FOV mapping
        self.roi_controller = SmoothROIController(camera_manager.hq_camera if camera_manager else None)
        
        # Tracking state
        self._running = False
        self._tracking_thread = None
        self._lock = threading.Lock()
        
        # Auto calibration - temporarily disabled for performance
        self.auto_calibration_enabled = False
        self.calibration_interval = 300  # Recalibrate every 5 minutes
        self.last_auto_calibration = None
        
        # Tracking parameters
        self.tracking_enabled = True  # Enable by default
        self.target_selection_mode = 'largest'  # 'largest', 'newest', 'most_active'
        self.tracking_timeout = 5.0  # Seconds without detection before resetting
        self.last_detection_time = None
        
        # Statistics
        self.tracks_followed = 0
        self.calibration_attempts = 0
        self.successful_calibrations = 0
        
        logger.info("Auto tracker initialized")
    
    def start(self):
        """Start auto tracking system"""
        with self._lock:
            if self._running:
                logger.info("Auto tracker already running")
                return True
            
            try:
                self._running = True
                self.roi_controller.start()
                
                self._tracking_thread = threading.Thread(target=self._tracking_loop, daemon=True)
                self._tracking_thread.start()
                
                logger.info("Auto tracking system started")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start auto tracking: {e}")
                self._running = False
                return False
    
    def stop(self):
        """Stop auto tracking system"""
        with self._lock:
            if not self._running:
                return
            
            self._running = False
            self.tracking_enabled = False
            
            if self._tracking_thread and self._tracking_thread.is_alive():
                self._tracking_thread.join(timeout=2.0)
            
            self.roi_controller.stop()
            
            logger.info("Auto tracking system stopped")
    
    def enable_tracking(self, enabled: bool = True):
        """Enable or disable active tracking"""
        self.tracking_enabled = enabled
        if not enabled:
            self.roi_controller.reset_roi()
        logger.info(f"Auto tracking {'enabled' if enabled else 'disabled'}")
    
    def calibrate_cameras(self) -> bool:
        """Manually calibrate camera correlation"""
        if not self.camera_manager:
            logger.error("Camera manager not available for calibration")
            return False
        
        try:
            # Get frames from both cameras
            ir_frame = self.camera_manager.get_frame_ir()
            hq_frame = self.camera_manager.get_frame_hq()
            
            if ir_frame is None or hq_frame is None:
                logger.error("Could not get frames for calibration")
                return False
            
            self.calibration_attempts += 1
            success = self.camera_correlation.calibrate_cameras(ir_frame, hq_frame)
            
            if success:
                self.successful_calibrations += 1
                logger.info("Manual camera calibration successful")
            else:
                logger.warning("Manual camera calibration failed")
            
            return success
            
        except Exception as e:
            logger.error(f"Error during manual calibration: {e}")
            return False
    
    def _tracking_loop(self):
        """Main auto tracking loop"""
        logger.info("Auto tracking loop started")
        
        while self._running:
            try:
                # Auto calibration check
                if self.auto_calibration_enabled:
                    self._check_auto_calibration()
                
                # Process tracking if enabled (FOV mapping doesn't require calibration)
                if self.tracking_enabled:
                    self._process_tracking()
                
                # Control processing rate - very low frequency without motion detection
                time.sleep(5.0)  # 0.2 FPS processing since no motion detection is available
                
            except Exception as e:
                logger.error(f"Error in auto tracking loop: {e}")
                time.sleep(0.1)
        
        logger.info("Auto tracking loop ended")
    
    def _check_auto_calibration(self):
        """Check if auto calibration is needed"""
        calibration_age = self.camera_correlation.get_calibration_age()
        
        # Calibrate if needed
        if (calibration_age > self.calibration_interval or 
            not self.camera_correlation.is_calibrated()):
            
            if (self.last_auto_calibration is None or 
                (datetime.now() - self.last_auto_calibration).total_seconds() > 30):
                
                logger.info("Performing auto calibration")
                self.last_auto_calibration = datetime.now()
                self.calibrate_cameras()
    
    def _process_tracking(self):
        """Process motion detection and update HQ camera tracking"""
        if not self.motion_detector or not self.camera_manager:
            return
        
        # Get current detections
        detections = self.motion_detector.get_current_detections()
        
        if detections:
            self.last_detection_time = datetime.now()
            
            # Select best detection to track
            target_detection = self._select_target_detection(detections)
            
            if target_detection:
                # Map IR detection to HQ camera coordinates using parametric FOV mapping
                ir_bbox = target_detection['bbox']
                hq_resolution = self.camera_manager.hq_camera.resolution if self.camera_manager.hq_camera else (4056, 3040)
                
                # Use new FOV-based mapping (always available, no calibration needed)
                hq_bbox = self.fov_mapper.map_ir_bbox_to_hq(ir_bbox)
                
                # Set smooth ROI target
                self.roi_controller.set_target_roi(hq_bbox, hq_resolution)
                self.tracks_followed += 1
                
                logger.debug(f"FOV Tracking object: IR bbox {ir_bbox} -> HQ bbox {hq_bbox}")
        else:
            # Check for tracking timeout
            if (self.last_detection_time and 
                (datetime.now() - self.last_detection_time).total_seconds() > self.tracking_timeout):
                
                # No detections for too long, reset to full view
                self.roi_controller.reset_roi()
                self.last_detection_time = None
                logger.debug("Tracking timeout, reset to full view")
    
    def _select_target_detection(self, detections: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Select the best detection to track"""
        if not detections:
            return None
        
        if self.target_selection_mode == 'largest':
            # Select detection with largest area
            return max(detections, key=lambda d: d.get('area', 0))
        
        elif self.target_selection_mode == 'newest':
            # Select most recent detection
            return max(detections, key=lambda d: d.get('timestamp', datetime.min))
        
        elif self.target_selection_mode == 'most_active':
            # Select detection with highest confidence
            return max(detections, key=lambda d: d.get('confidence', 0))
        
        else:
            # Default to first detection
            return detections[0]
    
    def get_status(self) -> Dict[str, Any]:
        """Get auto tracker status"""
        return {
            'running': self._running,
            'tracking_enabled': self.tracking_enabled,
            'calibrated': self.camera_correlation.is_calibrated(),
            'calibration_age_seconds': self.camera_correlation.get_calibration_age(),
            'target_selection_mode': self.target_selection_mode,
            'tracking_timeout': self.tracking_timeout,
            'last_detection': self.last_detection_time.isoformat() if self.last_detection_time else None,
            'statistics': {
                'tracks_followed': self.tracks_followed,
                'calibration_attempts': self.calibration_attempts,
                'successful_calibrations': self.successful_calibrations,
                'calibration_success_rate': (self.successful_calibrations / max(1, self.calibration_attempts)) * 100
            },
            'roi_controller_active': self.roi_controller._active if self.roi_controller else False,
            'fov_mapping': self.fov_mapper.get_scale_info() if self.fov_mapper else None
        }
    
    def set_target_selection_mode(self, mode: str):
        """Set target selection mode"""
        valid_modes = ['largest', 'newest', 'most_active']
        if mode in valid_modes:
            self.target_selection_mode = mode
            logger.info(f"Target selection mode set to: {mode}")
        else:
            logger.warning(f"Invalid target selection mode: {mode}")
    
    def set_tracking_timeout(self, timeout_seconds: float):
        """Set tracking timeout"""
        if timeout_seconds > 0:
            self.tracking_timeout = timeout_seconds
            logger.info(f"Tracking timeout set to: {timeout_seconds}s")
    
    def is_running(self) -> bool:
        """Check if auto tracker is running"""
        return self._running
    
    def is_tracking_enabled(self) -> bool:
        """Check if tracking is enabled"""
        return self.tracking_enabled
    
    def update_fov_settings(self, ir_fov_degrees: Optional[float] = None, hq_fov_degrees: Optional[float] = None):
        """Update field-of-view settings for parametric mapping"""
        if self.fov_mapper:
            self.fov_mapper.update_fov_settings(ir_fov_degrees, hq_fov_degrees)
    
    def validate_fov_mapping(self, test_points: list = None) -> dict:
        """Validate the FOV mapping with test points"""
        if self.fov_mapper:
            return self.fov_mapper.validate_mapping(test_points)
        return {'error': 'FOV mapper not available'}
    
    def cleanup(self):
        """Cleanup auto tracker"""
        logger.info("Cleaning up auto tracker...")
        self.stop()