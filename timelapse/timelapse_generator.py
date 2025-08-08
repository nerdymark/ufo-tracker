#!/usr/bin/env python3
"""
Timelapse Generator for UFO Tracker
Creates timelapse videos from detected images
"""

import os
import cv2
import glob
import logging
from datetime import datetime, timedelta
from pathlib import Path
import json
import subprocess

logger = logging.getLogger(__name__)

class TimelapseGenerator:
    def __init__(self, detections_dir="/home/mark/ufo-tracker/detections"):
        self.detections_dir = detections_dir
        self.output_dir = "/home/mark/ufo-tracker/timelapses"
        self.thumbnails_dir = os.path.join(self.output_dir, "thumbnails")
        self.ensure_output_dir()
        
    def ensure_output_dir(self):
        """Ensure timelapses output directory exists"""
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.thumbnails_dir, exist_ok=True)
        
    def parse_timestamp_from_filename(self, filename):
        """Parse timestamp from detection filename (e.g., detection_20250803_184429_949.jpg)"""
        try:
            if filename.startswith("detection_"):
                # Format: detection_YYYYMMDD_HHMMSS_mmm.jpg
                parts = filename.replace("detection_", "").replace(".jpg", "").split("_")
                if len(parts) >= 3:
                    date_str = parts[0]  # YYYYMMDD
                    time_str = parts[1]  # HHMMSS
                    ms_str = parts[2]    # mmm
                    
                    # Parse date and time
                    year = int(date_str[:4])
                    month = int(date_str[4:6])
                    day = int(date_str[6:8])
                    hour = int(time_str[:2])
                    minute = int(time_str[2:4])
                    second = int(time_str[4:6])
                    microsecond = int(ms_str) * 1000  # Convert ms to microseconds
                    
                    return datetime(year, month, day, hour, minute, second, microsecond)
        except Exception as e:
            logger.warning(f"Failed to parse timestamp from {filename}: {e}")
        return None
        
    def get_detection_images_by_hour(self, target_date=None, max_images_per_hour=500):
        """Group detection images by hour with optimized collection"""
        if target_date is None:
            target_date = datetime.now().date()
            
        logger.info(f"Collecting detection images for {target_date}")
        
        # Get all detection images (this can be slow with many files)
        pattern = os.path.join(self.detections_dir, "detection_*.jpg")
        image_files = glob.glob(pattern)
        
        logger.info(f"Found {len(image_files)} total detection files")
        
        # Group by hour
        hourly_groups = {}
        processed_count = 0
        
        for filepath in image_files:
            filename = os.path.basename(filepath)
            timestamp = self.parse_timestamp_from_filename(filename)
            
            if timestamp and timestamp.date() == target_date:
                # Group by hour (format: YYYY-MM-DD_HH)
                hour_key = timestamp.strftime("%Y-%m-%d_%H")
                
                if hour_key not in hourly_groups:
                    hourly_groups[hour_key] = []
                    
                # Limit images per hour to prevent memory issues
                if len(hourly_groups[hour_key]) < max_images_per_hour:
                    hourly_groups[hour_key].append({
                        'filepath': filepath,
                        'timestamp': timestamp,
                        'filename': filename
                    })
                    
            processed_count += 1
            if processed_count % 1000 == 0:
                logger.info(f"Processed {processed_count}/{len(image_files)} files")
        
        # Sort images within each hour by timestamp
        for hour_key in hourly_groups:
            hourly_groups[hour_key].sort(key=lambda x: x['timestamp'])
            logger.info(f"Hour {hour_key}: {len(hourly_groups[hour_key])} images")
            
        return hourly_groups
        
    def create_hourly_timelapse(self, hour_key, images, fps=10, quality=85, max_frames=300):
        """Create a timelapse video for a specific hour"""
        try:
            if not images:
                logger.warning(f"No images found for hour {hour_key}")
                return None
            
            # Sample images if there are too many (for performance and reasonable video length)
            if len(images) > max_frames:
                logger.info(f"Sampling {max_frames} images from {len(images)} total images for {hour_key}")
                # Sample evenly across the time period
                step = len(images) // max_frames
                sampled_images = images[::step][:max_frames]
            else:
                sampled_images = images
                
            logger.info(f"Creating timelapse for {hour_key} with {len(sampled_images)} frames")
            
            # Output filename: timelapse_YYYY-MM-DD_HH.mp4
            output_filename = f"timelapse_{hour_key}.mp4"
            output_path = os.path.join(self.output_dir, output_filename)
            
            # Read first image to get dimensions
            first_image = cv2.imread(sampled_images[0]['filepath'])
            if first_image is None:
                logger.error(f"Failed to read first image: {sampled_images[0]['filepath']}")
                return None
                
            height, width, layers = first_image.shape
            
            # Use H.264 codec for better compression and compatibility
            # Try different codecs in order of preference
            codecs_to_try = [
                ('avc1', cv2.VideoWriter_fourcc(*'avc1')),  # H.264 (best compatibility)
                ('H264', cv2.VideoWriter_fourcc(*'H264')),  # H.264 alternative
                ('mp4v', cv2.VideoWriter_fourcc(*'mp4v')),  # MPEG-4 (fallback)
                ('XVID', cv2.VideoWriter_fourcc(*'XVID'))   # XVID (last resort)
            ]
            
            video_writer = None
            used_codec = None
            
            for codec_name, fourcc in codecs_to_try:
                video_writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
                if video_writer.isOpened():
                    used_codec = codec_name
                    logger.info(f"Using {codec_name} codec for {hour_key}")
                    break
                else:
                    video_writer.release()
            
            if not video_writer or not video_writer.isOpened():
                logger.error(f"Failed to open video writer with any codec for {output_path}")
                return None
            
            frames_added = 0
            total_frames = len(sampled_images)
            
            for i, image_info in enumerate(sampled_images):
                filepath = image_info['filepath']
                timestamp = image_info['timestamp']
                
                # Read image
                frame = cv2.imread(filepath)
                if frame is None:
                    logger.warning(f"Failed to read image: {filepath}")
                    continue
                    
                # Resize if necessary to match first image dimensions
                if frame.shape[:2] != (height, width):
                    frame = cv2.resize(frame, (width, height))
                
                # Add timestamp overlay (smaller and more readable)
                timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                cv2.putText(frame, timestamp_str, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                # Add progress indicator
                progress_text = f"Frame {frames_added + 1}/{total_frames} ({(frames_added + 1) / total_frames * 100:.1f}%)"
                cv2.putText(frame, progress_text, (10, height - 20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                
                video_writer.write(frame)
                frames_added += 1
                
                # Log progress every 50 frames
                if frames_added % 50 == 0:
                    logger.info(f"Progress: {frames_added}/{total_frames} frames processed for {hour_key}")
                
            video_writer.release()
            
            if frames_added > 0:
                # Get file size
                file_size = os.path.getsize(output_path)
                
                logger.info(f"Created timelapse {output_filename} with {frames_added} frames ({file_size} bytes)")
                
                # Generate thumbnail
                thumbnail_path = self.generate_thumbnail(output_path, output_filename)
                
                return {
                    'filename': output_filename,
                    'filepath': output_path,
                    'hour': hour_key,
                    'frame_count': frames_added,
                    'original_images': len(images),
                    'sampled_images': len(sampled_images),
                    'duration_seconds': frames_added / fps,
                    'fps': fps,
                    'file_size': file_size,
                    'created': datetime.now().isoformat(),
                    'thumbnail': thumbnail_path
                }
            else:
                # Remove empty file
                if os.path.exists(output_path):
                    os.remove(output_path)
                logger.warning(f"No frames added to timelapse for {hour_key}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating timelapse for {hour_key}: {e}")
            return None
    
    def generate_thumbnail(self, video_path, video_filename):
        """Generate a thumbnail image from the middle of the video"""
        try:
            # Create thumbnail filename
            thumbnail_filename = video_filename.replace('.mp4', '_thumb.jpg')
            thumbnail_path = os.path.join(self.thumbnails_dir, thumbnail_filename)
            
            # Use OpenCV to extract a frame from the middle of the video
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"Failed to open video for thumbnail: {video_path}")
                return None
            
            # Get video properties
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames <= 0:
                logger.error(f"Video has no frames: {video_path}")
                cap.release()
                return None
            
            # Seek to middle frame
            middle_frame = total_frames // 2
            cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame)
            
            # Read the frame
            ret, frame = cap.read()
            cap.release()
            
            if not ret or frame is None:
                logger.error(f"Failed to read frame for thumbnail: {video_path}")
                return None
            
            # Resize to thumbnail size (320x240) while maintaining aspect ratio
            height, width = frame.shape[:2]
            thumb_width = 320
            thumb_height = int((thumb_width / width) * height)
            
            # Ensure height doesn't exceed reasonable bounds
            if thumb_height > 240:
                thumb_height = 240
                thumb_width = int((thumb_height / height) * width)
            
            thumbnail = cv2.resize(frame, (thumb_width, thumb_height))
            
            # Save thumbnail
            success = cv2.imwrite(thumbnail_path, thumbnail, [cv2.IMWRITE_JPEG_QUALITY, 85])
            
            if success:
                logger.info(f"Generated thumbnail: {thumbnail_filename}")
                return thumbnail_filename
            else:
                logger.error(f"Failed to save thumbnail: {thumbnail_path}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating thumbnail for {video_filename}: {e}")
            return None
            
    def create_all_hourly_timelapses(self, target_date=None, fps=10):
        """Create timelapse videos for all hours with detection images"""
        if target_date is None:
            target_date = datetime.now().date()
            
        logger.info(f"Creating hourly timelapses for {target_date}")
        
        # Get images grouped by hour
        hourly_groups = self.get_detection_images_by_hour(target_date)
        
        if not hourly_groups:
            logger.info(f"No detection images found for {target_date}")
            return []
            
        created_timelapses = []
        
        for hour_key, images in hourly_groups.items():
            logger.info(f"Processing hour {hour_key} with {len(images)} images")
            
            # Skip if too few images (need at least 10 for a meaningful timelapse)
            if len(images) < 10:
                logger.info(f"Skipping {hour_key} - only {len(images)} images (minimum 10 required)")
                continue
                
            timelapse_info = self.create_hourly_timelapse(hour_key, images, fps)
            if timelapse_info:
                created_timelapses.append(timelapse_info)
                
        logger.info(f"Created {len(created_timelapses)} timelapse videos for {target_date}")
        return created_timelapses
        
    def get_available_timelapses(self):
        """Get list of available timelapse videos"""
        try:
            pattern = os.path.join(self.output_dir, "timelapse_*.mp4")
            timelapse_files = glob.glob(pattern)
            
            timelapses = []
            for filepath in timelapse_files:
                filename = os.path.basename(filepath)
                stat = os.stat(filepath)
                
                # Parse hour from filename: timelapse_YYYY-MM-DD_HH.mp4
                hour_key = filename.replace("timelapse_", "").replace(".mp4", "")
                
                # Check for thumbnail
                thumbnail_filename = filename.replace('.mp4', '_thumb.jpg')
                thumbnail_path = os.path.join(self.thumbnails_dir, thumbnail_filename)
                thumbnail_url = f"/timelapse/thumbnails/{thumbnail_filename}" if os.path.exists(thumbnail_path) else None
                
                timelapses.append({
                    'filename': filename,
                    'hour': hour_key,
                    'file_size': stat.st_size,
                    'created': stat.st_mtime,
                    'url': f"/timelapse/{filename}",
                    'thumbnail': thumbnail_url
                })
                
            # Sort by creation time (newest first)
            timelapses.sort(key=lambda x: x['created'], reverse=True)
            
            return timelapses
            
        except Exception as e:
            logger.error(f"Error listing timelapses: {e}")
            return []
            
    def delete_timelapse(self, filename):
        """Delete a specific timelapse video"""
        try:
            filepath = os.path.join(self.output_dir, filename)
            if os.path.exists(filepath) and filename.startswith("timelapse_") and filename.endswith(".mp4"):
                os.remove(filepath)
                logger.info(f"Deleted timelapse: {filename}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting timelapse {filename}: {e}")
            return False
            
    def cleanup_old_timelapses(self, days_to_keep=7):
        """Remove timelapse videos older than specified days"""
        try:
            cutoff_time = datetime.now() - timedelta(days=days_to_keep)
            pattern = os.path.join(self.output_dir, "timelapse_*.mp4")
            timelapse_files = glob.glob(pattern)
            
            deleted_count = 0
            for filepath in timelapse_files:
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
    """Test the timelapse generator"""
    logging.basicConfig(level=logging.INFO)
    
    generator = TimelapseGenerator()
    
    # Create timelapses for today
    timelapses = generator.create_all_hourly_timelapses()
    print(f"Created {len(timelapses)} timelapses")
    
    # List available timelapses
    available = generator.get_available_timelapses()
    print(f"Available timelapses: {len(available)}")
    for tl in available:
        print(f"  - {tl['filename']} ({tl['file_size']} bytes)")


if __name__ == "__main__":
    main()
