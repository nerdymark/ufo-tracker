"""
Pan-Tilt Controller for UFO Tracker
Placeholder for Waveshare stepper motor controller integration

This module provides a placeholder implementation for the pan-tilt mechanism
that will be controlled by a Waveshare stepper motor controller when the 
hardware becomes available.
"""

import logging
import threading
import time
from typing import Tuple, Optional, Dict, Any
from datetime import datetime

from config.config import Config

logger = logging.getLogger(__name__)

class PanTiltController:
    """
    Pan-Tilt mechanism controller (Placeholder implementation)
    
    This is a placeholder for the actual Waveshare stepper controller integration.
    When the hardware is ready, this class will be updated to control the actual
    pan-tilt mechanism.
    """
    
    def __init__(self):
        """Initialize pan-tilt controller (placeholder)"""
        self.enabled = Config.PAN_TILT['enabled']
        self.controller_type = Config.PAN_TILT['controller_type']
        
        # Position limits (in degrees)
        self.pan_range = Config.PAN_TILT['pan_range']
        self.tilt_range = Config.PAN_TILT['tilt_range']
        
        # Movement parameters
        self.step_size = Config.PAN_TILT['step_size']
        self.speed = Config.PAN_TILT['speed']
        self.acceleration = Config.PAN_TILT['acceleration']
        
        # Current position (simulated)
        self._current_pan = 0.0
        self._current_tilt = 0.0
        self._target_pan = 0.0
        self._target_tilt = 0.0
        
        # State management
        self._connected = False
        self._moving = False
        self._lock = threading.Lock()
        
        # Movement thread
        self._movement_thread: Optional[threading.Thread] = None
        self._stop_movement = False
        
        # Hardware controller
        self._hardware_controller: Optional[WaveshareHRB8825Controller] = None
        
        # Statistics
        self._total_movements = 0
        self._last_movement_time: Optional[datetime] = None
        
        if self.enabled:
            self._initialize_hardware()
        else:
            logger.info("Pan-tilt controller initialized in placeholder mode (hardware disabled)")
    
    def _initialize_hardware(self):
        """
        Initialize hardware connection with HRB8825 controller
        """
        try:
            # Initialize HRB8825 controller
            logger.info("Initializing HRB8825 stepper controller")
            self._hardware_controller = WaveshareHRB8825Controller()
            
            # Connect to hardware
            if self._hardware_controller.connect():
                self._hardware_controller.set_speed(self.speed)
                self._hardware_controller.set_acceleration(self.acceleration)
                
                # Home the mechanism
                self._hardware_controller.home()
                
                self._connected = True
                logger.info("HRB8825 pan-tilt controller connected successfully")
            else:
                logger.error("Failed to connect to HRB8825 controller")
                self._connected = False
            
        except Exception as e:
            logger.error(f"Failed to initialize pan-tilt hardware: {e}")
            self._connected = False
            self._hardware_controller = None
    
    def is_connected(self) -> bool:
        """Check if controller is connected"""
        return self._connected and self.enabled
    
    def is_moving(self) -> bool:
        """Check if mechanism is currently moving"""
        return self._moving
    
    def get_position(self) -> Tuple[float, float]:
        """Get current pan/tilt position in degrees"""
        if self._hardware_controller and self._connected:
            return self._hardware_controller.get_position()
        else:
            with self._lock:
                return (self._current_pan, self._current_tilt)
    
    def get_target_position(self) -> Tuple[float, float]:
        """Get target pan/tilt position in degrees"""
        with self._lock:
            return (self._target_pan, self._target_tilt)
    
    def move_to(self, pan: float, tilt: float, blocking: bool = False) -> bool:
        """
        Move to specified pan/tilt position
        
        Args:
            pan: Pan angle in degrees (-90 to +90)
            tilt: Tilt angle in degrees (-30 to +60)
            blocking: If True, wait for movement to complete
            
        Returns:
            True if movement started successfully
        """
        if not self.is_connected():
            logger.warning("Cannot move: pan-tilt controller not connected")
            return False
        
        # Validate position limits
        pan = max(self.pan_range[0], min(self.pan_range[1], pan))
        tilt = max(self.tilt_range[0], min(self.tilt_range[1], tilt))
        
        with self._lock:
            self._target_pan = pan
            self._target_tilt = tilt
        
        try:
            if self._hardware_controller:
                # Use hardware controller for actual movement
                self._moving = True
                self._hardware_controller.set_position(pan, tilt)
                self._moving = False
                
                # Update internal position tracking
                with self._lock:
                    self._current_pan, self._current_tilt = self._hardware_controller.get_position()
                    self._total_movements += 1
                    self._last_movement_time = datetime.now()
                
                logger.info(f"Moved to pan={pan:.1f}°, tilt={tilt:.1f}°")
                return True
            else:
                # Fallback to simulation mode
                if not self._moving:
                    self._stop_movement = False
                    self._movement_thread = threading.Thread(
                        target=self._movement_loop, 
                        args=(pan, tilt),
                        daemon=True
                    )
                    self._movement_thread.start()
                    
                    logger.info(f"Started movement to pan={pan:.1f}°, tilt={tilt:.1f}° (simulation)")
                    
                    if blocking:
                        self._movement_thread.join()
                    
                    return True
                else:
                    logger.warning("Movement already in progress")
                    return False
                
        except Exception as e:
            logger.error(f"Failed to start movement: {e}")
            self._moving = False
            return False
    
    def _movement_loop(self, target_pan: float, target_tilt: float):
        """
        Movement simulation loop (placeholder)
        
        In actual implementation, this would send commands to the
        Waveshare controller to move the stepper motors.
        """
        self._moving = True
        self._last_movement_time = datetime.now()
        
        try:
            logger.debug(f"Movement loop started: pan={target_pan:.1f}°, tilt={target_tilt:.1f}°")
            
            # Simulate gradual movement
            start_pan, start_tilt = self._current_pan, self._current_tilt
            
            # Calculate movement steps
            pan_diff = target_pan - start_pan
            tilt_diff = target_tilt - start_tilt
            max_diff = max(abs(pan_diff), abs(tilt_diff))
            
            if max_diff == 0:
                return  # No movement needed
            
            # Simulate movement time based on speed
            movement_time = max_diff / self.speed * 10  # Scale for simulation
            steps = max(10, int(movement_time * 10))  # 10 steps per second
            
            for i in range(steps + 1):
                if self._stop_movement:
                    break
                
                # Calculate intermediate position
                progress = i / steps
                current_pan = start_pan + pan_diff * progress
                current_tilt = start_tilt + tilt_diff * progress
                
                with self._lock:
                    self._current_pan = current_pan
                    self._current_tilt = current_tilt
                
                # In actual implementation, send position commands here
                # waveshare_controller.set_position(current_pan, current_tilt)
                
                time.sleep(movement_time / steps)
            
            # Ensure final position is set
            with self._lock:
                self._current_pan = target_pan
                self._current_tilt = target_tilt
                self._total_movements += 1
            
            logger.info(f"Movement completed: pan={target_pan:.1f}°, tilt={target_tilt:.1f}°")
            
        except Exception as e:
            logger.error(f"Error in movement loop: {e}")
        finally:
            self._moving = False
    
    def stop_movement(self):
        """Stop current movement"""
        if self._moving:
            self._stop_movement = True
            if self._movement_thread and self._movement_thread.is_alive():
                self._movement_thread.join(timeout=2.0)
            logger.info("Movement stopped")
    
    def home(self) -> bool:
        """
        Home the pan-tilt mechanism
        
        Returns:
            True if homing successful
        """
        if not self.is_connected():
            logger.warning("Cannot home: pan-tilt controller not connected")
            return False
        
        logger.info("Homing pan-tilt mechanism")
        return self.move_to(0.0, 0.0, blocking=True)
    
    def track_object(self, object_position: Tuple[int, int], frame_size: Tuple[int, int]) -> bool:
        """
        Track an object by pointing the camera at it
        
        Args:
            object_position: (x, y) position of object in frame
            frame_size: (width, height) of camera frame
            
        Returns:
            True if tracking movement started
        """
        if not self.is_connected():
            return False
        
        # Convert pixel coordinates to pan/tilt angles
        # This is a simplified calculation - actual implementation would
        # need proper camera calibration and field of view calculations
        
        frame_width, frame_height = frame_size
        obj_x, obj_y = object_position
        
        # Calculate relative position (-1 to +1)
        rel_x = (obj_x - frame_width / 2) / (frame_width / 2)
        rel_y = (obj_y - frame_height / 2) / (frame_height / 2)
        
        # Convert to pan/tilt angles (simplified)
        # Assume 60° field of view for both pan and tilt
        fov_pan = 60.0
        fov_tilt = 45.0
        
        target_pan = rel_x * (fov_pan / 2)
        target_tilt = -rel_y * (fov_tilt / 2)  # Negative because y increases downward
        
        # Add to current position for relative movement
        current_pan, current_tilt = self.get_position()
        new_pan = current_pan + target_pan * 0.1  # Damping factor
        new_tilt = current_tilt + target_tilt * 0.1
        
        return self.move_to(new_pan, new_tilt)
    
    def get_status(self) -> Dict[str, Any]:
        """Get controller status"""
        logger.info("Getting pan-tilt status...")
        pan, tilt = self.get_position()
        logger.info(f"Got position: pan={pan}, tilt={tilt}")
        target_pan, target_tilt = self.get_target_position()
        logger.info("Got target position")
        
        return {
            'enabled': self.enabled,
            'connected': self._connected,
            'controller_type': self.controller_type,
            'moving': self._moving,
            'motors_enabled': self.get_motors_enabled(),
            'keepalive_enabled': self.get_keepalive_status(),
            'position': {
                'pan': round(pan, 2),
                'tilt': round(tilt, 2)
            },
            'target_position': {
                'pan': round(target_pan, 2),
                'tilt': round(target_tilt, 2)
            },
            'limits': {
                'pan_range': self.pan_range,
                'tilt_range': self.tilt_range
            },
            'settings': {
                'step_size': self.step_size,
                'speed': self.speed,
                'acceleration': self.acceleration
            },
            'statistics': {
                'total_movements': self._total_movements,
                'last_movement': self._last_movement_time.isoformat() if self._last_movement_time else None
            }
        }
    
    def set_speed(self, speed: int):
        """Set movement speed (0-255)"""
        if 0 <= speed <= 255:
            self.speed = speed
            logger.info(f"Pan-tilt speed set to {speed}")
        else:
            logger.warning(f"Invalid speed value: {speed}")
    
    def set_acceleration(self, acceleration: int):
        """Set movement acceleration (0-255)"""
        if 0 <= acceleration <= 255:
            self.acceleration = acceleration
            logger.info(f"Pan-tilt acceleration set to {acceleration}")
        else:
            logger.warning(f"Invalid acceleration value: {acceleration}")
    
    def cleanup(self):
        """Cleanup controller resources"""
        logger.info("Cleaning up pan-tilt controller...")
        
        # Stop any ongoing movement
        self.stop_movement()
        
        # Stop keepalive if running
        if self._hardware_controller:
            self.stop_keepalive()
        
        # Disconnect hardware controller
        if self._hardware_controller and self._connected and self.enabled:
            try:
                self._hardware_controller.disconnect()
                logger.info("HRB8825 controller disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting HRB8825 controller: {e}")
        
        self._connected = False
        self._hardware_controller = None
    
    def move_relative(self, pan_steps: int = 0, tilt_steps: int = 0) -> bool:
        """Move relative to current position by specified steps"""
        if not self.is_connected():
            return False
        
        if self._hardware_controller:
            return self._hardware_controller.move_relative(pan_steps, tilt_steps)
        else:
            # Fallback to degree-based movement for simulation
            current_pan, current_tilt = self.get_position()
            step_size = 1.0  # 1 degree per step for simulation
            new_pan = current_pan + (pan_steps * step_size)
            new_tilt = current_tilt + (tilt_steps * step_size)
            return self.move_to(new_pan, new_tilt)
    
    def calibrate_limits(self, axis: str, limit_type: str) -> bool:
        """
        Calibrate movement limits using current position
        
        Args:
            axis: 'pan' or 'tilt'
            limit_type: 'min' or 'max'
            
        Returns:
            True if calibration successful
        """
        if not self.is_connected():
            logger.warning("Cannot calibrate: controller not connected")
            return False
        
        if self._hardware_controller:
            return self._hardware_controller.calibrate_limits(axis, limit_type, True)
        else:
            logger.warning("Calibration not supported in simulation mode")
            return False
    
    def get_calibration_status(self) -> dict:
        """Get calibration status"""
        if self._hardware_controller:
            return self._hardware_controller.get_calibration_status()
        else:
            return {
                'calibrated': False,
                'pan_limits': {'min_degrees': self.pan_range[0], 'max_degrees': self.pan_range[1]},
                'tilt_limits': {'min_degrees': self.tilt_range[0], 'max_degrees': self.tilt_range[1]}
            }
    
    def enable_motors(self) -> bool:
        """Enable stepper motors (turn on holding torque)"""
        if not self.is_connected():
            return False
        
        if self._hardware_controller:
            return self._hardware_controller.enable_motors()
        return False
    
    def disable_motors(self) -> bool:
        """Disable stepper motors (turn off holding torque to save power)"""
        if not self.is_connected():
            return False
        
        if self._hardware_controller:
            return self._hardware_controller.disable_motors()
        return False
    
    def get_motors_enabled(self) -> bool:
        """Check if motors are enabled"""
        if self._hardware_controller:
            return self._hardware_controller.get_motors_enabled()
        return False
    
    def get_keepalive_status(self) -> bool:
        """Check if keepalive is enabled"""
        if self._hardware_controller:
            return self._hardware_controller.get_keepalive_status()
        return False
    
    def start_keepalive(self) -> bool:
        """Start keepalive pulses to prevent motor timeout during long exposures"""
        if not self.is_connected():
            logger.warning("Cannot start keepalive: controller not connected")
            return False
        
        if self._hardware_controller:
            return self._hardware_controller.start_keepalive()
        
        logger.warning("Keepalive not supported in simulation mode")
        return False
    
    def stop_keepalive(self):
        """Stop keepalive pulses"""
        if self._hardware_controller:
            self._hardware_controller.stop_keepalive()
    
    def set_keepalive_interval(self, interval_seconds: float):
        """Set keepalive pulse interval"""
        if self._hardware_controller:
            self._hardware_controller.set_keepalive_interval(interval_seconds)
        else:
            logger.warning("Cannot set keepalive interval: hardware controller not available")


