"""
Motion Detector for UFO Tracker
Detects moving objects in the sky using the IR camera
Saves detection frames with automatic storage management
"""

import logging
import threading
import time
import cv2
import numpy as np
import os
import shutil
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from config.config import Config

logger = logging.getLogger(__name__)

class MotionDetector:
    """Motion detection system for UFO tracking with frame saving"""
    
    def __init__(self, ir_camera):
        """Initialize motion detector"""
        self.ir_camera = ir_camera
        
        # Motion detection parameters
        self.sensitivity = Config.MOTION_DETECTION['sensitivity']
        self.min_area = Config.MOTION_DETECTION['min_area']
        self.blur_size = Config.MOTION_DETECTION['blur_size']
        
        # Detection frame storage
        self.detections_dir = "/home/mark/ufo-tracker/detections"
        self.max_disk_usage = 0.9  # Keep disk usage below 90%
        self.min_free_space_gb = 1.0  # Keep at least 1GB free
        
        # Create detections directory
        os.makedirs(self.detections_dir, exist_ok=True)
        
        # Background subtractor
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=Config.MOTION_DETECTION['history'],
            varThreshold=Config.MOTION_DETECTION['var_threshold'],
            detectShadows=Config.MOTION_DETECTION['detect_shadows']
        )
        
        # Detection state
        self._running = False
        self._detection_thread: Optional[threading.Thread] = None
        self._cleanup_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Detection results
        self._current_detections: List[Dict[str, Any]] = []
        self._detection_count = 0
        self._last_detection_time: Optional[datetime] = None
        self._saved_frames_count = 0
        
        # Statistics
        self._frame_count = 0
        self._start_time = None
        
        logger.info("Motion detector initialized with frame saving")
    
    def start(self):
        """Start motion detection"""
        with self._lock:
            if self._running:
                logger.info("Motion detector already running")
                return True
            
            if not self.ir_camera or not self.ir_camera.is_active():
                logger.error("IR camera not available for motion detection")
                return False
            
            try:
                self._running = True
                self._start_time = datetime.now()
                self._detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
                self._detection_thread.start()
                
                # Start cleanup thread for storage management
                self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
                self._cleanup_thread.start()
                
                logger.info("Motion detection started with frame saving")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start motion detection: {e}")
                self._running = False
                return False
    
    def stop(self):
        """Stop motion detection"""
        with self._lock:
            if not self._running:
                return
            
            self._running = False
            
            if self._detection_thread and self._detection_thread.is_alive():
                self._detection_thread.join(timeout=5.0)
            
            if self._cleanup_thread and self._cleanup_thread.is_alive():
                self._cleanup_thread.join(timeout=5.0)
            
            logger.info("Motion detection stopped")
    
    def _detection_loop(self):
        """Main detection loop"""
        logger.info("Motion detection loop started")
        
        while self._running:
            try:
                # Get frame from IR camera
                frame = self.ir_camera.get_frame()
                if frame is None:
                    time.sleep(0.1)
                    continue
                
                # Process frame for motion detection
                detections = self._process_frame(frame)
                
                # Update detection results
                with self._lock:
                    self._current_detections = detections
                    self._frame_count += 1
                    
                    if detections:
                        self._detection_count += len(detections)
                        self._last_detection_time = datetime.now()
                        
                        # Save detection frame only if configured
                        if Config.STORAGE.get('save_detections', False):
                            self._save_detection_frame(frame, detections)
                
                # Control processing rate to match IR camera framerate
                time.sleep(1.0 / Config.CAMERA_SETTINGS['ir_camera']['framerate'])  # Match camera FPS
                
            except Exception as e:
                logger.error(f"Error in motion detection loop: {e}")
                time.sleep(0.1)
        
        logger.info("Motion detection loop ended")
    
    def _process_frame(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Process frame for motion detection"""
        detections = []
        
        try:
            # Convert to grayscale (camera provides RGB format)
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            
            # Apply Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (self.blur_size, self.blur_size), 0)
            
            # Apply background subtraction
            fg_mask = self.bg_subtractor.apply(blurred)
            
            # Apply morphological operations to clean up the mask
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
            
            # Find contours
            contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Process contours
            for contour in contours:
                area = cv2.contourArea(contour)
                
                # Filter by minimum area
                if area >= self.min_area:
                    # Get bounding box
                    x, y, w, h = cv2.boundingRect(contour)
                    
                    # Calculate centroid
                    cx = x + w // 2
                    cy = y + h // 2
                    
                    # Create detection object
                    detection = {
                        'id': f"det_{int(time.time() * 1000)}_{len(detections)}",
                        'bbox': (x, y, w, h),
                        'centroid': (cx, cy),
                        'area': area,
                        'timestamp': datetime.now(),
                        'confidence': min(100, area / self.min_area * 10)  # Simple confidence score
                    }
                    
                    detections.append(detection)
            
        except Exception as e:
            logger.error(f"Error processing frame for motion detection: {e}")
        
        return detections
    
    def get_current_detections(self) -> List[Dict[str, Any]]:
        """Get current detection results"""
        with self._lock:
            return self._current_detections.copy()
    
    def get_status(self) -> Dict[str, Any]:
        """Get motion detector status including storage info"""
        with self._lock:
            uptime = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0
            fps = self._frame_count / uptime if uptime > 0 else 0
            
            status = {
                'running': self._running,
                'uptime_seconds': uptime,
                'frames_processed': self._frame_count,
                'fps': round(fps, 2),
                'total_detections': self._detection_count,
                'current_detections': len(self._current_detections),
                'last_detection': self._last_detection_time.isoformat() if self._last_detection_time else None,
                'settings': {
                    'sensitivity': self.sensitivity,
                    'min_area': self.min_area,
                    'blur_size': self.blur_size
                }
            }
            
            # Add storage information
            storage_info = self.get_storage_info()
            status['storage'] = storage_info
            
            return status
    
    def is_running(self) -> bool:
        """Check if motion detection is running"""
        return self._running
    
    def set_sensitivity(self, sensitivity: int):
        """Set motion detection sensitivity"""
        if 1 <= sensitivity <= 100:
            self.sensitivity = sensitivity
            logger.info(f"Motion detection sensitivity set to {sensitivity}")
        else:
            logger.warning(f"Invalid sensitivity value: {sensitivity}")
    
    def set_min_area(self, min_area: int):
        """Set minimum area for detection"""
        if min_area > 0:
            self.min_area = min_area
            logger.info(f"Motion detection minimum area set to {min_area}")
        else:
            logger.warning(f"Invalid minimum area value: {min_area}")
    
    def get_detection_frame(self) -> Optional[np.ndarray]:
        """Get frame with detection overlays"""
        if not self._running or not self.ir_camera:
            return None
        
        try:
            frame = self.ir_camera.get_frame()
            if frame is None:
                return None
            
            # Get current detections
            detections = self.get_current_detections()
            
            # Draw detection overlays
            for detection in detections:
                x, y, w, h = detection['bbox']
                cx, cy = detection['centroid']
                confidence = detection['confidence']
                
                # Draw bounding box
                color = (0, 255, 0) if confidence > 50 else (0, 255, 255)
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                
                # Draw centroid
                cv2.circle(frame, (cx, cy), 5, color, -1)
                
                # Draw confidence text
                text = f"Conf: {confidence:.1f}%"
                cv2.putText(frame, text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            
            # Draw status text
            status_text = f"Detections: {len(detections)}"
            cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            return frame
            
        except Exception as e:
            logger.error(f"Error creating detection frame: {e}")
            return None
    
    def cleanup(self):
        """Cleanup motion detector"""
        logger.info("Cleaning up motion detector...")
        self.stop()
    
    def _save_detection_frame(self, frame: np.ndarray, detections: List[Dict[str, Any]]):
        """Save frame with detections to disk"""
        try:
            # Create timestamped filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # milliseconds
            filename = f"detection_{timestamp}.jpg"
            filepath = os.path.join(self.detections_dir, filename)
            
            # Draw detection overlays on frame
            annotated_frame = frame.copy()
            for detection in detections:
                x, y, w, h = detection['bbox']
                cx, cy = detection['centroid']
                confidence = detection['confidence']
                
                # Draw bounding box
                color = (0, 255, 0) if confidence > 50 else (0, 255, 255)
                cv2.rectangle(annotated_frame, (x, y), (x + w, y + h), color, 2)
                
                # Draw centroid
                cv2.circle(annotated_frame, (cx, cy), 5, color, -1)
                
                # Draw confidence and timestamp
                text = f"Conf: {confidence:.1f}%"
                cv2.putText(annotated_frame, text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            
            # Add timestamp to image
            timestamp_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(annotated_frame, timestamp_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Add detection count
            det_text = f"Detections: {len(detections)}"
            cv2.putText(annotated_frame, det_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Save frame
            cv2.imwrite(filepath, annotated_frame)
            self._saved_frames_count += 1
            
            logger.debug(f"Saved detection frame: {filename}")
            
        except Exception as e:
            logger.error(f"Error saving detection frame: {e}")
    
    def _cleanup_loop(self):
        """Background loop to manage storage space"""
        logger.info("Storage cleanup loop started")
        
        while self._running:
            try:
                self._manage_storage()
                # Check every 5 minutes
                time.sleep(300)
            except Exception as e:
                logger.error(f"Error in storage cleanup: {e}")
                time.sleep(60)  # Wait a minute on error
        
        logger.info("Storage cleanup loop ended")
    
    def _manage_storage(self):
        """Manage detection frame storage to prevent disk overflow"""
        try:
            # Get disk usage
            disk_usage = shutil.disk_usage(self.detections_dir)
            total_space = disk_usage.total
            free_space = disk_usage.free
            used_percent = (total_space - free_space) / total_space
            free_gb = free_space / (1024**3)
            
            # Check if cleanup is needed
            if used_percent > self.max_disk_usage or free_gb < self.min_free_space_gb:
                logger.info(f"Disk usage: {used_percent:.1%}, Free: {free_gb:.2f}GB - Starting cleanup")
                self._cleanup_old_detections()
            
        except Exception as e:
            logger.error(f"Error checking disk usage: {e}")
    
    def _cleanup_old_detections(self):
        """Remove oldest detection frames to free space"""
        try:
            # Get all detection files
            detection_files = []
            for filename in os.listdir(self.detections_dir):
                if filename.startswith("detection_") and filename.endswith(".jpg"):
                    filepath = os.path.join(self.detections_dir, filename)
                    stat = os.stat(filepath)
                    detection_files.append((filepath, stat.st_mtime))
            
            # Sort by modification time (oldest first)
            detection_files.sort(key=lambda x: x[1])
            
            # Remove oldest 25% of files
            files_to_remove = len(detection_files) // 4
            if files_to_remove == 0 and detection_files:
                files_to_remove = 1  # Remove at least one file
            
            removed_count = 0
            for filepath, _ in detection_files[:files_to_remove]:
                try:
                    os.remove(filepath)
                    removed_count += 1
                except Exception as e:
                    logger.error(f"Error removing file {filepath}: {e}")
            
            logger.info(f"Cleaned up {removed_count} old detection frames")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def get_storage_info(self) -> Dict[str, Any]:
        """Get storage information"""
        try:
            # Count detection files
            detection_count = 0
            total_size = 0
            for filename in os.listdir(self.detections_dir):
                if filename.startswith("detection_") and filename.endswith(".jpg"):
                    filepath = os.path.join(self.detections_dir, filename)
                    detection_count += 1
                    total_size += os.path.getsize(filepath)
            
            # Get disk usage
            disk_usage = shutil.disk_usage(self.detections_dir)
            free_gb = disk_usage.free / (1024**3)
            used_percent = (disk_usage.total - disk_usage.free) / disk_usage.total
            
            return {
                'saved_frames': self._saved_frames_count,
                'stored_files': detection_count,
                'storage_size_mb': total_size / (1024**2),
                'disk_free_gb': free_gb,
                'disk_used_percent': used_percent * 100,
                'storage_path': self.detections_dir
            }
            
        except Exception as e:
            logger.error(f"Error getting storage info: {e}")
            return {
                'saved_frames': self._saved_frames_count,
                'stored_files': 0,
                'storage_size_mb': 0,
                'disk_free_gb': 0,
                'disk_used_percent': 0,
                'storage_path': self.detections_dir
            }
