// Pan/Tilt mechanism controls

let panTiltAutoRefresh = null;

// Pan/Tilt movement functions
function movePanTilt(action, params = {}) {
    const data = {
        action: action,
        ...params
    };
    
    // Use step size from slider for relative movements
    if (action === 'move_relative') {
        const stepSize = parseInt(document.getElementById('step-size')?.value || 5);
        if (params.pan_steps) {
            data.pan_steps = params.pan_steps * stepSize;
        }
        if (params.tilt_steps) {
            data.tilt_steps = params.tilt_steps * stepSize;
        }
    }
    
    console.log('Sending pan/tilt command:', data);
    
    fetch('/api/pan_tilt', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        console.log('Pan/Tilt Response:', data);
        if (data.success) {
            showMessage(data.message || 'Movement completed', 'success');
            if (data.position) {
                updatePanTiltPosition(data.position.pan, data.position.tilt);
            }
            // Calibration status removed
            // Auto-refresh status after movement
            setTimeout(refreshPanTiltStatus, 500);
        } else {
            showMessage('Pan/Tilt Error: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        console.error('Pan/Tilt Error:', error);
        console.log('Full error details:', error);
        showMessage('Pan/Tilt Communication Error: ' + error, 'error');
    });
}

// Position update
function updatePanTiltPosition(pan, tilt) {
    const panElement = document.getElementById('pan-position');
    const tiltElement = document.getElementById('tilt-position');
    
    if (panElement) panElement.textContent = pan.toFixed(1) + '°';
    if (tiltElement) tiltElement.textContent = tilt.toFixed(1) + '°';
}

// Status refresh
function refreshPanTiltStatus() {
    fetch('/api/pan_tilt')
    .then(response => response.json())
    .then(data => {
        if (data.position) {
            updatePanTiltPosition(data.position.pan, data.position.tilt);
        }
        
        // Update motor status
        updateMotorStatus(data.motors_enabled);
        
        // Update keepalive status
        if (data.hasOwnProperty('keepalive_enabled')) {
            updateKeepaliveStatus(data.keepalive_enabled);
        }
        
        // Update connection status
        const statusIndicator = document.getElementById('pantilt-control-status');
        if (statusIndicator) {
            if (data.connected) {
                statusIndicator.className = 'status-indicator active';
                statusIndicator.textContent = 'Connected';
            } else {
                statusIndicator.className = 'status-indicator inactive';
                statusIndicator.textContent = 'Disconnected';
            }
        }
    })
    .catch(error => {
        console.error('Pan/Tilt Status Error:', error);
        const statusIndicator = document.getElementById('pantilt-control-status');
        if (statusIndicator) {
            statusIndicator.className = 'status-indicator error';
            statusIndicator.textContent = 'Error';
        }
    });
}

// Speed control
function updatePanTiltSpeed() {
    const slider = document.getElementById('pantilt-speed');
    const display = document.getElementById('pantilt-speed-value');
    const speed = parseInt(slider.value);
    
    if (display) {
        display.textContent = speed;
    }
    
    // Send speed update to server
    movePanTilt('set_speed', { speed: speed });
}

// Step size control
function updateStepSize() {
    const slider = document.getElementById('step-size');
    const display = document.getElementById('step-size-value');
    const stepSize = parseInt(slider.value);
    
    if (display) {
        display.textContent = stepSize;
    }
}

// Auto refresh toggle
function togglePanTiltAutoRefresh() {
    const button = document.querySelector('button[onclick="togglePanTiltAutoRefresh()"]');
    
    if (panTiltAutoRefresh) {
        clearInterval(panTiltAutoRefresh);
        panTiltAutoRefresh = null;
        if (button) button.textContent = '⏰ Auto: OFF';
    } else {
        panTiltAutoRefresh = setInterval(refreshPanTiltStatus, 2000);
        if (button) button.textContent = '⏰ Auto: ON';
    }
}

// Motor control functions
function toggleMotors() {
    const button = document.getElementById('motor-toggle-btn');
    const isCurrentlyEnabled = button && button.textContent.includes('Disable');
    
    console.log('toggleMotors called, currently enabled:', isCurrentlyEnabled);
    console.log('Button element:', button);
    
    fetch('/api/pan_tilt/motors', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            enabled: !isCurrentlyEnabled
        })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Motors toggle response:', data);
        if (data.success) {
            updateMotorStatus(data.motors_enabled);
            showMessage(data.message || `Motors ${data.motors_enabled ? 'enabled' : 'disabled'}`, 'success');
        } else {
            showMessage('Motor toggle failed: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        console.error('Motor toggle error:', error);
        showMessage('Error toggling motors: ' + error, 'error');
    });
}