# Hardware abstraction for Waveshare HRB8825 Stepper Motor HAT
class WaveshareHRB8825Controller:
    """
    Waveshare HRB8825 Stepper Motor HAT Controller
    
    Controls two stepper motors (pan and tilt) via GPIO pins on Raspberry Pi.
    Based on HR8825 dual H-bridge motor driver chip with microstepping support.
    
    Motor Wiring (Bipolar Stepper):
    --------------------------------
    Motor Wire Colors:
    - A+ Black
    - A- Green  
    - B+ Red
    - B- Blue
    
    HAT Connections:
    Motor 1 (Pan):   A+ → A1, A- → A2, B+ → B1, B- → B2
    Motor 2 (Tilt):  A+ → A3, A- → A4, B+ → B3, B- → B4
    
    Step Sequence (Full Step Mode):
    Step   A+  B+  A-  B-
    1      +   +   -   -
    2      -   +   +   -
    3      -   -   +   +
    4      +   -   -   +
    """
    
    def __init__(self):
        """Initialize HRB8825 controller"""
        try:
            import RPi.GPIO as GPIO
            self.GPIO = GPIO
            self._gpio_available = True
        except ImportError:
            logger.warning("RPi.GPIO not available - running in simulation mode")
            self._gpio_available = False
            self.GPIO = None
        
        # GPIO Pin assignments for HRB8825 HAT
        self.MOTOR1_PINS = {  # Pan motor (swapped to be Motor 2 pins)
            'dir': 24,    # Direction pin
            'step': 18,   # Step pulse pin
            'enable': 4,  # Enable pin (active low)
            'mode1': 21,  # Microstepping mode pins
            'mode2': 22,
            'mode3': 27
        }
        
        self.MOTOR2_PINS = {  # Tilt motor (swapped to be Motor 1 pins)
            'dir': 13,    # Direction pin
            'step': 19,   # Step pulse pin
            'enable': 12, # Enable pin (active low)
            'mode1': 16,  # Microstepping mode pins
            'mode2': 17,
            'mode3': 20
        }
        
        # Microstepping configurations (mode1, mode2, mode3)
        self.MICROSTEP_MODES = {
            'full': (0, 0, 0),      # Full step
            'half': (1, 0, 0),      # Half step
            'quarter': (0, 1, 0),   # 1/4 step
            'eighth': (1, 1, 0),    # 1/8 step
            'sixteenth': (0, 0, 1), # 1/16 step
            'thirtysecond': (1, 1, 1) # 1/32 step
        }
        
        # Current configuration
        self.microstep_mode = 'sixteenth'  # Default to 1/16 step for smooth movement
        self.step_delay = 0.002  # Delay between steps (0.002s for noise reduction)
        
        # Motor parameters
        self.steps_per_revolution = 200  # Standard NEMA stepper
        self.microsteps_per_step = 16    # Based on mode
        self.gear_ratio = 1.0           # Adjust based on your gearing
        
        # Position tracking
        self._pan_position = 0      # Position in steps
        self._tilt_position = 0
        self._pan_angle = 0.0       # Position in degrees
        self._tilt_angle = 0.0
        
        # Calibration limits (in steps from center)
        self._pan_limit_min = -1000   # Will be set during calibration
        self._pan_limit_max = 1000
        self._tilt_limit_min = -500
        self._tilt_limit_max = 800
        
        self._connected = False
        self._calibrated = False
        self._motors_enabled = False
        
        # Auto-disable for noise reduction
        self._last_movement_time = None
        self._auto_disable_timer = None
        self._auto_disable_delay = 30.0  # Auto-disable after 30 seconds idle
        
        # Keepalive system to prevent timeout during long exposures
        self._keepalive_enabled = False
        self._keepalive_thread = None
        self._keepalive_stop = False
        self._keepalive_interval = 5.0  # Send keepalive pulse every 5 seconds
        
        logger.info("HRB8825 stepper controller initialized")
    
    def connect(self) -> bool:
        """Initialize GPIO pins and connect to the controller"""
        if not self._gpio_available:
            logger.warning("GPIO not available - simulating connection")
            self._connected = True
            return True
        
        try:
            # Set GPIO mode
            self.GPIO.setmode(self.GPIO.BCM)
            self.GPIO.setwarnings(False)
            
            # Setup Motor 1 (Pan) pins
            for pin_name, pin_num in self.MOTOR1_PINS.items():
                self.GPIO.setup(pin_num, self.GPIO.OUT)
                if pin_name == 'enable':
                    self.GPIO.output(pin_num, False)  # Disable motor initially (inverted logic)
                else:
                    self.GPIO.output(pin_num, False)
            
            # Setup Motor 2 (Tilt) pins
            for pin_name, pin_num in self.MOTOR2_PINS.items():
                self.GPIO.setup(pin_num, self.GPIO.OUT)
                if pin_name == 'enable':
                    self.GPIO.output(pin_num, False)  # Disable motor initially (inverted logic)
                else:
                    self.GPIO.output(pin_num, False)
            
            # Configure microstepping mode
            self._set_microstepping_mode(self.microstep_mode)
            
            # Motors start disabled (free to move, saving power)
            self.GPIO.output(self.MOTOR1_PINS['enable'], False)  # Inverted logic: False/0V = disabled/free
            self.GPIO.output(self.MOTOR2_PINS['enable'], False)  # Inverted logic: False/0V = disabled/free
            self._motors_enabled = False
            
            self._connected = True
            logger.info("HRB8825 controller connected successfully (motors disabled - free to move)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to HRB8825 controller: {e}")
            self._connected = False
            return False
    
    def disconnect(self):
        """Disconnect and cleanup GPIO"""
        # Stop keepalive if running
        if self._keepalive_enabled:
            self.stop_keepalive()
        
        if self._gpio_available and self.GPIO:
            try:
                # Disable motors (Inverted logic: False = disabled/free)
                self.GPIO.output(self.MOTOR1_PINS['enable'], False)
                self.GPIO.output(self.MOTOR2_PINS['enable'], False)
                
                # Cleanup GPIO
                self.GPIO.cleanup()
                logger.info("HRB8825 controller disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting HRB8825 controller: {e}")
        
        self._connected = False
    
    def _set_microstepping_mode(self, mode: str):
        """Set microstepping mode for both motors"""
        if mode not in self.MICROSTEP_MODES:
            logger.warning(f"Unknown microstepping mode: {mode}")
            return
        
        mode_bits = self.MICROSTEP_MODES[mode]
        
        if self._gpio_available and self.GPIO:
            # Set mode for Motor 1 (Pan)
            self.GPIO.output(self.MOTOR1_PINS['mode1'], mode_bits[0])
            self.GPIO.output(self.MOTOR1_PINS['mode2'], mode_bits[1])
            self.GPIO.output(self.MOTOR1_PINS['mode3'], mode_bits[2])
            
            # Set mode for Motor 2 (Tilt)
            self.GPIO.output(self.MOTOR2_PINS['mode1'], mode_bits[0])
            self.GPIO.output(self.MOTOR2_PINS['mode2'], mode_bits[1])
            self.GPIO.output(self.MOTOR2_PINS['mode3'], mode_bits[2])
        
        # Update microsteps per step
        microstep_values = {'full': 1, 'half': 2, 'quarter': 4, 'eighth': 8, 
                           'sixteenth': 16, 'thirtysecond': 32}
        self.microsteps_per_step = microstep_values[mode]
        self.microstep_mode = mode
        
        logger.info(f"Microstepping mode set to {mode} ({self.microsteps_per_step} microsteps per step)")
    
    def _steps_to_degrees(self, steps: int) -> float:
        """Convert steps to degrees"""
        full_steps = steps / self.microsteps_per_step
        return (full_steps / self.steps_per_revolution) * 360.0 / self.gear_ratio
    
    def _degrees_to_steps(self, degrees: float) -> int:
        """Convert degrees to steps"""
        full_steps = (degrees * self.steps_per_revolution * self.gear_ratio) / 360.0
        return int(full_steps * self.microsteps_per_step)
    
    def _move_motor(self, motor_pins: dict, steps: int, direction: bool):
        """Move a motor by specified steps in given direction"""
        if not self._connected or not self._gpio_available or not self.GPIO:
            return
        
        # Set direction (inverted logic - False for positive/CW, True for negative/CCW)
        self.GPIO.output(motor_pins['dir'], not direction)
        time.sleep(0.0001)  # Small delay for direction setup
        
        # Generate step pulses with acceleration profile for noise reduction
        steps_abs = abs(steps)
        if steps_abs == 0:
            return
        
        # Acceleration profile parameters
        accel_steps = min(steps_abs // 4, 20)  # Accelerate for first 25% or max 20 steps
        decel_steps = min(steps_abs // 4, 20)  # Decelerate for last 25% or max 20 steps
        
        for step in range(steps_abs):
            # Calculate delay based on acceleration profile
            if step < accel_steps:
                # Acceleration phase - start slow, get faster
                progress = step / accel_steps
                delay = self.step_delay * (2.0 - progress)  # 2x to 1x delay
            elif step >= steps_abs - decel_steps:
                # Deceleration phase - slow down
                progress = (steps_abs - step) / decel_steps
                delay = self.step_delay * (2.0 - progress)  # 1x to 2x delay  
            else:
                # Constant speed phase
                delay = self.step_delay
            
            # Generate step pulse
            self.GPIO.output(motor_pins['step'], True)
            time.sleep(delay / 2)
            self.GPIO.output(motor_pins['step'], False)
            time.sleep(delay / 2)
    
    def set_position(self, pan: float, tilt: float):
        """Set pan/tilt position in degrees"""
        if not self._connected:
            return
        
        # Motors must be manually enabled for movement
        if not self._motors_enabled:
            logger.warning("Cannot move: motors are disabled. Enable motors first.")
            return
        
        # Convert degrees to steps
        target_pan_steps = self._degrees_to_steps(pan)
        target_tilt_steps = self._degrees_to_steps(tilt)
        
        # Check limits if calibrated
        if self._calibrated:
            target_pan_steps = max(self._pan_limit_min, 
                                 min(self._pan_limit_max, target_pan_steps))
            target_tilt_steps = max(self._tilt_limit_min, 
                                  min(self._tilt_limit_max, target_tilt_steps))
        
        # Calculate steps to move
        pan_steps_to_move = target_pan_steps - self._pan_position
        tilt_steps_to_move = target_tilt_steps - self._tilt_position
        
        # Move pan motor
        if pan_steps_to_move != 0:
            pan_direction = pan_steps_to_move > 0
            self._move_motor(self.MOTOR1_PINS, abs(pan_steps_to_move), pan_direction)
            self._pan_position = target_pan_steps
            self._pan_angle = self._steps_to_degrees(self._pan_position)
        
        # Move tilt motor
        if tilt_steps_to_move != 0:
            tilt_direction = not (tilt_steps_to_move > 0)  # Inverted to swap up/down
            self._move_motor(self.MOTOR2_PINS, abs(tilt_steps_to_move), tilt_direction)
            self._tilt_position = target_tilt_steps
            self._tilt_angle = self._steps_to_degrees(self._tilt_position)
        
        logger.info(f"Moved to pan={self._pan_angle:.2f}°, tilt={self._tilt_angle:.2f}°")
        
        # Start auto-disable timer for noise reduction
        self._start_auto_disable_timer()
    
    def get_position(self) -> Tuple[float, float]:
        """Get current position in degrees"""
        return (self._pan_angle, self._tilt_angle)
    
    def set_speed(self, speed: int):
        """Set movement speed (0-255)"""
        # Convert speed to step delay (inverse relationship)
        max_delay = 0.010  # 10ms delay for slowest speed
        min_delay = 0.0005  # 0.5ms delay for fastest speed
        
        normalized_speed = max(0, min(255, speed)) / 255.0
        self.step_delay = max_delay - (normalized_speed * (max_delay - min_delay))
        
        logger.info(f"Speed set to {speed} (step delay: {self.step_delay:.4f}s)")
    
    def set_acceleration(self, acceleration: int):
        """Set movement acceleration (placeholder - not implemented in this simple driver)"""
        logger.info(f"Acceleration set to {acceleration} (not implemented in basic driver)")
    
    def home(self):
        """Home the mechanism to center position"""
        if not self._connected:
            return False
        
        # Reset position counters to center
        self._pan_position = 0
        self._tilt_position = 0
        self._pan_angle = 0.0
        self._tilt_angle = 0.0
        
        logger.info("Homed to center position")
        return True
    
    def calibrate_limits(self, axis: str, limit_type: str, current_position: bool = True):
        """
        Calibrate movement limits
        
        Args:
            axis: 'pan' or 'tilt'
            limit_type: 'min' or 'max'
            current_position: If True, use current position as limit
        """
        if not self._connected:
            return False
        
        if current_position:
            if axis == 'pan':
                if limit_type == 'min':
                    self._pan_limit_min = self._pan_position
                    logger.info(f"Pan minimum limit set to {self._pan_angle:.2f}° ({self._pan_position} steps)")
                elif limit_type == 'max':
                    self._pan_limit_max = self._pan_position
                    logger.info(f"Pan maximum limit set to {self._pan_angle:.2f}° ({self._pan_position} steps)")
            elif axis == 'tilt':
                if limit_type == 'min':
                    self._tilt_limit_min = self._tilt_position
                    logger.info(f"Tilt minimum limit set to {self._tilt_angle:.2f}° ({self._tilt_position} steps)")
                elif limit_type == 'max':
                    self._tilt_limit_max = self._tilt_position
                    logger.info(f"Tilt maximum limit set to {self._tilt_angle:.2f}° ({self._tilt_position} steps)")
        
        # Check if all limits are set
        if (self._pan_limit_min != -1000 and self._pan_limit_max != 1000 and 
            self._tilt_limit_min != -500 and self._tilt_limit_max != 800):
            self._calibrated = True
            logger.info("All limits calibrated - system ready")
        
        return True
    
    def get_calibration_status(self) -> dict:
        """Get current calibration status"""
        return {
            'calibrated': self._calibrated,
            'pan_limits': {
                'min_steps': self._pan_limit_min,
                'max_steps': self._pan_limit_max,
                'min_degrees': self._steps_to_degrees(self._pan_limit_min),
                'max_degrees': self._steps_to_degrees(self._pan_limit_max)
            },
            'tilt_limits': {
                'min_steps': self._tilt_limit_min,
                'max_steps': self._tilt_limit_max,
                'min_degrees': self._steps_to_degrees(self._tilt_limit_min),
                'max_degrees': self._steps_to_degrees(self._tilt_limit_max)
            }
        }
    
    def move_relative(self, pan_steps: int = 0, tilt_steps: int = 0):
        """Move relative to current position by specified steps"""
        if not self._connected:
            return False
        
        # Motors must be manually enabled for movement
        if not self._motors_enabled:
            logger.warning("Cannot move: motors are disabled. Enable motors first.")
            return
        
        # Calculate new positions
        new_pan_pos = self._pan_position + pan_steps
        new_tilt_pos = self._tilt_position + tilt_steps
        
        # Check limits if calibrated
        if self._calibrated:
            new_pan_pos = max(self._pan_limit_min, min(self._pan_limit_max, new_pan_pos))
            new_tilt_pos = max(self._tilt_limit_min, min(self._tilt_limit_max, new_tilt_pos))
        
        # Convert to degrees and move
        new_pan_angle = self._steps_to_degrees(new_pan_pos)
        new_tilt_angle = self._steps_to_degrees(new_tilt_pos)
        
        self.set_position(new_pan_angle, new_tilt_angle)
        return True
    
    def enable_motors(self) -> bool:
        """Enable stepper motors (turn on holding torque)"""
        if not self._connected:
            return False
        
        if self._gpio_available and self.GPIO:
            try:
                # Enable both motors (inverted logic - True/3.3V = enabled/holding)
                self.GPIO.output(self.MOTOR1_PINS['enable'], True)
                self.GPIO.output(self.MOTOR2_PINS['enable'], True)
                self._motors_enabled = True
                logger.info("Motors enabled (holding torque on)")
                return True
            except Exception as e:
                logger.error(f"Failed to enable motors: {e}")
                return False
        else:
            # Simulation mode
            self._motors_enabled = True
            logger.info("Motors enabled (simulation)")
            return True
    
    def disable_motors(self) -> bool:
        """Disable stepper motors (turn off holding torque to save power)"""
        if not self._connected:
            return False
        
        if self._gpio_available and self.GPIO:
            try:
                # Disable both motors (inverted logic - False/0V = disabled/free)
                self.GPIO.output(self.MOTOR1_PINS['enable'], False)
                self.GPIO.output(self.MOTOR2_PINS['enable'], False)
                self._motors_enabled = False
                logger.info("Motors disabled (holding torque off - free to move)")
                return True
            except Exception as e:
                logger.error(f"Failed to disable motors: {e}")
                return False
        else:
            # Simulation mode
            self._motors_enabled = False
            logger.info("Motors disabled (simulation)")
            return True
    
    def get_motors_enabled(self) -> bool:
        """Check if motors are currently enabled"""
        return self._motors_enabled
    
    def get_keepalive_status(self) -> bool:
        """Check if keepalive is currently active"""
        return self._keepalive_enabled
    
    def start_keepalive(self):
        """Start keepalive pulses to prevent motor timeout during long exposures"""
        if not self._connected or not self._gpio_available or not self.GPIO:
            logger.warning("Cannot start keepalive: not connected")
            return False
        
        if self._keepalive_enabled:
            logger.debug("Keepalive already running")
            return True
        
        # Ensure motors are enabled first
        if not self._motors_enabled:
            self.enable_motors()
        
        # Start keepalive thread
        import threading
        self._keepalive_enabled = True
        self._keepalive_stop = False
        self._keepalive_thread = threading.Thread(
            target=self._keepalive_loop,
            daemon=True
        )
        self._keepalive_thread.start()
        logger.info("Motor keepalive started (prevents timeout during long exposures)")
        return True
    
    def stop_keepalive(self):
        """Stop keepalive pulses"""
        if not self._keepalive_enabled:
            return
        
        self._keepalive_stop = True
        if self._keepalive_thread and self._keepalive_thread.is_alive():
            self._keepalive_thread.join(timeout=2.0)
        
        self._keepalive_enabled = False
        self._keepalive_thread = None
        logger.info("Motor keepalive stopped")
    
    def _keepalive_loop(self):
        """Keepalive loop that sends periodic pulses to maintain motor power"""
        logger.debug("Keepalive loop started")
        
        while not self._keepalive_stop:
            try:
                # Send a tiny pulse to each motor to reset the timeout
                # This doesn't actually move the motors, just keeps them energized
                
                # Pulse Motor 1 (Pan) - single microstep forward and back
                self.GPIO.output(self.MOTOR1_PINS['dir'], False)  # Forward
                time.sleep(0.0001)
                self.GPIO.output(self.MOTOR1_PINS['step'], True)
                time.sleep(0.0001)
                self.GPIO.output(self.MOTOR1_PINS['step'], False)
                time.sleep(0.0001)
                
                # Immediately reverse the microstep to maintain position
                self.GPIO.output(self.MOTOR1_PINS['dir'], True)  # Reverse
                time.sleep(0.0001)
                self.GPIO.output(self.MOTOR1_PINS['step'], True)
                time.sleep(0.0001)
                self.GPIO.output(self.MOTOR1_PINS['step'], False)
                time.sleep(0.0001)
                
                # Pulse Motor 2 (Tilt) - single microstep forward and back
                self.GPIO.output(self.MOTOR2_PINS['dir'], False)  # Forward
                time.sleep(0.0001)
                self.GPIO.output(self.MOTOR2_PINS['step'], True)
                time.sleep(0.0001)
                self.GPIO.output(self.MOTOR2_PINS['step'], False)
                time.sleep(0.0001)
                
                # Immediately reverse the microstep to maintain position
                self.GPIO.output(self.MOTOR2_PINS['dir'], True)  # Reverse
                time.sleep(0.0001)
                self.GPIO.output(self.MOTOR2_PINS['step'], True)
                time.sleep(0.0001)
                self.GPIO.output(self.MOTOR2_PINS['step'], False)
                
                logger.debug("Keepalive pulse sent")
                
            except Exception as e:
                logger.error(f"Error in keepalive loop: {e}")
            
            # Wait before next pulse
            for _ in range(int(self._keepalive_interval * 10)):
                if self._keepalive_stop:
                    break
                time.sleep(0.1)
        
        logger.debug("Keepalive loop ended")
    
    def _start_auto_disable_timer(self):
        """Start timer to auto-disable motors for noise reduction"""
        import threading
        
        # Don't auto-disable if keepalive is running
        if self._keepalive_enabled:
            logger.debug("Auto-disable skipped - keepalive is active")
            return
        
        # Cancel existing timer
        if self._auto_disable_timer:
            self._auto_disable_timer.cancel()
        
        # Start new timer
        self._auto_disable_timer = threading.Timer(
            self._auto_disable_delay, 
            self._auto_disable_motors
        )
        self._auto_disable_timer.start()
        logger.debug(f"Auto-disable timer started ({self._auto_disable_delay}s)")
    
    def _auto_disable_motors(self):
        """Automatically disable motors after idle period for noise reduction"""
        # Don't auto-disable if keepalive is running
        if self._keepalive_enabled:
            logger.debug("Auto-disable cancelled - keepalive is active")
            self._auto_disable_timer = None
            return
        
        if self._motors_enabled:
            self.disable_motors()
            logger.info(f"Motors auto-disabled after {self._auto_disable_delay}s idle (noise reduction)")
        self._auto_disable_timer = None
    
    def set_auto_disable_delay(self, delay_seconds: float):
        """Set auto-disable delay (0 to disable auto-disable)"""
        self._auto_disable_delay = delay_seconds
        logger.info(f"Auto-disable delay set to {delay_seconds}s")
    
    def set_keepalive_interval(self, interval_seconds: float):
        """Set keepalive pulse interval (how often to send keepalive pulses)"""
        self._keepalive_interval = max(1.0, min(30.0, interval_seconds))
        logger.info(f"Keepalive interval set to {self._keepalive_interval}s")
