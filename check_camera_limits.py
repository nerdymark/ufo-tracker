#!/usr/bin/env python3
"""
Check actual camera control limits for gain and exposure
"""

from picamera2 import Picamera2
import json

def check_camera_controls(camera_index, camera_name):
    print(f"\n{camera_name} (index {camera_index}):")
    print("="*50)
    
    try:
        camera = Picamera2(camera_index)
        
        # Get camera controls
        controls = camera.camera_controls
        
        # Check AnalogueGain limits
        if "AnalogueGain" in controls:
            gain_info = controls["AnalogueGain"]
            print(f"AnalogueGain: min={gain_info[0]}, max={gain_info[1]}, default={gain_info[2]}")
        
        # Check ExposureTime limits
        if "ExposureTime" in controls:
            exp_info = controls["ExposureTime"]
            print(f"ExposureTime: min={exp_info[0]}, max={exp_info[1]}, default={exp_info[2]}")
        
        # Check other relevant controls
        if "Brightness" in controls:
            bright_info = controls["Brightness"]
            print(f"Brightness: min={bright_info[0]}, max={bright_info[1]}, default={bright_info[2]}")
        
        if "Contrast" in controls:
            contrast_info = controls["Contrast"]
            print(f"Contrast: min={contrast_info[0]}, max={contrast_info[1]}, default={contrast_info[2]}")
        
        camera.close()
        
    except Exception as e:
        print(f"Error accessing camera: {e}")

if __name__ == "__main__":
    print("Checking camera control limits...")
    
    # Check IR camera (index 0)
    check_camera_controls(0, "IR Camera (IMX219)")
    
    # Check HQ camera (index 1)
    check_camera_controls(1, "HQ Camera (IMX477)")