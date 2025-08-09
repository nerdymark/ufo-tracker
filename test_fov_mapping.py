#!/usr/bin/env python3
"""
Test script for FOV mapping functionality
Tests coordinate transformation between IR and HQ cameras
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from detection.fov_mapper import FOVMapper

def test_fov_mapping():
    """Test the FOV mapping functionality"""
    print("Testing FOV Mapping System")
    print("=" * 50)
    
    # Initialize mapper
    mapper = FOVMapper()
    scale_info = mapper.get_scale_info()
    
    print(f"IR Camera: {scale_info['ir_fov_degrees']}° FOV, {scale_info['ir_resolution']} resolution")
    print(f"HQ Camera: {scale_info['hq_fov_degrees']}° FOV, {scale_info['hq_resolution']} resolution")
    print(f"Scale Factor: {scale_info['scale_factor']:.4f}")
    print(f"FOV Ratio: {scale_info['fov_ratio']:.2f}")
    print()
    
    # Test individual point mapping
    print("Point Mapping Tests:")
    print("-" * 30)
    
    test_points = [
        (0, 0),           # Top-left corner
        (640, 360),       # Center of IR frame (1280x720)
        (1279, 719),      # Bottom-right corner
        (320, 180),       # Quarter point
        (960, 540),       # Three-quarter point
    ]
    
    for ir_point in test_points:
        hq_point = mapper.map_ir_point_to_hq(ir_point)
        ir_back = mapper.map_hq_point_to_ir(hq_point)
        
        error_x = abs(ir_point[0] - ir_back[0])
        error_y = abs(ir_point[1] - ir_back[1])
        
        print(f"IR {ir_point} -> HQ {hq_point} -> IR {ir_back} (error: {error_x}, {error_y})")
    
    print()
    
    # Test bounding box mapping
    print("Bounding Box Mapping Tests:")
    print("-" * 40)
    
    test_bboxes = [
        (100, 100, 200, 150),   # Small box in top-left area
        (540, 310, 200, 100),   # Box near center
        (900, 500, 300, 180),   # Box in bottom-right area
        (0, 0, 100, 100),       # Corner box
        (600, 300, 80, 120),    # Small centered box
    ]
    
    for ir_bbox in test_bboxes:
        hq_bbox = mapper.map_ir_bbox_to_hq(ir_bbox)
        
        # Calculate size change
        ir_area = ir_bbox[2] * ir_bbox[3]
        hq_area = hq_bbox[2] * hq_bbox[3]
        area_ratio = hq_area / ir_area if ir_area > 0 else 0
        
        print(f"IR bbox {ir_bbox} -> HQ bbox {hq_bbox}")
        print(f"  Area change: {ir_area} -> {hq_area} (ratio: {area_ratio:.3f})")
        print()
    
    # Run validation
    print("Validation Test:")
    print("-" * 20)
    validation = mapper.validate_mapping()
    
    print(f"Average mapping error: {validation['average_error_pixels']:.2f} pixels")
    print(f"Maximum mapping error: {validation['max_error_pixels']:.2f} pixels")
    print()
    
    # Show detailed validation results
    print("Detailed Validation Results:")
    for i, result in enumerate(validation['test_results']):
        print(f"  Test {i+1}: {result['ir_original']} -> {result['hq_mapped']} -> {result['ir_back']}")
        print(f"           Error: {result['error_pixels']:.2f}px")
    
    print("\nTest completed successfully!")
    return True

def test_fov_adjustments():
    """Test FOV setting adjustments"""
    print("\nTesting FOV Adjustments:")
    print("=" * 30)
    
    mapper = FOVMapper()
    
    # Test different FOV settings
    test_fovs = [
        (30, 40),  # Narrower IR, narrower HQ
        (35, 45),  # Default settings
        (40, 50),  # Wider IR, wider HQ
        (35, 60),  # Default IR, much wider HQ
    ]
    
    for ir_fov, hq_fov in test_fovs:
        mapper.update_fov_settings(ir_fov, hq_fov)
        scale_info = mapper.get_scale_info()
        
        print(f"FOV IR:{ir_fov}° HQ:{hq_fov}° -> Scale:{scale_info['scale_factor']:.4f}, Ratio:{scale_info['fov_ratio']:.2f}")
        
        # Test center point mapping with these settings
        center_ir = (640, 360)
        center_hq = mapper.map_ir_point_to_hq(center_ir)
        print(f"  Center mapping: {center_ir} -> {center_hq}")
    
    print("\nFOV adjustment tests completed!")

if __name__ == "__main__":
    try:
        test_fov_mapping()
        test_fov_adjustments()
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)