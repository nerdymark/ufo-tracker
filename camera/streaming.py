"""
Streaming Output Handler for UFO Tracker
Manages video streaming for multiple concurrent viewers
"""

import logging
import threading
import time
import cv2
from typing import Generator, Optional, Set
from collections import deque

from config.config import Config

logger = logging.getLogger(__name__)

class StreamingOutput:
    """Handles video streaming output for multiple concurrent viewers"""
    
    def __init__(self):
        """Initialize streaming output"""
        self._current_frame_data: Optional[bytes] = None
        self._frame_lock = threading.RLock()
        self._viewers: Set[int] = set()
        self._viewer_lock = threading.RLock()
        self._active = True
        self._frame_ready = threading.Event()
        
        # Frame encoding settings
        self._jpeg_quality = Config.STREAMING['jpeg_quality']
        self._encode_params = [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality]
        
        logger.info("Simplified streaming output initialized")
    
    def write_frame(self, frame):
        """Write a new frame to the stream"""
        if not self._active:
            return
        
        try:
            # Frame from Picamera2 is in RGB format
            # Encode directly as JPEG without conversion - browsers expect RGB JPEGs
            success, buffer = cv2.imencode('.jpg', frame, self._encode_params)
            if success:
                # Store frame data directly as bytes
                frame_data = buffer.tobytes()
                
                with self._frame_lock:
                    # Replace current frame data
                    self._current_frame_data = frame_data
                    # Frame written successfully
                
                # Notify all waiting viewers that a new frame is available
                self._frame_ready.set()
                self._frame_ready.clear()
        
        except Exception as e:
            logger.error(f"Error writing frame to stream: {e}")
    
    def get_stream(self) -> Generator[bytes, None, None]:
        """Get streaming generator for Flask Response with proper multi-user support"""
        # Wait for first frame to be available
        timeout = 0
        while self._current_frame_data is None and timeout < 50:  # 5 second timeout
            time.sleep(0.1)
            timeout += 1
        
        if self._current_frame_data is None:
            logger.warning("No frame data available after timeout")
            return
        viewer_id = id(threading.current_thread())
        
        # Check viewer limit
        with self._viewer_lock:
            if len(self._viewers) >= Config.STREAMING['max_viewers']:
                logger.warning(f"Maximum viewers ({Config.STREAMING['max_viewers']}) reached, rejecting new connection")
                return
            self._viewers.add(viewer_id)
        
        logger.info(f"New viewer connected (ID: {viewer_id}), total viewers: {len(self._viewers)}")
        
        try:
            last_frame_data = None
            frame_count = 0
            consecutive_empty_frames = 0
            max_empty_frames = 150
            
            while self._active:
                try:
                    # Get current frame data (already stored as bytes)
                    frame_data = None
                    with self._frame_lock:
                        if self._current_frame_data:
                            # Frame data is already bytes, just copy reference
                            frame_data = self._current_frame_data
                            consecutive_empty_frames = 0
                        # No frame data check
                    
                    if frame_data and len(frame_data) > 0:
                        # Send frame using proper MJPEG format
                        try:
                            # Send frame in browser-compatible MJPEG format
                            yield b'--frame\r\n'
                            yield b'Content-Type: image/jpeg\r\n'
                            yield b'Content-Length: ' + str(len(frame_data)).encode() + b'\r\n\r\n'
                            yield frame_data
                            yield b'\r\n'
                            frame_count += 1
                            last_frame_data = frame_data  # Keep last known good frame
                            # Frame sent successfully
                            
                        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                            logger.info(f"Viewer {viewer_id} disconnected (broken pipe)")
                            break
                    
                    elif last_frame_data:
                        # If no new frame but we have a cached frame, send it to prevent timeout
                        try:
                            # Send cached frame in browser-compatible MJPEG format
                            yield b'--frame\r\n'
                            yield b'Content-Type: image/jpeg\r\n'
                            yield b'Content-Length: ' + str(len(last_frame_data)).encode() + b'\r\n\r\n'
                            yield last_frame_data
                            yield b'\r\n'
                            frame_count += 1
                        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                            logger.info(f"Viewer {viewer_id} disconnected (broken pipe)")
                            break
                        
                        consecutive_empty_frames += 1
                        if consecutive_empty_frames >= max_empty_frames:
                            logger.warning(f"Viewer {viewer_id} timed out after {max_empty_frames} repeat frames")
                            break
                    
                    else:
                        # No frame available at all
                        consecutive_empty_frames += 1
                        if consecutive_empty_frames >= max_empty_frames:
                            logger.warning(f"Viewer {viewer_id} timed out after {max_empty_frames} empty frames")
                            break
                    
                    # Dynamic frame rate - don't enforce fixed FPS to allow exposure control
                    # Just a minimal sleep to prevent CPU spinning
                    time.sleep(0.01)  # 10ms minimal sleep
                    
                except GeneratorExit:
                    break
                except Exception as e:
                    logger.error(f"Error in streaming generator for viewer {viewer_id}: {e}")
                    break
        
        finally:
            # Remove viewer
            with self._viewer_lock:
                self._viewers.discard(viewer_id)
            logger.info(f"Viewer disconnected (ID: {viewer_id}), sent {frame_count} frames, remaining viewers: {len(self._viewers)}")
    
    def get_viewer_count(self) -> int:
        """Get current number of viewers"""
        with self._viewer_lock:
            return len(self._viewers)
    
    def is_active(self) -> bool:
        """Check if streaming is active"""
        return self._active
    
    def get_stats(self) -> dict:
        """Get streaming statistics"""
        with self._viewer_lock:
            frame_available = self._current_frame_data is not None
            return {
                'active': self._active,
                'viewer_count': len(self._viewers),
                'frame_available': frame_available,
                'jpeg_quality': self._jpeg_quality,
                'fps_limit': Config.STREAMING['fps_limit']
            }
    
    def cleanup(self):
        """Cleanup streaming resources"""
        logger.info("Cleaning up streaming output...")
        
        self._active = False
        
        # Clear current frame data
        with self._frame_lock:
            self._current_frame_data = None
        
        # Clear viewers
        with self._viewer_lock:
            viewer_count = len(self._viewers)
            self._viewers.clear()
            if viewer_count > 0:
                logger.info(f"Disconnected {viewer_count} viewers during cleanup")