function updateMotorStatus(enabled) {
    const button = document.getElementById('motor-toggle-btn');
    const statusSpan = document.getElementById('motor-state');
    
    console.log('updateMotorStatus called with enabled =', enabled);
    console.log('Button element:', button);
    console.log('Status span element:', statusSpan);
    
    if (button) {
        if (enabled) {
            button.innerHTML = '🔌 Disable Motors';
            button.classList.remove('btn-success');
            button.classList.add('btn-warning');
        } else {
            button.innerHTML = '🔌 Enable Motors';
            button.classList.remove('btn-warning');
            button.classList.add('btn-success');
        }
    }
    
    if (statusSpan) {
        statusSpan.textContent = enabled ? 'Enabled' : 'Disabled';
        statusSpan.style.color = enabled ? '#4CAF50' : '#ff6b6b';
    }
}

function toggleKeepalive() {
    const button = document.getElementById('keepalive-toggle-btn');
    const isCurrentlyEnabled = button && button.textContent.includes('Disable');
    
    fetch('/api/pan_tilt/keepalive', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            enabled: !isCurrentlyEnabled
        })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Keepalive toggle response:', data);
        if (data.success) {
            updateKeepaliveStatus(data.keepalive_enabled);
            showMessage(data.message || `Keepalive ${data.keepalive_enabled ? 'enabled' : 'disabled'}`, 'success');
        } else {
            showMessage('Keepalive toggle failed: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        console.error('Keepalive toggle error:', error);
        showMessage('Error toggling keepalive: ' + error, 'error');
    });
}

function updateKeepaliveStatus(enabled) {
    const button = document.getElementById('keepalive-toggle-btn');
    const statusSpan = document.getElementById('keepalive-state');
    
    if (button) {
        if (enabled) {
            button.innerHTML = '🔒 Disable Keep On';
            button.classList.remove('btn-danger');
            button.classList.add('btn-warning');
        } else {
            button.innerHTML = '🔒 Keep Motors On';
            button.classList.remove('btn-warning');
            button.classList.add('btn-danger');
        }
    }
    
    if (statusSpan) {
        statusSpan.textContent = enabled ? 'Active' : 'Inactive';
        statusSpan.style.color = enabled ? '#4CAF50' : '#ff6b6b';
    }
}

// Home position
function goHome() {
    movePanTilt('go_home');
}

// Directional movement functions
function panLeft() {
    movePanTilt('move_relative', { pan_steps: -1 });
}

function panRight() {
    movePanTilt('move_relative', { pan_steps: 1 });
}

function tiltUp() {
    movePanTilt('move_relative', { tilt_steps: 1 });
}

function tiltDown() {
    movePanTilt('move_relative', { tilt_steps: -1 });
}

// Initialize pan/tilt status on page load
document.addEventListener('DOMContentLoaded', function() {
    // Delay initial status check to allow other systems to initialize
    // setTimeout(refreshPanTiltStatus, 2000); // DISABLED - causing auto-enable
});

// Cleanup pan/tilt auto refresh
window.addEventListener('beforeunload', function() {
    if (panTiltAutoRefresh) {
        clearInterval(panTiltAutoRefresh);
    }
});