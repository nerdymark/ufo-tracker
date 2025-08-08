"""
Auto-Tuning System for Camera Exposure Settings
Uses histogram analysis to find optimal camera parameters
"""

import logging
import time
import cv2
import numpy as np
from typing import Tuple, Dict, List, Optional
from dataclasses import dataclass
import threading

logger = logging.getLogger(__name__)

@dataclass
class CameraSettings:
    """Container for camera settings"""
    exposure_time: int  # microseconds
    gain: float
    brightness: float  # -1.0 to 1.0
    contrast: float    # 0.5 to 2.0
    score: float = 0.0  # Histogram quality score

class CameraAutoTuner:
    """Auto-tuning system using histogram analysis"""
    
    def __init__(self):
        """Initialize the auto-tuner"""
        self.tuning_in_progress = False
        self._lock = threading.Lock()
        
        # Histogram target parameters (ideal distribution)
        self.target_mean = 128      # Target mean brightness (0-255)
        self.target_std = 50        # Target standard deviation
        self.min_dynamic_range = 100  # Minimum range between darkest and brightest
        
        # Sampling ranges for different lighting conditions
        self.day_ranges = {
            'exposure_time': [1000, 2000, 5000, 10000, 15000],
            'gain': [1.0, 1.5, 2.0, 3.0],
            'brightness': [-0.2, 0.0, 0.2],
            'contrast': [0.8, 1.0, 1.2]
        }
        
        self.night_ranges = {
            'exposure_time': [20000, 30000, 50000, 70000, 100000],
            'gain': [4.0, 6.0, 8.0, 10.0, 12.0],
            'brightness': [0.0, 0.2, 0.4],
            'contrast': [1.0, 1.2, 1.5]
        }
    
    def analyze_histogram(self, frame: np.ndarray) -> Dict:
        """Analyze frame histogram to evaluate image quality"""
        # Convert to grayscale if needed
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        else:
            gray = frame
        
        # Calculate histogram
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist = hist.flatten() / hist.sum()  # Normalize
        
        # Calculate statistics
        pixels = gray.flatten()
        mean_val = np.mean(pixels)
        std_val = np.std(pixels)
        min_val = np.min(pixels)
        max_val = np.max(pixels)
        dynamic_range = max_val - min_val
        
        # Calculate percentiles for exposure evaluation
        p5 = np.percentile(pixels, 5)
        p95 = np.percentile(pixels, 95)
        
        # Check for clipping (overexposure/underexposure)
        underexposed_ratio = np.sum(pixels < 10) / len(pixels)
        overexposed_ratio = np.sum(pixels > 245) / len(pixels)
        
        # Calculate entropy (information content)
        hist_nonzero = hist[hist > 0]
        entropy = -np.sum(hist_nonzero * np.log2(hist_nonzero))
        
        return {
            'mean': mean_val,
            'std': std_val,
            'min': min_val,
            'max': max_val,
            'dynamic_range': dynamic_range,
            'p5': p5,
            'p95': p95,
            'underexposed_ratio': underexposed_ratio,
            'overexposed_ratio': overexposed_ratio,
            'entropy': entropy,
            'histogram': hist
        }
    
    def calculate_histogram_score(self, stats: Dict) -> float:
        """Calculate quality score based on histogram statistics"""
        score = 100.0
        
        # Penalize deviation from target mean (most important)
        mean_deviation = abs(stats['mean'] - self.target_mean)
        score -= mean_deviation * 0.5
        
        # Penalize low dynamic range
        if stats['dynamic_range'] < self.min_dynamic_range:
            score -= (self.min_dynamic_range - stats['dynamic_range']) * 0.3
        
        # Penalize clipping (severe penalty)
        score -= stats['underexposed_ratio'] * 100
        score -= stats['overexposed_ratio'] * 100
        
        # Reward good standard deviation (contrast)
        std_deviation = abs(stats['std'] - self.target_std)
        score -= std_deviation * 0.2
        
        # Reward high entropy (information content)
        score += stats['entropy'] * 2
        
        # Ensure score doesn't go negative
        return max(0, score)
    
    def sample_settings(self, camera, settings: CameraSettings) -> Optional[Dict]:
        """Sample a specific camera setting and analyze the result"""
        try:
            # Apply settings
            logger.info(f"Testing settings: exposure={settings.exposure_time}μs, "
                       f"gain={settings.gain}, brightness={settings.brightness}, "
                       f"contrast={settings.contrast}")
            
            # Disable auto exposure first
            camera.set_auto_exposure(False)
            time.sleep(0.1)  # Let it settle
            
            # Apply individual settings
            camera.set_exposure(settings.exposure_time)
            camera.set_gain(settings.gain)
            camera.set_brightness(settings.brightness)
            camera.set_contrast(settings.contrast)
            
            # Wait for settings to take effect
            time.sleep(0.5)
            
            # Capture a frame
            frame = camera.get_frame()
            if frame is None:
                logger.warning("Failed to capture frame for analysis")
                return None
            
            # Analyze histogram
            stats = self.analyze_histogram(frame)
            score = self.calculate_histogram_score(stats)
            settings.score = score
            
            logger.info(f"Score: {score:.2f} (mean={stats['mean']:.1f}, "
                       f"std={stats['std']:.1f}, range={stats['dynamic_range']:.0f})")
            
            return stats
            
        except Exception as e:
            logger.error(f"Error sampling settings: {e}")
            return None
    
    def auto_tune_camera(self, camera, is_day: bool = True, quick_mode: bool = False) -> Optional[CameraSettings]:
        """
        Auto-tune camera settings using histogram analysis
        
        Args:
            camera: Camera object to tune
            is_day: True for daytime settings, False for nighttime
            quick_mode: If True, use fewer samples for faster tuning
        
        Returns:
            Optimal CameraSettings or None if tuning failed
        """
        with self._lock:
            if self.tuning_in_progress:
                logger.warning("Auto-tuning already in progress")
                return None
            self.tuning_in_progress = True
        
        try:
            logger.info(f"Starting auto-tuning for {'day' if is_day else 'night'} mode")
            ranges = self.day_ranges if is_day else self.night_ranges
            
            # Generate test configurations
            test_configs = []
            
            if quick_mode:
                # Quick mode: test fewer combinations
                for exp in ranges['exposure_time'][::2]:  # Every other exposure
                    for gain in ranges['gain'][::2]:  # Every other gain
                        for bright in [ranges['brightness'][len(ranges['brightness'])//2]]:  # Middle brightness
                            for contrast in [ranges['contrast'][len(ranges['contrast'])//2]]:  # Middle contrast
                                test_configs.append(CameraSettings(exp, gain, bright, contrast))
            else:
                # Full mode: test all combinations (may be slow)
                for exp in ranges['exposure_time']:
                    for gain in ranges['gain']:
                        for bright in ranges['brightness']:
                            for contrast in ranges['contrast']:
                                test_configs.append(CameraSettings(exp, gain, bright, contrast))
            
            logger.info(f"Testing {len(test_configs)} configurations...")
            
            # Test each configuration
            best_settings = None
            best_score = -float('inf')
            
            for i, settings in enumerate(test_configs):
                if not self.tuning_in_progress:
                    logger.info("Auto-tuning cancelled")
                    break
                
                stats = self.sample_settings(camera, settings)
                if stats and settings.score > best_score:
                    best_score = settings.score
                    best_settings = settings
                
                # Progress update
                if (i + 1) % 5 == 0:
                    logger.info(f"Progress: {i+1}/{len(test_configs)} tested, "
                               f"best score so far: {best_score:.2f}")
            
            if best_settings:
                logger.info(f"Auto-tuning complete! Best settings: "
                           f"exposure={best_settings.exposure_time}μs, "
                           f"gain={best_settings.gain}, "
                           f"brightness={best_settings.brightness}, "
                           f"contrast={best_settings.contrast}, "
                           f"score={best_settings.score:.2f}")
                
                # Apply best settings
                camera.set_exposure(best_settings.exposure_time)
                camera.set_gain(best_settings.gain) 
                camera.set_brightness(best_settings.brightness)
                camera.set_contrast(best_settings.contrast)
                
                return best_settings
            else:
                logger.error("Auto-tuning failed: no valid configurations found")
                return None
                
        except Exception as e:
            logger.error(f"Auto-tuning error: {e}")
            return None
        finally:
            with self._lock:
                self.tuning_in_progress = False
    
    def fine_tune_settings(self, camera, current_settings: CameraSettings, 
                          step_size: float = 0.1) -> Optional[CameraSettings]:
        """
        Fine-tune existing settings using gradient-based optimization
        
        Args:
            camera: Camera object to tune
            current_settings: Current camera settings to improve
            step_size: Step size for gradient search (0.0 to 1.0)
        
        Returns:
            Improved CameraSettings or None if tuning failed
        """
        logger.info("Starting fine-tuning of current settings...")
        
        best_settings = CameraSettings(
            current_settings.exposure_time,
            current_settings.gain,
            current_settings.brightness,
            current_settings.contrast,
            current_settings.score
        )
        
        # Sample current settings to get baseline
        stats = self.sample_settings(camera, best_settings)
        if not stats:
            return None
        
        # Try small adjustments in each direction
        adjustments = [
            ('exposure_time', [-0.2, 0.2]),  # ±20% exposure
            ('gain', [-0.1, 0.1]),           # ±10% gain
            ('brightness', [-0.1, 0.1]),      # ±0.1 brightness
            ('contrast', [-0.1, 0.1])         # ±0.1 contrast
        ]
        
        for param, deltas in adjustments:
            for delta in deltas:
                test_settings = CameraSettings(
                    best_settings.exposure_time,
                    best_settings.gain,
                    best_settings.brightness,
                    best_settings.contrast
                )
                
                # Apply adjustment
                if param == 'exposure_time':
                    new_val = int(test_settings.exposure_time * (1 + delta))
                    test_settings.exposure_time = max(1000, min(100000, new_val))
                elif param == 'gain':
                    test_settings.gain = max(1.0, min(16.0, test_settings.gain + delta * 2))
                elif param == 'brightness':
                    test_settings.brightness = max(-1.0, min(1.0, test_settings.brightness + delta))
                elif param == 'contrast':
                    test_settings.contrast = max(0.5, min(2.0, test_settings.contrast + delta))
                
                # Test adjusted settings
                stats = self.sample_settings(camera, test_settings)
                if stats and test_settings.score > best_settings.score:
                    logger.info(f"Improvement found: {param} adjustment {delta:+.2f} "
                               f"improved score from {best_settings.score:.2f} "
                               f"to {test_settings.score:.2f}")
                    best_settings = test_settings
        
        logger.info(f"Fine-tuning complete. Final score: {best_settings.score:.2f}")
        return best_settings
    
    def cancel_tuning(self):
        """Cancel ongoing auto-tuning"""
        with self._lock:
            if self.tuning_in_progress:
                self.tuning_in_progress = False
                logger.info("Auto-tuning cancelled by user")