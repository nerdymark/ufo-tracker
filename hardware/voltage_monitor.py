#!/usr/bin/env python3
"""
VREF Voltage Monitor for HRB8825 Stepper Driver
Monitors potentiometer voltage for proper motor current setting
"""

import logging
import time
import sys

logger = logging.getLogger(__name__)

class VREFMonitor:
    """
    Monitor VREF voltage on HRB8825 stepper driver
    VREF should be set to 70% of motor rating for optimal noise reduction
    
    For typical NEMA stepper motors:
    - 1.7A motor: VREF = 1.19V (1.7 * 0.7)
    - 2.0A motor: VREF = 1.40V (2.0 * 0.7)
    - 2.5A motor: VREF = 1.75V (2.5 * 0.7)
    """
    
    def __init__(self, spi_channel=0, adc_channel=0):
        """Initialize VREF monitor"""
        self.spi_channel = spi_channel
        self.adc_channel = adc_channel
        self.spi = None
        self._initialize_spi()
        
        # Motor specifications (adjust for your motors)
        self.motor_current_rating = 2.0  # Amps - adjust for your motors
        self.optimal_vref = self.motor_current_rating * 0.7
        
    def _initialize_spi(self):
        """Initialize SPI connection for ADC"""
        try:
            import spidev
            self.spi = spidev.SpiDev()
            self.spi.open(0, self.spi_channel)  # Bus 0, Device 0
            self.spi.max_speed_hz = 1000000  # 1MHz
            self.spi.mode = 0
            logger.info("SPI ADC initialized successfully")
        except ImportError:
            logger.warning("spidev not available - install with: pip install spidev")
            self.spi = None
        except Exception as e:
            logger.error(f"Failed to initialize SPI ADC: {e}")
            self.spi = None
    
    def read_vref_voltage(self):
        """
        Read VREF voltage from ADC
        Assumes MCP3008 or similar 10-bit ADC with 3.3V reference
        """
        if not self.spi:
            return None
        
        try:
            # MCP3008 command: start bit, single-ended, channel select
            command = [1, (8 + self.adc_channel) << 4, 0]
            response = self.spi.xfer2(command)
            
            # Parse 10-bit ADC result
            adc_value = ((response[1] & 3) << 8) + response[2]
            
            # Convert to voltage (assuming 3.3V reference)
            voltage = (adc_value / 1023.0) * 3.3
            
            return voltage
            
        except Exception as e:
            logger.error(f"Error reading VREF voltage: {e}")
            return None
    
    def get_vref_status(self):
        """Get VREF voltage and status"""
        voltage = self.read_vref_voltage()
        
        if voltage is None:
            return {
                'voltage': None,
                'status': 'error',
                'message': 'Unable to read voltage'
            }
        
        # Calculate percentage of optimal
        percentage = (voltage / self.optimal_vref) * 100 if self.optimal_vref > 0 else 0
        
        # Determine status
        if 65 <= percentage <= 75:  # Within 5% of 70%
            status = 'optimal'
            message = f'VREF optimal at {voltage:.3f}V ({percentage:.1f}% of motor rating)'
        elif 60 <= percentage <= 80:
            status = 'good'
            message = f'VREF acceptable at {voltage:.3f}V ({percentage:.1f}% of motor rating)'
        elif percentage < 60:
            status = 'low'
            message = f'VREF too low at {voltage:.3f}V ({percentage:.1f}% of motor rating) - increase potentiometer'
        else:
            status = 'high'
            message = f'VREF too high at {voltage:.3f}V ({percentage:.1f}% of motor rating) - decrease potentiometer'
        
        return {
            'voltage': voltage,
            'optimal_voltage': self.optimal_vref,
            'percentage': percentage,
            'status': status,
            'message': message,
            'motor_rating': self.motor_current_rating
        }
    
    def monitor_continuous(self, interval=1.0):
        """Monitor VREF voltage continuously"""
        print(f"Monitoring VREF voltage (optimal: {self.optimal_vref:.3f}V for {self.motor_current_rating}A motor)")
        print("Press Ctrl+C to stop\n")
        
        try:
            while True:
                status = self.get_vref_status()
                if status['voltage'] is not None:
                    print(f"VREF: {status['voltage']:.3f}V | {status['status'].upper()} | {status['message']}")
                else:
                    print("Error reading VREF voltage")
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\nMonitoring stopped")
    
    def cleanup(self):
        """Cleanup SPI connection"""
        if self.spi:
            self.spi.close()

# Utility functions for manual voltage checking
def check_vref_now(motor_current=2.0):
    """Quick VREF check"""
    monitor = VREFMonitor()
    monitor.motor_current_rating = motor_current
    monitor.optimal_vref = motor_current * 0.7
    
    status = monitor.get_vref_status()
    monitor.cleanup()
    
    return status

if __name__ == '__main__':
    if len(sys.argv) > 1:
        try:
            motor_current = float(sys.argv[1])
            print(f"Checking VREF for {motor_current}A motor...")
            status = check_vref_now(motor_current)
            print(f"\nResult: {status['message']}")
        except ValueError:
            print("Usage: python voltage_monitor.py [motor_current_rating]")
    else:
        # Continuous monitoring
        monitor = VREFMonitor()
        try:
            monitor.monitor_continuous()
        finally:
            monitor.cleanup()