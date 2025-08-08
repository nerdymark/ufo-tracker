"""
Object Tracker for UFO Tracker
Tracks detected objects and manages HQ camera zooming
"""

import logging
import threading
import time
import math
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict

from config.config import Config

logger = logging.getLogger(__name__)

class TrackedObject:
    """Represents a tracked object"""
    
    def __init__(self, object_id: str, initial_detection: Dict[str, Any]):
        """Initialize tracked object"""
        self.id = object_id
        self.first_seen = datetime.now()
        self.last_seen = datetime.now()
        self.positions = []
        self.disappeared_count = 0
        self.is_active = True
        
        # Add initial position
        self.add_detection(initial_detection)
        
        # Tracking statistics
        self.max_speed = 0.0
        self.total_distance = 0.0
        self.direction_changes = 0
        
        logger.debug(f"Created tracked object {self.id}")
    
    def add_detection(self, detection: Dict[str, Any]):
        """Add a new detection to this tracked object"""
        current_time = datetime.now()
        centroid = detection['centroid']
        
        # Calculate speed if we have previous positions
        if self.positions:
            prev_pos = self.positions[-1]['centroid']
            prev_time = self.positions[-1]['timestamp']
            
            # Calculate distance and time difference
            distance = math.sqrt((centroid[0] - prev_pos[0])**2 + (centroid[1] - prev_pos[1])**2)
            time_diff = (current_time - prev_time).total_seconds()
            
            if time_diff > 0:
                speed = distance / time_diff
                self.max_speed = max(self.max_speed, speed)
                self.total_distance += distance
        
        # Add position
        position_data = {
            'centroid': centroid,
            'bbox': detection['bbox'],
            'timestamp': current_time,
            'area': detection.get('area', 0),
            'confidence': detection.get('confidence', 0)
        }
        
        self.positions.append(position_data)
        self.last_seen = current_time
        self.disappeared_count = 0
        
        # Limit position history
        max_history = 100
        if len(self.positions) > max_history:
            self.positions = self.positions[-max_history:]
    
    def mark_disappeared(self):
        """Mark object as disappeared for this frame"""
        self.disappeared_count += 1
    
    def get_current_position(self) -> Optional[Tuple[int, int]]:
        """Get current centroid position"""
        if self.positions:
            return self.positions[-1]['centroid']
        return None
    
    def get_current_bbox(self) -> Optional[Tuple[int, int, int, int]]:
        """Get current bounding box"""
        if self.positions:
            return self.positions[-1]['bbox']
        return None
    
    def get_predicted_position(self) -> Optional[Tuple[int, int]]:
        """Predict next position based on movement history"""
        if len(self.positions) < 2:
            return self.get_current_position()
        
        # Simple linear prediction based on last two positions
        last_pos = self.positions[-1]['centroid']
        prev_pos = self.positions[-2]['centroid']
        
        # Calculate velocity
        dx = last_pos[0] - prev_pos[0]
        dy = last_pos[1] - prev_pos[1]
        
        # Predict next position
        predicted_x = last_pos[0] + dx
        predicted_y = last_pos[1] + dy
        
        return (int(predicted_x), int(predicted_y))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get tracking statistics"""
        duration = (self.last_seen - self.first_seen).total_seconds()
        
        return {
            'id': self.id,
            'first_seen': self.first_seen.isoformat(),
            'last_seen': self.last_seen.isoformat(),
            'duration_seconds': duration,
            'position_count': len(self.positions),
            'disappeared_count': self.disappeared_count,
            'is_active': self.is_active,
            'max_speed': round(self.max_speed, 2),
            'total_distance': round(self.total_distance, 2),
            'current_position': self.get_current_position(),
            'predicted_position': self.get_predicted_position()
        }

class ObjectTracker:
    """Tracks detected objects and manages camera control"""
    
    def __init__(self, camera_manager, motion_detector):
        """Initialize object tracker"""
        self.camera_manager = camera_manager
        self.motion_detector = motion_detector
        
        # Tracking parameters
        self.max_disappeared = Config.TRACKING['max_disappeared']
        self.max_distance = Config.TRACKING['max_distance']
        self.track_duration = Config.TRACKING['track_duration']
        
        # Tracked objects
        self.objects: Dict[str, TrackedObject] = {}
        self._lock = threading.Lock()
        self._next_id = 0
        
        # Tracking state
        self._running = False
        self._tracking_thread: Optional[threading.Thread] = None
        
        # Currently tracked object for HQ camera
        self._primary_target: Optional[str] = None
        
        # Statistics
        self._total_objects_tracked = 0
        self._start_time = None
        
        logger.info("Object tracker initialized")
    
    def start(self):
        """Start object tracking"""
        with self._lock:
            if self._running:
                logger.info("Object tracker already running")
                return True
            
            try:
                self._running = True
                self._start_time = datetime.now()
                self._tracking_thread = threading.Thread(target=self._tracking_loop, daemon=True)
                self._tracking_thread.start()
                
                logger.info("Object tracking started")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start object tracking: {e}")
                self._running = False
                return False
    
    def stop(self):
        """Stop object tracking"""
        with self._lock:
            if not self._running:
                return
            
            self._running = False
            
            if self._tracking_thread and self._tracking_thread.is_alive():
                self._tracking_thread.join(timeout=5.0)
            
            # Reset HQ camera
            if self.camera_manager and self.camera_manager.hq_camera:
                self.camera_manager.reset_hq_roi()
            
            logger.info("Object tracking stopped")
    
    def _tracking_loop(self):
        """Main tracking loop"""
        logger.info("Object tracking loop started")
        
        while self._running:
            try:
                # Get current detections
                detections = self.motion_detector.get_current_detections()
                
                # Update tracking
                self._update_tracking(detections)
                
                # Update HQ camera targeting
                self._update_camera_targeting()
                
                # Cleanup old objects
                self._cleanup_objects()
                
                # Control processing rate
                time.sleep(1.0 / 10)  # Process at ~10 FPS
                
            except Exception as e:
                logger.error(f"Error in object tracking loop: {e}")
                time.sleep(0.1)
        
        logger.info("Object tracking loop ended")
    
    def _update_tracking(self, detections: List[Dict[str, Any]]):
        """Update object tracking with new detections"""
        with self._lock:
            # Mark all objects as potentially disappeared
            for obj in self.objects.values():
                obj.mark_disappeared()
            
            # Match detections to existing objects
            used_detections = set()
            
            for obj_id, obj in self.objects.items():
                if not obj.is_active:
                    continue
                
                best_match_idx = None
                best_distance = float('inf')
                
                # Find closest detection to this object's predicted position
                predicted_pos = obj.get_predicted_position()
                if predicted_pos:
                    for i, detection in enumerate(detections):
                        if i in used_detections:
                            continue
                        
                        det_centroid = detection['centroid']
                        distance = math.sqrt(
                            (predicted_pos[0] - det_centroid[0])**2 + 
                            (predicted_pos[1] - det_centroid[1])**2
                        )
                        
                        if distance < self.max_distance and distance < best_distance:
                            best_distance = distance
                            best_match_idx = i
                
                # Update object with matched detection
                if best_match_idx is not None:
                    obj.add_detection(detections[best_match_idx])
                    used_detections.add(best_match_idx)
            
            # Create new objects for unmatched detections
            for i, detection in enumerate(detections):
                if i not in used_detections:
                    obj_id = f"obj_{self._next_id}"
                    self._next_id += 1
                    
                    new_obj = TrackedObject(obj_id, detection)
                    self.objects[obj_id] = new_obj
                    self._total_objects_tracked += 1
                    
                    logger.info(f"Started tracking new object: {obj_id}")
    
    def _update_camera_targeting(self):
        """Update HQ camera targeting based on tracked objects"""
        if not self.camera_manager or not self.camera_manager.hq_camera:
            return
        
        # Find best object to track with HQ camera
        best_target = self._select_primary_target()
        
        if best_target != self._primary_target:
            self._primary_target = best_target
            
            if best_target:
                target_obj = self.objects[best_target]
                bbox = target_obj.get_current_bbox()
                
                if bbox:
                    # Set ROI for HQ camera
                    x, y, w, h = bbox
                    
                    # Expand bbox for better tracking
                    margin = 50
                    x = max(0, x - margin)
                    y = max(0, y - margin)
                    w = w + 2 * margin
                    h = h + 2 * margin
                    
                    self.camera_manager.set_hq_roi(x, y, w, h)
                    logger.info(f"HQ camera targeting object {best_target}")
            else:
                # No target, reset to full view
                self.camera_manager.reset_hq_roi()
                logger.info("HQ camera reset to full view")
    
    def _select_primary_target(self) -> Optional[str]:
        """Select the best object to track with HQ camera"""
        best_obj_id = None
        best_score = 0
        
        current_time = datetime.now()
        
        for obj_id, obj in self.objects.items():
            if not obj.is_active or obj.disappeared_count > 5:
                continue
            
            # Calculate tracking score based on multiple factors
            score = 0
            
            # Duration bonus
            duration = (current_time - obj.first_seen).total_seconds()
            if duration >= self.track_duration:
                score += 50
            
            # Size bonus (larger objects get higher priority)
            if obj.positions:
                area = obj.positions[-1].get('area', 0)
                score += min(30, area / 1000)
            
            # Movement bonus (moving objects are more interesting)
            score += min(20, obj.max_speed / 10)
            
            # Consistency bonus (objects seen more frequently)
            score += min(20, len(obj.positions) / 10)
            
            # Penalty for recently disappeared objects
            score -= obj.disappeared_count * 5
            
            if score > best_score:
                best_score = score
                best_obj_id = obj_id
        
        return best_obj_id
    
    def _cleanup_objects(self):
        """Remove objects that have disappeared for too long"""
        with self._lock:
            objects_to_remove = []
            
            for obj_id, obj in self.objects.items():
                # Mark as inactive if disappeared for too long
                if obj.disappeared_count >= self.max_disappeared:
                    obj.is_active = False
                
                # Remove very old inactive objects
                if not obj.is_active and obj.disappeared_count >= self.max_disappeared * 2:
                    objects_to_remove.append(obj_id)
            
            # Remove old objects
            for obj_id in objects_to_remove:
                del self.objects[obj_id]
                if obj_id == self._primary_target:
                    self._primary_target = None
                logger.debug(f"Removed old tracked object: {obj_id}")
    
    def get_tracked_objects(self) -> List[Dict[str, Any]]:
        """Get list of all tracked objects"""
        with self._lock:
            return [obj.get_stats() for obj in self.objects.values() if obj.is_active]
    
    def get_status(self) -> Dict[str, Any]:
        """Get tracker status"""
        with self._lock:
            uptime = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0
            active_objects = len([obj for obj in self.objects.values() if obj.is_active])
            
            return {
                'running': self._running,
                'uptime_seconds': uptime,
                'total_objects_tracked': self._total_objects_tracked,
                'active_objects': active_objects,
                'primary_target': self._primary_target,
                'settings': {
                    'max_disappeared': self.max_disappeared,
                    'max_distance': self.max_distance,
                    'track_duration': self.track_duration
                }
            }
    
    def is_running(self) -> bool:
        """Check if tracker is running"""
        return self._running
    
    def get_primary_target(self) -> Optional[str]:
        """Get current primary target object ID"""
        return self._primary_target
    
    def set_primary_target(self, obj_id: Optional[str]):
        """Manually set primary target"""
        with self._lock:
            if obj_id is None or obj_id in self.objects:
                self._primary_target = obj_id
                logger.info(f"Primary target set to {obj_id}")
                return True
            else:
                logger.warning(f"Object {obj_id} not found for targeting")
                return False
    
    def cleanup(self):
        """Cleanup object tracker"""
        logger.info("Cleaning up object tracker...")
        self.stop()
