"""
UFO Tracker Configuration
Copy this file to config.py and modify settings as needed
"""

import os

class Config:
    """Configuration settings for UFO Tracker"""
    
    # Flask Application Settings
    HOST = '0.0.0.0'  # Allow connections from any IP
    PORT = 5000
    DEBUG = False
    SECRET_KEY = 'your-secret-key-change-this-in-production'
    
    # Camera Settings
    CAMERA_SETTINGS = {
        'ir_camera': {
            'index': 0,  # Camera index for IR camera
            'resolution': (640, 480),
            'framerate': 30,
            'auto_exposure': True,
            'exposure_time': 10000,  # microseconds
            'gain': 1.0
        },
        'hq_camera': {
            'index': 1,  # Camera index for HQ camera
            'resolution': (1920, 1080),
            'framerate': 15,
            'auto_exposure': True,
            'exposure_time': 10000,  # microseconds
            'gain': 1.0
        }
    }
    
    # Motion Detection Settings
    MOTION_DETECTION = {
        'sensitivity': 25,  # Motion detection sensitivity (lower = more sensitive)
        'min_area': 500,    # Minimum area for motion detection
        'blur_size': 21,    # Gaussian blur size for background subtraction
        'history': 500,     # Background subtractor history
        'var_threshold': 16, # Background subtractor variance threshold
        'detect_shadows': True
    }
    
    # Object Tracking Settings
    TRACKING = {
        'max_disappeared': 30,  # Max frames object can disappear before being deregistered
        'max_distance': 50,     # Max distance between centroids for tracking
        'zoom_factor': 2.0,     # Zoom factor for HQ camera when tracking
        'track_duration': 10    # Minimum tracking duration in seconds
    }
    
    # Pan-Tilt Settings (Placeholder for Waveshare controller)
    PAN_TILT = {
        'enabled': False,       # Set to True when hardware is ready
        'controller_type': 'waveshare',
        'pan_range': (-90, 90), # Pan range in degrees
        'tilt_range': (-30, 60), # Tilt range in degrees
        'step_size': 1.8,       # Step size in degrees
        'speed': 100,           # Movement speed (0-255)
        'acceleration': 50      # Acceleration (0-255)
    }
    
    # Streaming Settings
    STREAMING = {
        'jpeg_quality': 85,     # JPEG compression quality (1-100)
        'buffer_size': 3,       # Frame buffer size
        'max_viewers': 10,      # Maximum concurrent viewers
        'fps_limit': 30         # FPS limit for streams
    }
    
    # Storage Settings
    STORAGE = {
        'save_detections': True,    # Save detected objects
        'save_path': 'detections/', # Path to save detections
        'max_storage_gb': 10,       # Maximum storage in GB
        'cleanup_days': 7           # Delete files older than X days
    }
    
    # Logging Settings
    LOGGING = {
        'level': 'INFO',            # Logging level
        'file_path': 'logs/ufo_tracker.log',
        'max_size_mb': 10,          # Max log file size in MB
        'backup_count': 5           # Number of backup log files
    }
    
    # Network Settings
    NETWORK = {
        'stream_timeout': 30,       # Stream timeout in seconds
        'connection_timeout': 10,   # Connection timeout in seconds
        'retry_attempts': 3         # Number of retry attempts
    }
