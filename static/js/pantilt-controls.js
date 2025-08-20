// Pan/Tilt mechanism controls

let panTiltAutoRefresh = null;
let wasdKeysEnabled = false;
let keyboardEventBound = false;

// Key bindings for WASD control
const keyBindings = {
    'KeyW': { action: 'tiltUp', name: 'W (Tilt Up)' },
    'KeyA': { action: 'panLeft', name: 'A (Pan Left)' }, 
    'KeyS': { action: 'tiltDown', name: 'S (Tilt Down)' },
    'KeyD': { action: 'panRight', name: 'D (Pan Right)' }
};

// Track pressed keys to prevent key repeat
let pressedKeys = new Set();

// WASD Key event handlers
function handleKeyDown(event) {
    if (!wasdKeysEnabled) return;
    
    // Prevent key repeat
    if (pressedKeys.has(event.code)) return;
    pressedKeys.add(event.code);
    
    // Check if it's a WASD key
    if (keyBindings[event.code]) {
        event.preventDefault();
        const fineStep = event.shiftKey; // Shift for fine control
        const binding = keyBindings[event.code];
        
        console.log(`Key pressed: ${binding.name}${fineStep ? ' (Fine Mode)' : ''}`);
        
        // Execute the movement
        // Base step size - all movements use the same base step
        const baseStep = 10; // 10 steps per key press for consistent movement
        
        switch(binding.action) {
            case 'panLeft':
                movePanTiltRelative(-baseStep, 0, fineStep);
                break;
            case 'panRight':
                movePanTiltRelative(baseStep, 0, fineStep);
                break;
            case 'tiltUp':
                // Invert tilt direction: W should tilt up (negative)
                movePanTiltRelative(0, -baseStep, fineStep);
                break;
            case 'tiltDown':
                // Invert tilt direction: S should tilt down (positive)
                movePanTiltRelative(0, baseStep, fineStep);
                break;
        }
    }
}

function handleKeyUp(event) {
    pressedKeys.delete(event.code);
}

// Toggle WASD controls
function toggleWASDControl() {
    wasdKeysEnabled = !wasdKeysEnabled;
    
    // Update all WASD buttons
    const buttons = [
        document.getElementById('wasd-toggle-btn'),
        document.getElementById('wasd-toggle-btn-live')
    ];
    
    if (wasdKeysEnabled) {
        // Enable motors when starting WASD control
        enablePanTiltMotors();
        
        buttons.forEach(button => {
            if (button) {
                button.innerHTML = '⌨️ WASD: ON';
                button.classList.remove('btn-secondary');
                button.classList.add('btn-primary');
            }
        });
        showMessage('WASD controls enabled. Use W/A/S/D to control pan/tilt. Hold Shift for fine movement.', 'success');
    } else {
        buttons.forEach(button => {
            if (button) {
                button.innerHTML = '⌨️ WASD: OFF';
                button.classList.remove('btn-primary');
                button.classList.add('btn-secondary');
            }
        });
        showMessage('WASD controls disabled', 'info');
    }
    
    // Bind keyboard events if not already bound
    if (!keyboardEventBound) {
        document.addEventListener('keydown', handleKeyDown);
        document.addEventListener('keyup', handleKeyUp);
        keyboardEventBound = true;
    }
}

// Pan/Tilt movement functions
function movePanTiltRelative(panSteps, tiltSteps, fineStep = false) {
    // For WASD control, use the steps directly without multiplying by slider value
    // The steps are already calculated with the correct base step size
    const data = {
        pan_steps: panSteps,
        tilt_steps: tiltSteps,
        fine_step: fineStep
    };
    
    console.log('Sending relative movement:', data);
    
    fetch('/api/pantilt/move_relative', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        console.log('Pan/Tilt Response:', data);
        if (!data.success) {
            showMessage('Pan/Tilt Error: ' + (data.error || 'Unknown error'), 'error');
        }
        // Don't show success messages for WASD to avoid spam
    })
    .catch(error => {
        console.error('Pan/Tilt Error:', error);
        showMessage('Pan/Tilt Communication Error: ' + error, 'error');
    });
}

// Legacy movement function for compatibility
function movePanTilt(action, params = {}) {
    let endpoint = '/api/pantilt/status';
    let method = 'GET';
    let data = {};
    
    switch(action) {
        case 'move_relative':
            endpoint = '/api/pantilt/move_relative';
            method = 'POST';
            data = params;
            break;
        case 'go_home':
            endpoint = '/api/pantilt/home';
            method = 'POST';
            break;
        case 'set_speed':
            // Speed setting not implemented in new API
            console.log('Speed setting not supported in new API');
            return;
        default:
            console.log('Unknown action:', action);
            return;
    }
    
    console.log('Sending pan/tilt command:', data);
    
    fetch(endpoint, {
        method: method,
        headers: {
            'Content-Type': 'application/json',
        },
        body: method === 'POST' ? JSON.stringify(data) : undefined
    })
    .then(response => response.json())
    .then(data => {
        console.log('Pan/Tilt Response:', data);
        if (data.success) {
            showMessage(data.message || 'Movement completed', 'success');
            // Auto-refresh status after movement
            setTimeout(refreshPanTiltStatus, 500);
        } else {
            showMessage('Pan/Tilt Error: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        console.error('Pan/Tilt Error:', error);
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
    fetch('/api/pantilt/status')
    .then(response => response.json())
    .then(data => {
        if (data.success && data.status) {
            const status = data.status;
            
            if (status.position) {
                updatePanTiltPosition(status.position.pan, status.position.tilt);
            }
            
            // Update motor status
            updateMotorStatus(status.motors_enabled);
            
            // Update keepalive status
            if (status.hasOwnProperty('keepalive_enabled')) {
                updateKeepaliveStatus(status.keepalive_enabled);
            }
            
            // Update connection status
            const statusIndicator = document.getElementById('pantilt-control-status');
            if (statusIndicator) {
                if (status.connected) {
                    statusIndicator.className = 'status-indicator active';
                    statusIndicator.textContent = 'Connected';
                } else {
                    statusIndicator.className = 'status-indicator inactive';
                    statusIndicator.textContent = 'Disconnected';
                }
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
    
    const endpoint = isCurrentlyEnabled ? '/api/pantilt/disable_motors' : '/api/pantilt/enable_motors';
    
    fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        console.log('Motors toggle response:', data);
        if (data.success) {
            updateMotorStatus(!isCurrentlyEnabled);
            showMessage(data.message || `Motors ${!isCurrentlyEnabled ? 'enabled' : 'disabled'}`, 'success');
        } else {
            showMessage('Motor toggle failed: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        console.error('Motor toggle error:', error);
        showMessage('Error toggling motors: ' + error, 'error');
    });
}

function enablePanTiltMotors() {
    fetch('/api/pantilt/enable_motors', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            updateMotorStatus(true);
        } else {
            console.error('Motor enable failed:', data.error);
        }
    })
    .catch(error => {
        console.error('Motor enable error:', error);
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
    
    const endpoint = isCurrentlyEnabled ? '/api/pantilt/stop_keepalive' : '/api/pantilt/start_keepalive';
    
    fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        console.log('Keepalive toggle response:', data);
        if (data.success) {
            updateKeepaliveStatus(!isCurrentlyEnabled);
            showMessage(data.message || `Keepalive ${!isCurrentlyEnabled ? 'enabled' : 'disabled'}`, 'success');
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