"""
Field of View Mapping Utility for UFO Tracker
Parametric coordinate transformation between cameras with different FOVs
"""

import logging
import math
import numpy as np
from typing import Tuple, Optional
from config.config import Config

logger = logging.getLogger(__name__)

class FOVMapper:
    """Handles parametric field-of-view based coordinate mapping between cameras"""
    
    def __init__(self):
        """Initialize FOV mapper with camera parameters from config"""
        self.ir_fov_degrees = Config.CAMERA_SETTINGS['ir_camera']['field_of_view_degrees']
        self.hq_fov_degrees = Config.CAMERA_SETTINGS['hq_camera']['field_of_view_degrees']
        self.ir_resolution = Config.CAMERA_SETTINGS['ir_camera']['resolution']
        self.hq_resolution = Config.CAMERA_SETTINGS['hq_camera']['resolution']
        
        # Convert FOV to radians for calculations
        self.ir_fov_rad = math.radians(self.ir_fov_degrees)
        self.hq_fov_rad = math.radians(self.hq_fov_degrees)
        
        # Calculate scale factors
        self._calculate_scale_factors()
        
        logger.info(f"FOV Mapper initialized: IR={self.ir_fov_degrees}°, HQ={self.hq_fov_degrees}°")
    
    def _calculate_scale_factors(self):
        """Calculate scale factors for coordinate transformation"""
        # Angular resolution (radians per pixel) for each camera
        self.ir_angular_res = self.ir_fov_rad / self.ir_resolution[0]  # rad/pixel horizontal
        self.hq_angular_res = self.hq_fov_rad / self.hq_resolution[0]  # rad/pixel horizontal
        
        # Scale factor from IR to HQ coordinates
        self.scale_factor = self.ir_angular_res / self.hq_angular_res
        
        # Center offsets (assuming cameras are centered on same target point)
        self.ir_center = (self.ir_resolution[0] / 2, self.ir_resolution[1] / 2)
        self.hq_center = (self.hq_resolution[0] / 2, self.hq_resolution[1] / 2)
        
        logger.debug(f"Scale factor IR->HQ: {self.scale_factor:.4f}")
        logger.debug(f"IR angular resolution: {math.degrees(self.ir_angular_res):.4f}°/px")
        logger.debug(f"HQ angular resolution: {math.degrees(self.hq_angular_res):.4f}°/px")
    
    def map_ir_point_to_hq(self, ir_point: Tuple[int, int]) -> Tuple[int, int]:
        """
        Map a point from IR camera coordinates to HQ camera coordinates
        
        Args:
            ir_point: (x, y) coordinates in IR camera space
            
        Returns:
            (x, y) coordinates in HQ camera space
        """
        ir_x, ir_y = ir_point
        
        # Convert IR pixel coordinates to angular coordinates relative to center
        ir_angle_x = (ir_x - self.ir_center[0]) * self.ir_angular_res
        ir_angle_y = (ir_y - self.ir_center[1]) * self.ir_angular_res
        
        # Convert angular coordinates to HQ pixel coordinates
        hq_x = int(ir_angle_x / self.hq_angular_res + self.hq_center[0])
        hq_y = int(ir_angle_y / self.hq_angular_res + self.hq_center[1])
        
        # Clamp to HQ resolution bounds
        hq_x = max(0, min(hq_x, self.hq_resolution[0] - 1))
        hq_y = max(0, min(hq_y, self.hq_resolution[1] - 1))
        
        return (hq_x, hq_y)
    
    def map_ir_bbox_to_hq(self, ir_bbox: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
        """
        Map a bounding box from IR camera coordinates to HQ camera coordinates
        
        Args:
            ir_bbox: (x, y, width, height) in IR camera space
            
        Returns:
            (x, y, width, height) in HQ camera space
        """
        ir_x, ir_y, ir_w, ir_h = ir_bbox
        
        # Map all four corners of the bounding box
        top_left = self.map_ir_point_to_hq((ir_x, ir_y))
        top_right = self.map_ir_point_to_hq((ir_x + ir_w, ir_y))
        bottom_left = self.map_ir_point_to_hq((ir_x, ir_y + ir_h))
        bottom_right = self.map_ir_point_to_hq((ir_x + ir_w, ir_y + ir_h))
        
        # Find the bounding rectangle of the mapped corners
        all_x = [top_left[0], top_right[0], bottom_left[0], bottom_right[0]]
        all_y = [top_left[1], top_right[1], bottom_left[1], bottom_right[1]]
        
        hq_x = min(all_x)
        hq_y = min(all_y)
        hq_w = max(all_x) - hq_x
        hq_h = max(all_y) - hq_y
        
        # Ensure positive dimensions
        hq_w = max(1, hq_w)
        hq_h = max(1, hq_h)
        
        return (hq_x, hq_y, hq_w, hq_h)
    
    def map_hq_point_to_ir(self, hq_point: Tuple[int, int]) -> Tuple[int, int]:
        """
        Map a point from HQ camera coordinates to IR camera coordinates
        
        Args:
            hq_point: (x, y) coordinates in HQ camera space
            
        Returns:
            (x, y) coordinates in IR camera space
        """
        hq_x, hq_y = hq_point
        
        # Convert HQ pixel coordinates to angular coordinates relative to center
        hq_angle_x = (hq_x - self.hq_center[0]) * self.hq_angular_res
        hq_angle_y = (hq_y - self.hq_center[1]) * self.hq_angular_res
        
        # Convert angular coordinates to IR pixel coordinates
        ir_x = int(hq_angle_x / self.ir_angular_res + self.ir_center[0])
        ir_y = int(hq_angle_y / self.ir_angular_res + self.ir_center[1])
        
        # Clamp to IR resolution bounds
        ir_x = max(0, min(ir_x, self.ir_resolution[0] - 1))
        ir_y = max(0, min(ir_y, self.ir_resolution[1] - 1))
        
        return (ir_x, ir_y)
    
    def get_scale_info(self) -> dict:
        """Get scaling information for debugging and calibration"""
        return {
            'ir_fov_degrees': self.ir_fov_degrees,
            'hq_fov_degrees': self.hq_fov_degrees,
            'ir_resolution': self.ir_resolution,
            'hq_resolution': self.hq_resolution,
            'scale_factor': self.scale_factor,
            'ir_angular_resolution_deg_per_pixel': math.degrees(self.ir_angular_res),
            'hq_angular_resolution_deg_per_pixel': math.degrees(self.hq_angular_res),
            'fov_ratio': self.hq_fov_degrees / self.ir_fov_degrees
        }
    
    def update_fov_settings(self, ir_fov_degrees: Optional[float] = None, hq_fov_degrees: Optional[float] = None):
        """
        Update FOV settings dynamically (useful for calibration)
        
        Args:
            ir_fov_degrees: New IR camera FOV in degrees
            hq_fov_degrees: New HQ camera FOV in degrees
        """
        if ir_fov_degrees is not None:
            self.ir_fov_degrees = ir_fov_degrees
            self.ir_fov_rad = math.radians(ir_fov_degrees)
            
        if hq_fov_degrees is not None:
            self.hq_fov_degrees = hq_fov_degrees
            self.hq_fov_rad = math.radians(hq_fov_degrees)
        
        # Recalculate scale factors
        self._calculate_scale_factors()
        
        logger.info(f"FOV settings updated: IR={self.ir_fov_degrees}°, HQ={self.hq_fov_degrees}°")
    
    def validate_mapping(self, test_points: list = None) -> dict:
        """
        Validate the mapping with test points
        
        Args:
            test_points: List of (x, y) points in IR space to test, or None for default test points
            
        Returns:
            Dictionary with validation results
        """
        if test_points is None:
            # Default test points: center and corners of IR frame
            test_points = [
                (int(self.ir_resolution[0] / 2), int(self.ir_resolution[1] / 2)),  # Center
                (0, 0),  # Top-left
                (self.ir_resolution[0] - 1, 0),  # Top-right
                (0, self.ir_resolution[1] - 1),  # Bottom-left
                (self.ir_resolution[0] - 1, self.ir_resolution[1] - 1),  # Bottom-right
            ]
        
        results = []
        for ir_point in test_points:
            hq_point = self.map_ir_point_to_hq(ir_point)
            # Test round-trip accuracy
            ir_back = self.map_hq_point_to_ir(hq_point)
            
            # Calculate error
            error_x = abs(ir_point[0] - ir_back[0])
            error_y = abs(ir_point[1] - ir_back[1])
            error_distance = math.sqrt(error_x**2 + error_y**2)
            
            results.append({
                'ir_original': ir_point,
                'hq_mapped': hq_point,
                'ir_back': ir_back,
                'error_pixels': error_distance,
                'error_x': error_x,
                'error_y': error_y
            })
        
        # Calculate average error
        avg_error = sum(r['error_pixels'] for r in results) / len(results)
        max_error = max(r['error_pixels'] for r in results)
        
        return {
            'test_results': results,
            'average_error_pixels': avg_error,
            'max_error_pixels': max_error,
            'scale_info': self.get_scale_info()
        }