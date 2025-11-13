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
    
    # ADSB Flight Tracking Settings
    ADSB = {
        'enabled': True,            # Enable ADSB flight tracking
        'piaware_url': 'http://10.0.1.249:8080/skyaware/data/aircraft.json',  # Local PiAware SkyAware ADSB feeder
        'max_distance_miles': 5.0,  # Maximum distance for flight display (miles)
        'update_interval': 10,      # Update interval in seconds
        'altitude_filter': {
            'min_feet': 0,          # Minimum altitude to display (feet)
            'max_feet': 50000       # Maximum altitude to display (feet)
        },
        'observer_location': {
            # Set your actual location coordinates here
            'latitude': 37.7749,    # San Francisco Bay Area (update with your location)
            'longitude': -122.4194,
            'altitude_feet': 100    # Observer altitude above sea level
        },
        'display_settings': {
            'show_all_flights': True,       # Show all flights within range
            'show_only_nearby': False,      # Only show flights within max_distance_miles
            'show_altitude_info': True,     # Show altitude and speed information
            'refresh_rate': 10,             # OPTIMIZED: Display refresh rate (was 15s, now matches backend)
            'max_display_count': 20         # Maximum number of flights to display
        }
    }
    
    # Satellite Tracking Settings
    SATELLITE = {
        'enabled': True,            # Enable satellite tracking
        'tle_url': 'https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle',  # CelesTrak TLE data source
        'min_elevation': 10.0,      # Minimum elevation angle in degrees (0 = horizon)
        'max_satellites': 1000,     # Maximum number of satellites to load (for performance)
        'update_interval': 30,      # Update interval in seconds
        'tle_refresh_hours': 6,     # How often to refresh TLE data (hours)
        'observer_location': {
            # Set your actual location coordinates here (should match ADSB location)
            'latitude': 37.7749,    # San Francisco Bay Area (update with your location)
            'longitude': -122.4194,
            'altitude_km': 0.1      # Observer altitude above sea level in kilometers
        },
        'display_settings': {
            'show_all_satellites': True,    # Show all satellites above min elevation
            'show_space_stations': True,    # Highlight space stations (ISS, Tiangong, etc.)
            'show_satellite_info': True,    # Show altitude, velocity, and category
            'refresh_rate': 30,             # Display refresh rate in seconds
            'max_display_count': 15         # Maximum number of satellites to display
        },
        'categories': {
            'space_stations': ['ISS', 'TIANHE', 'TIANGONG', 'CSS'],
            'navigation': ['GPS', 'GLONASS', 'GALILEO', 'BEIDOU'],
            'communications': ['STARLINK', 'ONEWEB', 'IRIDIUM'],
            'earth_observation': ['LANDSAT', 'SENTINEL', 'SPOT'],
            'weather': ['WEATHER', 'GOES', 'NOAA'],
            'science': ['HUBBLE', 'KEPLER', 'TESS']
        }
    }
    
    # Motion Sensor Settings (MPU9250)
    # PERFORMANCE OPTIMIZED: Sample rate reduced from 50Hz to 10Hz
    # This reduces I2C bus traffic by 80% while maintaining responsive tracking
    MOTION_SENSOR = {
        'enabled': True,            # Enable MPU9250 motion sensor
        'sample_rate': 10,          # OPTIMIZED: Samples per second (was 50Hz, now 10Hz = 80% reduction in I2C traffic)
        'motion_threshold': 2.0,    # Motion detection threshold (m/s²)
        'vibration_threshold': 10.0, # Vibration alert threshold (deg/s)
        'calibration_samples': 100,  # Number of samples for calibration
        'filter_alpha': 0.8,        # Low-pass filter coefficient (0-1)
        'i2c_address': 0x68,        # I2C address of MPU9250
        'range_settings': {
            'accelerometer': '±4g',  # ±2g, ±4g, ±8g, ±16g
            'gyroscope': '±500°/s',  # ±250°/s, ±500°/s, ±1000°/s, ±2000°/s
            'filter_bandwidth': '21Hz'  # 5Hz, 10Hz, 21Hz, 44Hz, 94Hz, 184Hz, 260Hz
        },
        'alert_thresholds': {
            'tilt_angle': 45.0,     # Alert if tilt exceeds this angle (degrees)
            'shock_threshold': 20.0, # Shock detection threshold (m/s²)
            'temperature_min': 0.0,  # Minimum operating temperature (°C)
            'temperature_max': 70.0  # Maximum operating temperature (°C)
        },
        'display_settings': {
            'show_raw_data': True,       # Show raw accelerometer/gyro values
            'show_orientation': True,    # Show pitch/roll/yaw
            'show_motion_alerts': True,  # Show motion detection alerts
            'show_temperature': True,    # Show sensor temperature
            'update_rate': 2,           # Widget update rate (seconds)
            'chart_history': 60         # Seconds of data to chart
        }
    }
