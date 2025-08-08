"""
Image Processing Module for UFO Tracker
Handles image stacking and feature alignment functionality with fisheye correction
"""

import cv2
import numpy as np
import logging
from typing import Optional, Tuple, List
from collections import deque
import threading
import time
import os

logger = logging.getLogger(__name__)

class ImageProcessor:
    """Handles advanced image processing for UFO tracking"""
    
    def __init__(self, max_stack_frames: int = 10):
        """Initialize image processor"""
        self.max_stack_frames = max_stack_frames
        self._ir_frames = deque(maxlen=max_stack_frames)
        self._hq_frames = deque(maxlen=max_stack_frames)
        self._lock = threading.Lock()
        
        # Feature detectors
        self._orb = cv2.ORB_create()
        try:
            self._sift = cv2.SIFT_create()
        except AttributeError:
            self._sift = None
            logger.warning("SIFT not available in this OpenCV build")
        
        try:
            self._surf = cv2.xfeatures2d.SURF_create()
        except (AttributeError, cv2.error):
            self._surf = None
            logger.warning("SURF not available in this OpenCV build")
        
        # Feature matcher
        self._matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        
        # Fisheye correction parameters (will be calibrated automatically)
        self._ir_camera_matrix = None
        self._ir_dist_coeffs = None
        self._hq_camera_matrix = None
        self._hq_dist_coeffs = None
        self._calibration_file = "/home/mark/ufo-tracker/config/camera_calibration.npz"
        
        # Load or initialize calibration
        self._load_calibration()
        
        logger.info("Image processor initialized with fisheye correction")
    
    def add_frame(self, camera_type: str, frame: np.ndarray):
        """Add a frame to the processing queue"""
        if frame is None:
            return
        
        with self._lock:
            if camera_type == 'ir':
                self._ir_frames.append(frame.copy())
            elif camera_type == 'hq':
                self._hq_frames.append(frame.copy())
    
    def _load_calibration(self):
        """Load camera calibration data or initialize defaults"""
        try:
            if os.path.exists(self._calibration_file):
                data = np.load(self._calibration_file)
                self._ir_camera_matrix = data.get('ir_camera_matrix')
                self._ir_dist_coeffs = data.get('ir_dist_coeffs')
                self._hq_camera_matrix = data.get('hq_camera_matrix')
                self._hq_dist_coeffs = data.get('hq_dist_coeffs')
                logger.info("Loaded camera calibration data")
            else:
                logger.info("No calibration file found, will auto-calibrate")
                self._auto_calibrate()
        except Exception as e:
            logger.error(f"Error loading calibration: {e}")
            self._auto_calibrate()
    
    def _auto_calibrate(self):
        """Auto-calibrate fisheye correction based on typical camera parameters"""
        # Default camera matrices (estimated for typical Pi cameras)
        # These will be refined through usage
        
        # IR camera (typically wider angle, more distortion)
        self._ir_camera_matrix = np.array([
            [400, 0, 320],
            [0, 400, 240],
            [0, 0, 1]
        ], dtype=np.float32)
        
        # Higher distortion for wider angle lens
        self._ir_dist_coeffs = np.array([-0.3, 0.1, 0, 0, 0], dtype=np.float32)
        
        # HQ camera (typically more telephoto, less distortion)
        self._hq_camera_matrix = np.array([
            [600, 0, 320],
            [0, 600, 240],
            [0, 0, 1]
        ], dtype=np.float32)
        
        # Lower distortion for telephoto lens
        self._hq_dist_coeffs = np.array([-0.1, 0.05, 0, 0, 0], dtype=np.float32)
        
        logger.info("Auto-calibrated camera parameters")
    
    def _save_calibration(self):
        """Save calibration data to file"""
        try:
            os.makedirs(os.path.dirname(self._calibration_file), exist_ok=True)
            np.savez(self._calibration_file,
                    ir_camera_matrix=self._ir_camera_matrix,
                    ir_dist_coeffs=self._ir_dist_coeffs,
                    hq_camera_matrix=self._hq_camera_matrix,
                    hq_dist_coeffs=self._hq_dist_coeffs)
            logger.info("Saved camera calibration data")
        except Exception as e:
            logger.error(f"Error saving calibration: {e}")
    
    def correct_fisheye(self, frame: np.ndarray, camera_type: str) -> np.ndarray:
        """Apply fisheye correction to frame"""
        if frame is None:
            return frame
        
        try:
            if camera_type == 'ir':
                camera_matrix = self._ir_camera_matrix
                dist_coeffs = self._ir_dist_coeffs
            elif camera_type == 'hq':
                camera_matrix = self._hq_camera_matrix
                dist_coeffs = self._hq_dist_coeffs
            else:
                return frame
            
            if camera_matrix is None or dist_coeffs is None:
                return frame
            
            h, w = frame.shape[:2]
            
            # Scale camera matrix to actual frame size
            scale_x = w / 640
            scale_y = h / 480
            scaled_matrix = camera_matrix.copy()
            scaled_matrix[0, 0] *= scale_x  # fx
            scaled_matrix[1, 1] *= scale_y  # fy
            scaled_matrix[0, 2] *= scale_x  # cx
            scaled_matrix[1, 2] *= scale_y  # cy
            
            # Apply undistortion
            undistorted = cv2.undistort(frame, scaled_matrix, dist_coeffs)
            return undistorted
            
        except Exception as e:
            logger.error(f"Error correcting fisheye for {camera_type}: {e}")
            return frame
    
    def add_frame_to_stack(self, camera_type: str, frame: np.ndarray):
        """Add a frame to the processing queue"""
        if frame is None:
            logger.warning(f"Tried to add None frame to {camera_type} stack")
            return
        
        with self._lock:
            if camera_type == 'ir':
                self._ir_frames.append(frame.copy())
                logger.debug(f"Added IR frame to stack: shape {frame.shape}, total frames: {len(self._ir_frames)}")
            elif camera_type == 'hq':
                self._hq_frames.append(frame.copy())
                logger.debug(f"Added HQ frame to stack: shape {frame.shape}, total frames: {len(self._hq_frames)}")
            else:
                logger.warning(f"Unknown camera type for stacking: {camera_type}")
    
    def stack_images(self, camera_type: str, stack_count: int = 5) -> Optional[np.ndarray]:
        """Stack multiple images for noise reduction and feature enhancement with fisheye correction"""
        with self._lock:
            frames = self._ir_frames if camera_type == 'ir' else self._hq_frames
            
            logger.debug(f"Stack request for {camera_type}: have {len(frames)} frames, need {stack_count}")
            
            if len(frames) < 2:
                logger.warning(f"Not enough frames for stacking {camera_type}: {len(frames)} < 2")
                return None

            # Get the most recent frames
            recent_frames = list(frames)[-stack_count:]
            
            if len(recent_frames) < 2:
                logger.warning(f"Not enough recent frames for stacking {camera_type}: {len(recent_frames)} < 2")
                return recent_frames[-1] if recent_frames else None

            try:
                logger.debug(f"Processing {len(recent_frames)} frames for {camera_type} stacking")
                
                # Apply fisheye correction to all frames first
                corrected_frames = []
                for i, frame in enumerate(recent_frames):
                    corrected = self.correct_fisheye(frame, camera_type)
                    corrected_frames.append(corrected)
                    logger.debug(f"Frame {i} shape: {frame.shape}, corrected shape: {corrected.shape}")
                
                # Convert to float for processing
                stacked = np.zeros_like(corrected_frames[0], dtype=np.float32)
                
                # Stack by averaging
                for frame in corrected_frames:
                    stacked += frame.astype(np.float32)
                
                # Average and convert back to uint8
                averaged = (stacked / len(corrected_frames))
                
                # Apply much stronger brightness enhancement to match live feed brightness
                enhanced = np.power(averaged / 255.0, 0.6)  # Stronger gamma correction
                enhanced = np.clip(enhanced * 255.0 * 2.5, 0, 255)  # Much higher brightness boost (2.5x)
                
                # Apply adaptive histogram equalization for better local contrast
                result_uint8 = enhanced.astype(np.uint8)
                if len(result_uint8.shape) == 3:
                    # For color images, convert to LAB and enhance L channel
                    lab = cv2.cvtColor(result_uint8, cv2.COLOR_RGB2LAB)
                    l, a, b = cv2.split(lab)
                    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                    l = clahe.apply(l)
                    enhanced_lab = cv2.merge([l, a, b])
                    result = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2RGB)
                else:
                    # For grayscale, apply CLAHE directly
                    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                    result = clahe.apply(result_uint8)
                
                logger.debug(f"Stacking complete for {camera_type}: result shape {result.shape}, min={result.min()}, max={result.max()}")
                return result
                
            except Exception as e:
                logger.error(f"Error stacking images: {e}")
                import traceback
                logger.error(f"Stack trace: {traceback.format_exc()}")
                return None
    
    def long_exposure_stack(self, camera_type: str, stack_count: int = 5) -> Optional[np.ndarray]:
        """
        Create a long exposure effect by multiplying frame intensities
        Simulates a long exposure photograph where bright objects accumulate
        """
        with self._lock:
            frames = self._ir_frames if camera_type == 'ir' else self._hq_frames
            
            logger.debug(f"Long exposure stack request for {camera_type}: have {len(frames)} frames, need {stack_count}")
            
            if len(frames) < 2:
                logger.warning(f"Not enough frames for long exposure stacking {camera_type}: {len(frames)} < 2")
                return None

            # Get the most recent frames
            recent_frames = list(frames)[-stack_count:]
            
            if len(recent_frames) < 2:
                logger.warning(f"Not enough recent frames for long exposure stacking {camera_type}: {len(recent_frames)} < 2")
                return recent_frames[-1] if recent_frames else None

            try:
                logger.debug(f"Processing {len(recent_frames)} frames for {camera_type} long exposure stacking")
                
                # Apply fisheye correction to all frames first
                corrected_frames = []
                for i, frame in enumerate(recent_frames):
                    corrected = self.correct_fisheye(frame, camera_type)
                    corrected_frames.append(corrected)
                    logger.debug(f"Frame {i} shape: {frame.shape}, corrected shape: {corrected.shape}")
                
                # Normalize frames to [0,1] range
                normalized_frames = []
                for frame in corrected_frames:
                    norm_frame = frame.astype(np.float32) / 255.0
                    normalized_frames.append(norm_frame)
                
                # Start with the first frame
                result = normalized_frames[0].copy()
                
                # Multiply subsequent frames - bright objects will accumulate
                for frame in normalized_frames[1:]:
                    # Use additive blending for better light accumulation
                    # Add frames but prevent overflow, then apply screen blend
                    additive = np.minimum(result + frame * 0.5, 1.0)
                    result = 1.0 - (1.0 - additive) * (1.0 - frame)
                
                # Much more aggressive enhancement for very dark scenes
                result = np.power(result, 0.5)  # Stronger gamma correction
                result = np.clip(result * 3.0, 0, 1)  # Much higher brightness boost
                
                # Apply adaptive histogram equalization for local contrast
                if len(result.shape) == 3:
                    # For color images, convert to LAB and enhance L channel
                    result_uint8 = (result * 255).astype(np.uint8)
                    lab = cv2.cvtColor(result_uint8, cv2.COLOR_RGB2LAB)
                    l, a, b = cv2.split(lab)
                    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
                    l = clahe.apply(l)
                    enhanced = cv2.merge([l, a, b])
                    final_result = cv2.cvtColor(enhanced, cv2.COLOR_LAB2RGB)
                else:
                    # For grayscale, apply CLAHE directly
                    result_uint8 = (result * 255).astype(np.uint8)
                    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
                    final_result = clahe.apply(result_uint8)
                
                logger.debug(f"Long exposure stacking complete for {camera_type}: result shape {final_result.shape}, min={final_result.min()}, max={final_result.max()}")
                return final_result
                
            except Exception as e:
                logger.error(f"Error in long exposure stacking: {e}")
                import traceback
                logger.error(f"Stack trace: {traceback.format_exc()}")
                return None
    
    def infinite_exposure_stack(self, camera_type: str) -> Optional[np.ndarray]:
        """
        Create an infinite long exposure by using all available frames
        Continuously accumulates light from all frames in the buffer
        """
        with self._lock:
            frames = self._ir_frames if camera_type == 'ir' else self._hq_frames
            
            logger.debug(f"Infinite exposure stack request for {camera_type}: have {len(frames)} frames")
            
            if len(frames) < 1:
                logger.warning(f"No frames available for infinite exposure stacking {camera_type}")
                return None

            # Use all available frames
            all_frames = list(frames)
            
            if len(all_frames) < 1:
                logger.warning(f"No frames for infinite exposure stacking {camera_type}")
                return None

            try:
                logger.debug(f"Processing ALL {len(all_frames)} frames for {camera_type} infinite exposure stacking")
                
                # Apply fisheye correction to all frames first
                corrected_frames = []
                for i, frame in enumerate(all_frames):
                    corrected = self.correct_fisheye(frame, camera_type)
                    corrected_frames.append(corrected)
                
                # Normalize frames to [0,1] range
                normalized_frames = []
                for frame in corrected_frames:
                    norm_frame = frame.astype(np.float32) / 255.0
                    normalized_frames.append(norm_frame)
                
                # Start with zeros for infinite accumulation
                result = np.zeros_like(normalized_frames[0], dtype=np.float32)
                
                # Accumulate all frames with progressive weighting
                for i, frame in enumerate(normalized_frames):
                    # Progressive accumulation - newer frames have slightly more weight
                    weight = 1.0 + (i / len(normalized_frames)) * 0.2
                    result = np.minimum(result + frame * weight / len(normalized_frames), 1.0)
                
                # Very aggressive enhancement for infinite mode
                result = np.power(result, 0.3)  # Very strong gamma correction
                result = np.clip(result * 5.0, 0, 1)  # Very high brightness boost
                
                # Apply strong adaptive histogram equalization
                if len(result.shape) == 3:
                    result_uint8 = (result * 255).astype(np.uint8)
                    lab = cv2.cvtColor(result_uint8, cv2.COLOR_RGB2LAB)
                    l, a, b = cv2.split(lab)
                    clahe = cv2.createCLAHE(clipLimit=5.0, tileGridSize=(4,4))
                    l = clahe.apply(l)
                    enhanced = cv2.merge([l, a, b])
                    final_result = cv2.cvtColor(enhanced, cv2.COLOR_LAB2RGB)
                else:
                    result_uint8 = (result * 255).astype(np.uint8)
                    clahe = cv2.createCLAHE(clipLimit=5.0, tileGridSize=(4,4))
                    final_result = clahe.apply(result_uint8)
                
                logger.debug(f"Infinite exposure stacking complete for {camera_type}: result shape {final_result.shape}, min={final_result.min()}, max={final_result.max()}")
                return final_result
                
            except Exception as e:
                logger.error(f"Error in infinite exposure stacking: {e}")
                import traceback
                logger.error(f"Stack trace: {traceback.format_exc()}")
                return None
    
    def align_cameras(self, method: str = 'phase', show_features: bool = False) -> Optional[np.ndarray]:
        """Align IR and HQ camera views with fisheye correction"""
        with self._lock:
            if not self._ir_frames or not self._hq_frames:
                logger.warning("Not enough frames for alignment")
                return None
            
            try:
                # Get latest frames
                ir_frame = self._ir_frames[-1]
                hq_frame = self._hq_frames[-1]
                
                # Apply fisheye correction first
                ir_corrected = self.correct_fisheye(ir_frame, 'ir')
                hq_corrected = self.correct_fisheye(hq_frame, 'hq')
                
                # Resize frames to same size for alignment
                target_size = (640, 480)
                ir_resized = cv2.resize(ir_corrected, target_size)
                hq_resized = cv2.resize(hq_corrected, target_size)
                
                if method == 'phase':
                    return self._align_phase_correlation(ir_resized, hq_resized)
                else:
                    return self._align_features(ir_resized, hq_resized, method, show_features)
                    
            except Exception as e:
                logger.error(f"Error aligning cameras: {e}")
                return None
    
    def _align_features(self, img1: np.ndarray, img2: np.ndarray, method: str, show_features: bool) -> Optional[np.ndarray]:
        """Align images using feature detection"""
        # Convert to grayscale for feature detection
        gray1 = cv2.cvtColor(img1, cv2.COLOR_RGB2GRAY) if len(img1.shape) == 3 else img1
        gray2 = cv2.cvtColor(img2, cv2.COLOR_RGB2GRAY) if len(img2.shape) == 3 else img2
        
        # Detect features
        detector = self._get_detector(method)
        if detector is None:
            logger.warning(f"Detector {method} not available, falling back to ORB")
            detector = self._orb
        
        kp1, des1 = detector.detectAndCompute(gray1, None)
        kp2, des2 = detector.detectAndCompute(gray2, None)
        
        if des1 is None or des2 is None or len(des1) < 4 or len(des2) < 4:
            logger.warning("Not enough features found for alignment")
            return self._create_side_by_side(img1, img2)
        
        # Match features
        if method == 'sift' or method == 'surf':
            matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=True)
        else:
            matcher = self._matcher
        
        matches = matcher.match(des1, des2)
        matches = sorted(matches, key=lambda x: x.distance)
        
        if len(matches) < 4:
            logger.warning("Not enough good matches for alignment")
            return self._create_side_by_side(img1, img2)
        
        # Extract matching points
        src_pts = np.float32([kp1[m.queryIdx].pt for m in matches[:50]]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches[:50]]).reshape(-1, 1, 2)
        
        # Find homography
        M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        
        if M is None:
            logger.warning("Failed to find homography")
            return self._create_side_by_side(img1, img2)
        
        # Warp image
        h, w = img2.shape[:2]
        aligned_img1 = cv2.warpPerspective(img1, M, (w, h))
        
        # Create result image
        if show_features:
            # Draw matches
            result = cv2.drawMatches(img1, kp1, img2, kp2, matches[:20], None, flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
            return result
        else:
            # Blend the aligned images
            result = cv2.addWeighted(aligned_img1, 0.5, img2, 0.5, 0)
            return result
    
    def _align_phase_correlation(self, img1: np.ndarray, img2: np.ndarray) -> Optional[np.ndarray]:
        """Align images using phase correlation"""
        try:
            # Convert to grayscale
            gray1 = cv2.cvtColor(img1, cv2.COLOR_RGB2GRAY) if len(img1.shape) == 3 else img1
            gray2 = cv2.cvtColor(img2, cv2.COLOR_RGB2GRAY) if len(img2.shape) == 3 else img2
            
            # Calculate phase correlation
            shift, error = cv2.phaseCorrelate(gray1.astype(np.float32), gray2.astype(np.float32))
            
            # Create translation matrix
            M = np.float32([[1, 0, shift[0]], [0, 1, shift[1]]])
            
            # Apply translation
            h, w = img2.shape[:2]
            aligned_img1 = cv2.warpAffine(img1, M, (w, h))
            
            # Blend images
            result = cv2.addWeighted(aligned_img1, 0.5, img2, 0.5, 0)
            return result
            
        except Exception as e:
            logger.error(f"Error in phase correlation alignment: {e}")
            return self._create_side_by_side(img1, img2)
    
    def _get_detector(self, method: str):
        """Get the appropriate feature detector"""
        if method == 'orb':
            return self._orb
        elif method == 'sift' and self._sift is not None:
            return self._sift
        elif method == 'surf' and self._surf is not None:
            return self._surf
        else:
            return self._orb
    
    def _create_side_by_side(self, img1: np.ndarray, img2: np.ndarray) -> np.ndarray:
        """Create a side-by-side comparison when alignment fails"""
        # Ensure both images have the same height
        h1, w1 = img1.shape[:2]
        h2, w2 = img2.shape[:2]
        
        target_height = min(h1, h2)
        img1_resized = cv2.resize(img1, (int(w1 * target_height / h1), target_height))
        img2_resized = cv2.resize(img2, (int(w2 * target_height / h2), target_height))
        
        # Concatenate horizontally
        result = np.hstack([img1_resized, img2_resized])
        return result
    
    def get_stack_info(self) -> dict:
        """Get information about current frame stacks"""
        with self._lock:
            return {
                'ir_frame_count': len(self._ir_frames),
                'hq_frame_count': len(self._hq_frames),
                'max_frames': self.max_stack_frames
            }
    
    def clear_stacks(self):
        """Clear all frame stacks"""
        with self._lock:
            self._ir_frames.clear()
            self._hq_frames.clear()
            logger.info("Frame stacks cleared")
