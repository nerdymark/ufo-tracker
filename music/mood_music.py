"""
Mood Music Controller for UFO Tracker
Python interface for the Java MIDI ambient music generator
"""

import subprocess
import threading
import time
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

class MoodMusicController:
    """Controls the ambient mood music system"""
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.is_enabled = False
        self.is_playing = False
        self._lock = threading.Lock()
        self.java_class = "MoodMusicGenerator"
        self.music_dir = os.path.dirname(os.path.abspath(__file__))
        
    def enable(self):
        """Enable mood music system"""
        with self._lock:
            self.is_enabled = True
            logger.info("Mood music system enabled")
    
    def disable(self):
        """Disable mood music system and stop any playing music"""
        with self._lock:
            self.is_enabled = False
            if self.is_playing:
                self.stop()
            logger.info("Mood music system disabled")
    
    def toggle(self):
        """Toggle mood music system on/off"""
        if self.is_enabled:
            self.disable()
        else:
            self.enable()
        return self.is_enabled
    
    def play_random_track(self) -> bool:
        """Start playing a random ambient track"""
        if not self.is_enabled:
            logger.warning("Cannot play: mood music is disabled")
            return False
        
        with self._lock:
            # Stop any currently playing music
            if self.is_playing:
                self.stop()
            
            try:
                # Compile Java class if needed
                if not self._ensure_compiled():
                    return False
                
                # Start Java music generator in background
                java_cmd = [
                    'java',
                    '-cp', self.music_dir,
                    self.java_class
                ]
                
                self.process = subprocess.Popen(
                    java_cmd,
                    cwd=self.music_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                self.is_playing = True
                logger.info("Started playing random ambient track")
                
                # Start monitoring thread
                monitor_thread = threading.Thread(
                    target=self._monitor_process,
                    daemon=True
                )
                monitor_thread.start()
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to start mood music: {e}")
                self.is_playing = False
                return False
    
    def stop(self) -> bool:
        """Stop currently playing music"""
        with self._lock:
            if not self.is_playing or not self.process:
                return True
            
            try:
                self.process.terminate()
                
                # Give it a moment to terminate gracefully
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning("Music process didn't terminate gracefully, killing it")
                    self.process.kill()
                
                self.process = None
                self.is_playing = False
                logger.info("Stopped mood music")
                return True
                
            except Exception as e:
                logger.error(f"Failed to stop mood music: {e}")
                return False
    
    def _ensure_compiled(self) -> bool:
        """Ensure Java class is compiled"""
        java_file = os.path.join(self.music_dir, f"{self.java_class}.java")
        class_file = os.path.join(self.music_dir, f"{self.java_class}.class")
        
        # Check if class file exists and is newer than source
        if os.path.exists(class_file):
            if os.path.getmtime(class_file) > os.path.getmtime(java_file):
                return True
        
        try:
            # Compile Java source
            compile_cmd = ['javac', java_file]
            result = subprocess.run(
                compile_cmd,
                cwd=self.music_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info("Successfully compiled mood music generator")
                return True
            else:
                logger.error(f"Failed to compile Java music generator: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Java compilation timed out")
            return False
        except Exception as e:
            logger.error(f"Error compiling Java music generator: {e}")
            return False
    
    def _monitor_process(self):
        """Monitor the Java music process"""
        if not self.process:
            return
        
        try:
            # Wait for process to complete
            stdout, stderr = self.process.communicate()
            
            if stdout:
                logger.debug(f"Music generator output: {stdout}")
            if stderr:
                logger.warning(f"Music generator errors: {stderr}")
            
        except Exception as e:
            logger.error(f"Error monitoring music process: {e}")
        finally:
            with self._lock:
                self.is_playing = False
                self.process = None
            logger.debug("Music process monitoring ended")
    
    def get_status(self) -> dict:
        """Get current status of mood music system"""
        return {
            'enabled': self.is_enabled,
            'playing': self.is_playing,
            'java_available': self._check_java_available()
        }
    
    def _check_java_available(self) -> bool:
        """Check if Java is available on the system"""
        try:
            result = subprocess.run(
                ['java', '-version'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def cleanup(self):
        """Cleanup resources"""
        self.stop()
        logger.info("Mood music controller cleaned up")


# Global mood music controller instance
mood_music = MoodMusicController()