class MultiStreamingOutput:
    """Manages multiple streaming outputs for different cameras"""
    
    def __init__(self):
        """Initialize multi-streaming output manager"""
        self._streams = {}
        self._lock = threading.Lock()
        
        logger.info("Multi-streaming output manager initialized")
    
    def create_stream(self, stream_id: str) -> StreamingOutput:
        """Create a new streaming output"""
        with self._lock:
            if stream_id in self._streams:
                logger.warning(f"Stream {stream_id} already exists")
                return self._streams[stream_id]
            
            stream = StreamingOutput()
            self._streams[stream_id] = stream
            logger.info(f"Created streaming output for {stream_id}")
            return stream
    
    def get_stream(self, stream_id: str) -> Optional[StreamingOutput]:
        """Get existing streaming output"""
        with self._lock:
            return self._streams.get(stream_id)
    
    def remove_stream(self, stream_id: str):
        """Remove streaming output"""
        with self._lock:
            if stream_id in self._streams:
                try:
                    self._streams[stream_id].cleanup()
                    del self._streams[stream_id]
                    logger.info(f"Removed streaming output for {stream_id}")
                except Exception as e:
                    logger.error(f"Error removing stream {stream_id}: {e}")
    
    def get_all_stats(self) -> dict:
        """Get statistics for all streams"""
        with self._lock:
            stats = {}
            for stream_id, stream in self._streams.items():
                stats[stream_id] = stream.get_stats()
            return stats
    
    def cleanup(self):
        """Cleanup all streaming outputs"""
        logger.info("Cleaning up all streaming outputs...")
        
        with self._lock:
            for stream_id, stream in self._streams.items():
                try:
                    stream.cleanup()
                    logger.info(f"Cleaned up stream {stream_id}")
                except Exception as e:
                    logger.error(f"Error cleaning up stream {stream_id}: {e}")
            
            self._streams.clear()
