#!/usr/bin/env python3
"""
Automated Timelapse Service for UFO Tracker
Continuously captures HQ and IR frames and compiles them into hourly movies
"""

import os
import time
import threading
import requests
import cv2
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List
import json
import glob
import shutil
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/mark/ufo-tracker/logs/timelapse_service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TimelapseService:
    def __init__(self):
        self.base_dir = "/home/mark/ufo-tracker"
        self.temp_frames_dir = os.path.join(self.base_dir, "temp/timelapse_frames")
        self.output_dir = os.path.join(self.base_dir, "static/gallery/videos")
        self.frame_service_url = "http://localhost:5002"
        
        # Capture settings
        self.capture_interval = 60  # Capture every 60 seconds
        self.frames_per_hour = 60   # Should give us 60 frames per hour
        self.fps = 10               # Output video FPS
        self.quality = 85           # JPEG quality for temp frames
        
        # Threading
        self.running = False
        self.capture_thread = None
        self.compile_thread = None
        self.lock = threading.Lock()
        
        # Current hour tracking
        self.current_hour = datetime.now().strftime("%Y-%m-%d_%H")
        
        self.setup_directories()
        
    def setup_directories(self):
        """Create necessary directories"""
        try:
            os.makedirs(self.temp_frames_dir, exist_ok=True)
            os.makedirs(os.path.join(self.temp_frames_dir, "hq"), exist_ok=True)
            os.makedirs(os.path.join(self.temp_frames_dir, "ir"), exist_ok=True)
            os.makedirs(self.output_dir, exist_ok=True)
            logger.info("Timelapse directories created")
        except Exception as e:
            logger.error(f"Failed to create directories: {e}")
            
    def capture_frames(self):
        """Continuously capture frames from both cameras"""
        logger.info("Starting frame capture thread")
        
        while self.running:
            try:
                current_hour = datetime.now().strftime("%Y-%m-%d_%H")
                
                # Check if we've moved to a new hour
                if current_hour != self.current_hour:
                    logger.info(f"Hour changed from {self.current_hour} to {current_hour}")
                    old_hour = self.current_hour
                    self.current_hour = current_hour
                    
                    # Trigger compilation of the completed hour
                    threading.Thread(target=self.compile_hour, args=(old_hour,)).start()
                
                # Capture current frames
                timestamp = datetime.now()
                self.capture_camera_frame("hq", timestamp)
                self.capture_camera_frame("ir", timestamp)
                
                # Wait for next capture interval
                time.sleep(self.capture_interval)
                
            except Exception as e:
                logger.error(f"Error in frame capture: {e}")
                time.sleep(30)  # Wait before retrying
                
        logger.info("Frame capture thread stopped")
        
    def capture_camera_frame(self, camera: str, timestamp: datetime):
        """Capture a single frame from a camera"""
        try:
            # Get frame from frame service
            response = requests.get(f"{self.frame_service_url}/{camera}_frame", 
                                  timeout=10, stream=True)
            
            if response.status_code == 200:
                # Save frame with timestamp
                filename = f"{camera}_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
                hour_dir = os.path.join(self.temp_frames_dir, camera, self.current_hour)
                os.makedirs(hour_dir, exist_ok=True)
                
                filepath = os.path.join(hour_dir, filename)
                
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Verify file was saved
                if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
                    logger.debug(f"Captured {camera} frame: {filename}")
                    return filepath
                else:
                    logger.warning(f"Failed to save {camera} frame properly")
                    
            else:
                logger.warning(f"Failed to get {camera} frame: HTTP {response.status_code}")
                
        except requests.RequestException as e:
            logger.error(f"Network error capturing {camera} frame: {e}")
        except Exception as e:
            logger.error(f"Error capturing {camera} frame: {e}")
            
        return None
        
    def compile_hour(self, hour_key: str):
        """Compile frames for a completed hour into video"""
        logger.info(f"Starting compilation for hour: {hour_key}")
        
        try:
            # Compile both cameras
            hq_video = self.create_timelapse_video("hq", hour_key)
            ir_video = self.create_timelapse_video("ir", hour_key)
            
            # Create combined video if both cameras have footage
            if hq_video and ir_video:
                self.create_combined_timelapse(hour_key, hq_video, ir_video)
            
            # Cleanup temp frames for this hour
            self.cleanup_temp_frames(hour_key)
            
            logger.info(f"Compilation completed for hour: {hour_key}")
            
        except Exception as e:
            logger.error(f"Error compiling hour {hour_key}: {e}")
            
    def create_timelapse_video(self, camera: str, hour_key: str) -> Optional[str]:
        """Create timelapse video for one camera"""
        try:
            frames_dir = os.path.join(self.temp_frames_dir, camera, hour_key)
            
            if not os.path.exists(frames_dir):
                logger.warning(f"No frames directory for {camera} {hour_key}")
                return None
                
            # Get all frame files
            frame_files = sorted(glob.glob(os.path.join(frames_dir, f"{camera}_*.jpg")))
            
            if len(frame_files) < 5:  # Need at least 5 frames
                logger.warning(f"Not enough frames for {camera} {hour_key}: {len(frame_files)}")
                return None
                
            logger.info(f"Creating {camera} timelapse with {len(frame_files)} frames")
            
            # Output filename
            output_filename = f"timelapse_{camera}_{hour_key}.mp4"
            output_path = os.path.join(self.output_dir, output_filename)
            
            # Read first frame to get dimensions
            first_frame = cv2.imread(frame_files[0])
            if first_frame is None:
                logger.error(f"Failed to read first frame: {frame_files[0]}")
                return None
                
            height, width, _ = first_frame.shape
            
            # Create video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            video_writer = cv2.VideoWriter(output_path, fourcc, self.fps, (width, height))
            
            if not video_writer.isOpened():
                logger.error(f"Failed to create video writer for {output_path}")
                return None
                
            frames_written = 0
            
            for frame_file in frame_files:
                frame = cv2.imread(frame_file)
                if frame is None:
                    continue
                    
                # Resize if necessary
                if frame.shape[:2] != (height, width):
                    frame = cv2.resize(frame, (width, height))
                
                # Extract timestamp from filename for overlay
                basename = os.path.basename(frame_file)
                timestamp_str = self.extract_timestamp_from_filename(basename)
                
                # Add timestamp and camera overlay
                if timestamp_str:
                    cv2.putText(frame, timestamp_str, (10, 30), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                cv2.putText(frame, camera.upper(), (10, height - 30), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                video_writer.write(frame)
                frames_written += 1
                
            video_writer.release()
            
            if frames_written > 0:
                logger.info(f"Created {camera} timelapse: {output_filename} ({frames_written} frames)")
                return output_path
            else:
                # Remove empty file
                if os.path.exists(output_path):
                    os.remove(output_path)
                return None
                
        except Exception as e:
            logger.error(f"Error creating {camera} timelapse for {hour_key}: {e}")
            return None
            
    def create_combined_timelapse(self, hour_key: str, hq_video: str, ir_video: str):
        """Create side-by-side combined timelapse"""
        try:
            output_filename = f"timelapse_combined_{hour_key}.mp4"
            output_path = os.path.join(self.output_dir, output_filename)
            
            # Use ffmpeg to create side-by-side video
            cmd = [
                'ffmpeg', '-y',  # Overwrite output
                '-i', hq_video,  # Input 1 (HQ)
                '-i', ir_video,  # Input 2 (IR)
                '-filter_complex', '[0:v][1:v]hstack=inputs=2',  # Side by side
                '-c:v', 'libx264',  # H.264 codec
                '-crf', '23',       # Quality
                '-preset', 'medium', # Encoding speed
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                logger.info(f"Created combined timelapse: {output_filename}")
                return output_path
            else:
                logger.error(f"ffmpeg error: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error(f"ffmpeg timeout creating combined timelapse for {hour_key}")
            return None
        except Exception as e:
            logger.error(f"Error creating combined timelapse for {hour_key}: {e}")
            return None
            
    def extract_timestamp_from_filename(self, filename: str) -> Optional[str]:
        """Extract timestamp from frame filename"""
        try:
            # Format: camera_YYYYMMDD_HHMMSS.jpg
            parts = filename.replace('.jpg', '').split('_')
            if len(parts) >= 3:
                date_str = parts[1]  # YYYYMMDD
                time_str = parts[2]  # HHMMSS
                
                # Parse and format
                dt = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
                return dt.strftime("%Y-%m-%d %H:%M:%S")
                
        except Exception as e:
            logger.debug(f"Failed to parse timestamp from {filename}: {e}")
            
        return None
        
    def cleanup_temp_frames(self, hour_key: str):
        """Remove temporary frames for a completed hour"""
        try:
            for camera in ["hq", "ir"]:
                frames_dir = os.path.join(self.temp_frames_dir, camera, hour_key)
                if os.path.exists(frames_dir):
                    shutil.rmtree(frames_dir)
                    logger.info(f"Cleaned up temp frames for {camera} {hour_key}")
                    
        except Exception as e:
            logger.error(f"Error cleaning up temp frames for {hour_key}: {e}")
            
    def start(self):
        """Start the timelapse service"""
        if self.running:
            logger.warning("Timelapse service already running")
            return
            
        logger.info("Starting timelapse service")
        self.running = True
        
        # Start capture thread
        self.capture_thread = threading.Thread(target=self.capture_frames, daemon=True)
        self.capture_thread.start()
        
        logger.info("Timelapse service started successfully")
        
    def stop(self):
        """Stop the timelapse service"""
        if not self.running:
            return
            
        logger.info("Stopping timelapse service")
        self.running = False
        
        # Wait for threads to complete
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=30)
            
        logger.info("Timelapse service stopped")
        
    def get_status(self) -> Dict:
        """Get service status"""
        return {
            "running": self.running,
            "current_hour": self.current_hour,
            "capture_interval": self.capture_interval,
            "temp_frames_dir": self.temp_frames_dir,
            "output_dir": self.output_dir,
            "frames_captured_this_hour": self.count_frames_this_hour()
        }
        
    def count_frames_this_hour(self) -> Dict[str, int]:
        """Count frames captured in current hour"""
        counts = {"hq": 0, "ir": 0}
        
        try:
            for camera in ["hq", "ir"]:
                frames_dir = os.path.join(self.temp_frames_dir, camera, self.current_hour)
                if os.path.exists(frames_dir):
                    counts[camera] = len(glob.glob(os.path.join(frames_dir, f"{camera}_*.jpg")))
                    
        except Exception as e:
            logger.error(f"Error counting frames: {e}")
            
        return counts
        
    def cleanup_old_videos(self, days_to_keep: int = 7):
        """Remove timelapse videos older than specified days"""
        try:
            cutoff_time = datetime.now() - timedelta(days=days_to_keep)
            pattern = os.path.join(self.output_dir, "timelapse_*.mp4")
            video_files = glob.glob(pattern)
            
            deleted_count = 0
            for filepath in video_files:
                stat = os.stat(filepath)
                file_time = datetime.fromtimestamp(stat.st_mtime)
                
                if file_time < cutoff_time:
                    os.remove(filepath)
                    deleted_count += 1
                    logger.info(f"Deleted old timelapse: {os.path.basename(filepath)}")
                    
            logger.info(f"Cleaned up {deleted_count} old timelapse videos")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old timelapses: {e}")
            return 0


def main():
    """Run the timelapse service"""
    service = TimelapseService()
    
    try:
        service.start()
        
        # Keep running
        while True:
            time.sleep(60)
            status = service.get_status()
            logger.info(f"Service status: {status}")
            
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        service.stop()


if __name__ == "__main__":
    main()