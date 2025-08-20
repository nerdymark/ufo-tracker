// MPU9250 Sensor Data Display and Controls

let sensorUpdateInterval = null;
let sensorData = null;

// Initialize sensor data display when page loads
document.addEventListener('DOMContentLoaded', function() {
    initializeSensorDisplay();
    
    // Start sensor data updates
    updateSensorData();
    startSensorUpdates();
});

function initializeSensorDisplay() {
    console.log('Initializing MPU9250 sensor display...');
    
    // Check if sensor display elements exist
    const sensorElements = [
        'sensor-status',
        'sensor-acceleration',
        'sensor-gyroscope',
        'sensor-magnetometer',
        'sensor-orientation',
        'sensor-compass',
        'sensor-temperature'
    ];
    
    sensorElements.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            console.log(`Found sensor element: ${id}`);
        }
    });
}

function startSensorUpdates() {
    if (sensorUpdateInterval) {
        clearInterval(sensorUpdateInterval);
    }
    
    // Update sensor data every 2 seconds
    sensorUpdateInterval = setInterval(updateSensorData, 2000);
    console.log('Started sensor data updates');
}

function stopSensorUpdates() {
    if (sensorUpdateInterval) {
        clearInterval(sensorUpdateInterval);
        sensorUpdateInterval = null;
        console.log('Stopped sensor data updates');
    }
}

async function updateSensorData() {
    try {
        const response = await fetch('/api/sensor/data');
        const result = await response.json();
        
        if (result.success) {
            sensorData = result.data;
            updateSensorDisplay(sensorData);
        } else {
            console.error('Failed to fetch sensor data:', result.error);
            updateSensorDisplay(null);
        }
    } catch (error) {
        console.error('Error fetching sensor data:', error);
        updateSensorDisplay(null);
    }
}

function updateSensorDisplay(data) {
    if (!data) {
        // Update display to show error state
        updateElement('sensor-status', 'Sensor Error');
        updateElement('sensor-acceleration', 'X: -- Y: -- Z: --');
        updateElement('sensor-gyroscope', 'X: -- Y: -- Z: --');
        updateElement('sensor-magnetometer', 'X: -- Y: -- Z: --');
        updateElement('sensor-orientation', 'P: -- R: -- Y: --');
        updateElement('sensor-compass', 'H: -- T: --');
        updateElement('sensor-temperature', '--°C');
        return;
    }
    
    // Update status
    const status = data.calibrated ? 'Active & Calibrated' : 'Active (Not Calibrated)';
    updateElement('sensor-status', status);
    
    // Update acceleration data
    const accel = data.acceleration;
    updateElement('sensor-acceleration', 
        `X: ${accel.x.toFixed(2)} Y: ${accel.y.toFixed(2)} Z: ${accel.z.toFixed(2)} m/s²`);
    
    // Update gyroscope data
    const gyro = data.gyroscope;
    updateElement('sensor-gyroscope', 
        `X: ${gyro.x.toFixed(2)} Y: ${gyro.y.toFixed(2)} Z: ${gyro.z.toFixed(2)} °/s`);
    
    // Update magnetometer data
    const mag = data.magnetometer;
    updateElement('sensor-magnetometer', 
        `X: ${mag.x.toFixed(2)} Y: ${mag.y.toFixed(2)} Z: ${mag.z.toFixed(2)} µT`);
    
    // Update orientation data
    const orient = data.orientation;
    updateElement('sensor-orientation', 
        `P: ${orient.pitch.toFixed(1)} R: ${orient.roll.toFixed(1)} Y: ${orient.yaw.toFixed(1)} °`);
    
    // Update compass data
    const compass = data.compass;
    updateElement('sensor-compass', 
        `H: ${compass.heading.toFixed(1)}° T: ${compass.true_heading.toFixed(1)}°`);
    
    // Update temperature
    updateElement('sensor-temperature', `${data.temperature.toFixed(1)}°C`);
    
    // Update motion and tilt indicators
    updateElement('sensor-motion', data.motion_detected ? 'Motion Detected' : 'Stable');
    updateElement('sensor-tilt', `${data.tilt_angle.toFixed(1)}°`);
    updateElement('sensor-vibration', `${data.vibration_level.toFixed(2)} °/s`);
    
    // Update calibration status indicators
    updateElement('compass-calibrated', compass.calibrated ? 'Yes' : 'No');
    updateElement('sensor-calibrated', data.calibrated ? 'Yes' : 'No');
    
    // Update compass elements for trajectory system
    updateElement('compass-heading', `${compass.heading.toFixed(1)}°`);
    updateElement('compass-true-heading', `${compass.true_heading.toFixed(1)}°`);
    updateElement('compass-status', compass.calibrated ? 'Calibrated' : 'Not Calibrated');
    updateElement('compass-declination', `${compass.magnetic_declination.toFixed(1)}°`);
}

function updateElement(id, text) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = text;
    }
}

