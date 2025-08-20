"""
OpenCV Feature Tracker Service
Tracks user-selected features using OpenCV and controls motors to follow them
"""

import cv2
import numpy as np
import threading
import time
import logging
from typing import Optional, Tuple, Dict, Any
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

class FeatureTracker:
    def __init__(self, config):
        self.config = config
        self.tracking_active = False
        self.tracking_thread = None
        self.selected_feature = None
        self.tracker = None
        self.last_position = None
        self.frame_service_url = "http://localhost:5002"
        self.api_service_url = "http://localhost:5000"
        self.camera_type = "ir"  # Default to IR camera
        
        # Feature detection parameters
        self.feature_params = {
            'maxCorners': 100,
            'qualityLevel': 0.3,
            'minDistance': 7,
            'blockSize': 7
        }
        
        # Lucas-Kanade optical flow parameters
        self.lk_params = {
            'winSize': (15, 15),
            'maxLevel': 2,
            'criteria': (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
        }
        
        # Tracking state
        self.target_point = None
        self.selected_point = None
        self.old_gray = None
        self.feature_points = None
        self.tracking_bbox = None
        self.last_motor_command = None
        self.motor_cooldown = 1.0  # seconds
        
        # Movement parameters
        self.movement_threshold = 10  # pixels
        self.pan_scale = 0.5  # degrees per pixel
        self.tilt_scale = 0.4  # degrees per pixel
        
    def get_status(self) -> Dict[str, Any]:
        """Get current tracking status"""
        return {
            'tracking_active': self.tracking_active,
            'has_selected_feature': self.selected_feature is not None,
            'camera_type': self.camera_type,
            'target_point': self.target_point,
            'selected_point': self.selected_point,
            'last_position': self.last_position
        }
    
    def get_still_frame(self, camera_type: str = "ir") -> Optional[np.ndarray]:
        """Get a still frame from the specified camera"""
        try:
            self.camera_type = camera_type
            response = requests.get(f"{self.frame_service_url}/{camera_type}_frame", timeout=5)
            
            if response.status_code == 200:
                # Convert response content to numpy array
                img_array = np.frombuffer(response.content, np.uint8)
                frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                return frame
            else:
                logger.error(f"Failed to get frame: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting still frame: {e}")
            return None
    
    def select_feature_at_point(self, x: int, y: int, frame: np.ndarray) -> bool:
        """Select a feature at the specified point for tracking"""
        try:
            logger.info(f"Attempting to select feature at ({x}, {y}) on frame shape {frame.shape}")
            
            # Validate coordinates
            if x < 0 or y < 0 or x >= frame.shape[1] or y >= frame.shape[0]:
                logger.error(f"Coordinates ({x}, {y}) are outside frame bounds {frame.shape}")
                return False
            
            self.selected_point = (x, y)
            
            # Convert to grayscale for feature detection
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame.copy()
            
            logger.info(f"Converted frame to grayscale, shape: {gray.shape}")
            
            # Create a larger search area around the selected point
            search_radius = 50
            mask = np.zeros_like(gray)
            cv2.circle(mask, (x, y), search_radius, 255, -1)
            
            # Try different feature detection parameters if the first attempt fails
            attempts = [
                {'maxCorners': 100, 'qualityLevel': 0.01, 'minDistance': 5},
                {'maxCorners': 200, 'qualityLevel': 0.005, 'minDistance': 3},
                {'maxCorners': 50, 'qualityLevel': 0.1, 'minDistance': 10}
            ]
            
            corners = None
            used_params = None
            
            for params in attempts:
                try:
                    corners = cv2.goodFeaturesToTrack(
                        gray,
                        mask=mask,
                        blockSize=7,
                        **params
                    )
                    if corners is not None and len(corners) > 0:
                        used_params = params
                        logger.info(f"Found {len(corners)} corners using params: {params}")
                        break
                except Exception as e:
                    logger.warning(f"Feature detection failed with params {params}: {e}")
                    continue
            
            if corners is not None and len(corners) > 0:
                # Find the closest corner to the clicked point
                distances = [np.sqrt((corner[0][0] - x)**2 + (corner[0][1] - y)**2) for corner in corners]
                closest_idx = np.argmin(distances)
                closest_distance = distances[closest_idx]
                
                logger.info(f"Closest feature is {closest_distance:.1f} pixels away")
                
                # Use the clicked point if no close feature found, otherwise use closest feature
                if closest_distance > search_radius / 2:
                    self.target_point = (x, y)
                    logger.info(f"No close features found, using clicked point ({x}, {y})")
                else:
                    self.target_point = tuple(corners[closest_idx][0].astype(int))
                    logger.info(f"Using closest feature at {self.target_point}")
                
                self.feature_points = corners
                self.old_gray = gray.copy()
                
                # Create a bounding box around the feature
                bbox_size = 60  # Larger bbox for better tracking
                bbox_x = max(0, self.target_point[0] - bbox_size//2)
                bbox_y = max(0, self.target_point[1] - bbox_size//2)
                bbox_w = min(bbox_size, gray.shape[1] - bbox_x)
                bbox_h = min(bbox_size, gray.shape[0] - bbox_y)
                self.tracking_bbox = (bbox_x, bbox_y, bbox_w, bbox_h)
                
                logger.info(f"Created tracking bbox: {self.tracking_bbox}")
                
                # Initialize OpenCV tracker
                try:
                    self.tracker = cv2.TrackerCSRT_create()
                    success = self.tracker.init(frame, self.tracking_bbox)
                    if not success:
                        logger.error("Tracker initialization failed")
                        return False
                    logger.info("Tracker initialized successfully")
                except Exception as e:
                    logger.error(f"Tracker creation/init failed: {e}")
                    return False
                
                self.selected_feature = {
                    'point': self.target_point,
                    'bbox': self.tracking_bbox,
                    'timestamp': datetime.now().isoformat(),
                    'camera_type': self.camera_type,
                    'detection_params': used_params
                }
                
                logger.info(f"Feature successfully selected at {self.target_point} with bbox {self.tracking_bbox}")
                return True
            else:
                logger.warning(f"No features found near point ({x}, {y}) even with relaxed parameters")
                
                # Fallback: create a basic tracking box at the clicked location
                self.target_point = (x, y)
                bbox_size = 40
                bbox_x = max(0, x - bbox_size//2)
                bbox_y = max(0, y - bbox_size//2)
                bbox_w = min(bbox_size, frame.shape[1] - bbox_x)
                bbox_h = min(bbox_size, frame.shape[0] - bbox_y)
                self.tracking_bbox = (bbox_x, bbox_y, bbox_w, bbox_h)
                
                try:
                    self.tracker = cv2.TrackerCSRT_create()
                    success = self.tracker.init(frame, self.tracking_bbox)
                    if success:
                        self.selected_feature = {
                            'point': self.target_point,
                            'bbox': self.tracking_bbox,
                            'timestamp': datetime.now().isoformat(),
                            'camera_type': self.camera_type,
                            'fallback': True
                        }
                        logger.info(f"Fallback tracking created at {self.target_point}")
                        return True
                    else:
                        logger.error("Fallback tracker initialization failed")
                        return False
                except Exception as e:
                    logger.error(f"Fallback tracker creation failed: {e}")
                    return False
                
        except Exception as e:
            logger.error(f"Error selecting feature: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def start_tracking(self) -> bool:
        """Start the feature tracking thread"""
        if self.tracking_active:
            logger.warning("Feature tracking already active")
            return False
            
        if self.selected_feature is None:
            logger.error("No feature selected for tracking")
            return False
        
        self.tracking_active = True
        self.tracking_thread = threading.Thread(target=self._tracking_loop, daemon=True)
        self.tracking_thread.start()
        
        logger.info("Feature tracking started")
        return True
    
    def stop_tracking(self):
        """Stop the feature tracking"""
        self.tracking_active = False
        
        if self.tracking_thread and self.tracking_thread.is_alive():
            self.tracking_thread.join(timeout=2.0)
        
        self.tracking_thread = None
        logger.info("Feature tracking stopped")
    
    def _tracking_loop(self):
        """Main tracking loop that runs in a separate thread"""
        logger.info("Starting feature tracking loop")
        
        while self.tracking_active:
            try:
                # Get current frame
                frame = self.get_still_frame(self.camera_type)
                if frame is None:
                    time.sleep(0.1)
                    continue
                
                # Update tracker
                success, bbox = self.tracker.update(frame)
                
                if success:
                    # Calculate center of bounding box
                    center_x = int(bbox[0] + bbox[2] / 2)
                    center_y = int(bbox[1] + bbox[3] / 2)
                    current_position = (center_x, center_y)
                    
                    # Calculate movement needed
                    frame_center_x = frame.shape[1] // 2
                    frame_center_y = frame.shape[0] // 2
                    
                    offset_x = center_x - frame_center_x
                    offset_y = center_y - frame_center_y
                    
                    # Check if movement is significant enough
                    distance = np.sqrt(offset_x**2 + offset_y**2)
                    
                    if distance > self.movement_threshold:
                        # Calculate motor movements
                        pan_movement = offset_x * self.pan_scale
                        tilt_movement = -offset_y * self.tilt_scale  # Negative for correct direction
                        
                        # Send motor command
                        self._send_motor_command(pan_movement, tilt_movement)
                    
                    self.last_position = current_position
                    self.tracking_bbox = bbox
                    
                    logger.debug(f"Tracking feature at {current_position}, offset: ({offset_x}, {offset_y})")
                    
                else:
                    logger.warning("Feature tracking lost")
                    # Try to re-initialize tracking
                    self._attempt_reinitialization(frame)
                
                # Control loop rate
                time.sleep(0.1)  # 10 FPS tracking rate
                
            except Exception as e:
                logger.error(f"Error in tracking loop: {e}")
                time.sleep(1.0)
    
    def _attempt_reinitialization(self, frame: np.ndarray):
        """Attempt to re-initialize tracking when lost"""
        try:
            if self.selected_point is None:
                return False
            
            # Try to find features near the last known position
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            search_radius = 50
            mask = np.zeros_like(gray)
            cv2.circle(mask, self.selected_point, search_radius, 255, -1)
            
            corners = cv2.goodFeaturesToTrack(gray, mask=mask, **self.feature_params)
            
            if corners is not None and len(corners) > 0:
                # Reinitialize with the closest feature
                distances = [np.sqrt((corner[0][0] - self.selected_point[0])**2 + 
                                   (corner[0][1] - self.selected_point[1])**2) for corner in corners]
                closest_idx = np.argmin(distances)
                
                new_point = tuple(corners[closest_idx][0].astype(int))
                
                # Create new bounding box
                bbox_size = 40
                bbox_x = max(0, new_point[0] - bbox_size//2)
                bbox_y = max(0, new_point[1] - bbox_size//2)
                bbox_w = min(bbox_size, gray.shape[1] - bbox_x)
                bbox_h = min(bbox_size, gray.shape[0] - bbox_y)
                new_bbox = (bbox_x, bbox_y, bbox_w, bbox_h)
                
                # Reinitialize tracker
                self.tracker = cv2.TrackerCSRT_create()
                self.tracker.init(frame, new_bbox)
                
                self.target_point = new_point
                self.tracking_bbox = new_bbox
                
                logger.info(f"Reinitialized tracking at {new_point}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error reinitializing tracking: {e}")
            return False
    
    def _send_motor_command(self, pan_degrees: float, tilt_degrees: float):
        """Send motor movement command to API service"""
        try:
            # Check cooldown
            current_time = time.time()
            if (self.last_motor_command and 
                current_time - self.last_motor_command < self.motor_cooldown):
                return
            
            # Send relative movement command
            data = {
                'pan_delta': round(pan_degrees, 2),
                'tilt_delta': round(tilt_degrees, 2)
            }
            
            response = requests.post(
                f"{self.api_service_url}/api/motors/move_relative",
                json=data,
                timeout=2.0
            )
            
            if response.status_code == 200:
                self.last_motor_command = current_time
                logger.debug(f"Motor command sent: pan={pan_degrees:.2f}°, tilt={tilt_degrees:.2f}°")
            else:
                logger.warning(f"Motor command failed: HTTP {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error sending motor command: {e}")
    
    def clear_selection(self):
        """Clear the current feature selection"""
        self.stop_tracking()
        self.selected_feature = None
        self.target_point = None
        self.selected_point = None
        self.tracking_bbox = None
        self.tracker = None
        self.old_gray = None
        self.feature_points = None
        logger.info("Feature selection cleared")

# Global feature tracker instance
feature_tracker = None

def initialize_feature_tracker(config):
    """Initialize the global feature tracker"""
    global feature_tracker
    feature_tracker = FeatureTracker(config)
    return feature_tracker

def get_feature_tracker():
    """Get the global feature tracker instance"""
    return feature_tracker