// Sensor calibration functions
async function calibrateAccelerometer() {
    try {
        if (confirm('This will calibrate the accelerometer and gyroscope. Keep the device stationary and level. Continue?')) {
            showNotification('Calibrating accelerometer and gyroscope...', 'info');
            
            const response = await fetch('/api/sensor/calibrate/accelerometer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ samples: 1000 })
            });
            
            const data = await response.json();
            
            if (data.success) {
                showNotification('Accelerometer calibration completed!', 'success');
                updateSensorData();
            } else {
                showNotification('Calibration failed: ' + (data.error || 'Unknown error'), 'error');
            }
        }
    } catch (error) {
        console.error('Error calibrating accelerometer:', error);
        showNotification('Error calibrating accelerometer', 'error');
    }
}

async function calibrateMagnetometer() {
    try {
        if (confirm('This will start magnetometer calibration. Rotate the device in 3D figure-8 patterns for 60 seconds. Continue?')) {
            showNotification('Starting magnetometer calibration...', 'info');
            
            const response = await fetch('/api/sensor/calibrate/magnetometer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ duration: 60 })
            });
            
            const data = await response.json();
            
            if (data.success) {
                showNotification('Magnetometer calibration completed!', 'success');
                updateSensorData();
            } else {
                showNotification('Calibration failed: ' + (data.error || 'Unknown error'), 'error');
            }
        }
    } catch (error) {
        console.error('Error calibrating magnetometer:', error);
        showNotification('Error calibrating magnetometer', 'error');
    }
}

async function setCompassNorth() {
    try {
        const response = await fetch('/api/sensor/compass/set_north', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification('North reference set to current heading!', 'success');
            updateSensorData();
        } else {
            showNotification('North calibration failed: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error setting north reference:', error);
        showNotification('Error setting north reference', 'error');
    }
}

async function setMagneticDeclination() {
    try {
        const declination = parseFloat(prompt('Enter magnetic declination for your location (degrees):') || '0');
        
        const response = await fetch('/api/sensor/compass/set_declination', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ declination: declination })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification(`Magnetic declination set to ${declination}°`, 'success');
            updateSensorData();
        } else {
            showNotification('Setting declination failed: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error setting magnetic declination:', error);
        showNotification('Error setting magnetic declination', 'error');
    }
}

async function getSensorStatus() {
    try {
        const response = await fetch('/api/sensor/status');
        const result = await response.json();
        
        if (result.success) {
            const status = result.status;
            console.log('Sensor Status:', status);
            
            // Show detailed status in a modal or alert
            const statusText = `
MPU9250 Sensor Status:
- Running: ${status.running ? 'Yes' : 'No'}
- Enabled: ${status.enabled ? 'Yes' : 'No'}
- Hardware Available: ${status.hardware_available ? 'Yes' : 'No'}
- Library: ${status.library || 'Not Available'}
- Calibrated: ${status.calibrated ? 'Yes' : 'No'}
- Compass Calibrated: ${status.compass_calibrated ? 'Yes' : 'No'}
- Sample Rate: ${status.sample_rate} Hz
- Temperature: ${status.current_temperature}°C
- I2C Addresses: ${status.i2c_addresses ? status.i2c_addresses.join(', ') : 'Unknown'}
- Last Update: ${status.last_update || 'Never'}
            `;
            
            alert(statusText);
        } else {
            showNotification('Failed to get sensor status: ' + (result.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error getting sensor status:', error);
        showNotification('Error getting sensor status', 'error');
    }
}

// Helper function to show notifications (reused from compass-trajectory.js)
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        background: ${type === 'success' ? '#28a745' : type === 'error' ? '#dc3545' : '#17a2b8'};
        color: white;
        border-radius: 5px;
        z-index: 10000;
        animation: slideIn 0.3s ease;
        max-width: 300px;
        word-wrap: break-word;
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 5000); // Show for 5 seconds
}

// Compass direction helper
function getCompassDirection(heading) {
    const directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
    const index = Math.round(heading / 22.5) % 16;
    return directions[index];
}

// Enhanced compass display with direction
function updateCompassWithDirection(heading) {
    const direction = getCompassDirection(heading);
    updateElement('compass-direction', direction);
    
    // Update compass needle rotation if element exists
    const compassNeedle = document.getElementById('compass-needle');
    if (compassNeedle) {
        compassNeedle.style.transform = `rotate(${heading}deg)`;
    }
}

// Auto-refresh toggle
function toggleSensorUpdates() {
    const button = document.getElementById('sensor-auto-refresh');
    
    if (sensorUpdateInterval) {
        stopSensorUpdates();
        if (button) {
            button.textContent = '▶ Start Auto-Refresh';
            button.classList.remove('btn-danger');
            button.classList.add('btn-success');
        }
    } else {
        startSensorUpdates();
        if (button) {
            button.textContent = '⏸ Stop Auto-Refresh';
            button.classList.remove('btn-success');
            button.classList.add('btn-danger');
        }
    }
}

// Export functions for use by other modules
window.MPU9250Sensor = {
    updateSensorData,
    calibrateAccelerometer,
    calibrateMagnetometer,
    setCompassNorth,
    setMagneticDeclination,
    getSensorStatus,
    toggleSensorUpdates,
    startSensorUpdates,
    stopSensorUpdates
};