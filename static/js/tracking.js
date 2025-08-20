// Auto-tracking and motion detection functionality

let trackingStatusInterval = null;

// Auto-tracking controls
function startAutoTracker() {
    fetch('/api/auto_tracker/start', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage('Auto-tracker started successfully', 'success');
            updateTrackerButton(true);
            // Start status monitoring
            if (!trackingStatusInterval) {
                trackingStatusInterval = setInterval(refreshTrackingStatus, 2000);
            }
        } else {
            showMessage('Failed to start auto-tracker: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        showMessage('Error starting auto-tracker: ' + error, 'error');
        console.error('Auto-tracker start error:', error);
    });
}

function stopAutoTracker() {
    fetch('/api/auto_tracker/stop', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage('Auto-tracker stopped successfully', 'success');
            updateTrackerButton(false);
            // Stop status monitoring
            if (trackingStatusInterval) {
                clearInterval(trackingStatusInterval);
                trackingStatusInterval = null;
            }
        } else {
            showMessage('Failed to stop auto-tracker: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        showMessage('Error stopping auto-tracker: ' + error, 'error');
        console.error('Auto-tracker stop error:', error);
    });
}

function updateTrackerButton(isRunning) {
    const button = document.getElementById('tracker-toggle-btn');
    const enableBtn = document.getElementById('enable-tracking-btn');
    
    if (button) {
        if (isRunning) {
            button.innerHTML = '⏹️ Stop Tracking';
            button.classList.remove('btn-success');
            button.classList.add('btn-danger');
            button.onclick = stopAutoTracker;
        } else {
            button.innerHTML = '▶️ Start Tracking';
            button.classList.remove('btn-danger');
            button.classList.add('btn-success');
            button.onclick = startAutoTracker;
        }
    }
    
    // Also update the enable-tracking-btn in auto-tracking view
    if (enableBtn) {
        if (isRunning) {
            enableBtn.textContent = 'Disable Tracking';
            enableBtn.classList.remove('btn-success');
            enableBtn.classList.add('btn-danger');
            
            // Update status display
            const statusElement = document.getElementById('tracking-enabled-status');
            if (statusElement) {
                statusElement.textContent = 'Enabled';
                statusElement.style.color = '#4CAF50';
            }
        } else {
            enableBtn.textContent = 'Enable Tracking';
            enableBtn.classList.remove('btn-danger');
            enableBtn.classList.add('btn-success');
            
            // Update status display
            const statusElement = document.getElementById('tracking-enabled-status');
            if (statusElement) {
                statusElement.textContent = 'Disabled';
                statusElement.style.color = '#666';
            }
        }
    }
}

// Tracking status and statistics
function refreshTrackingStatus() {
    fetch('/api/auto_tracker/status')
    .then(response => response.json())
    .then(data => {
        console.log('Tracking status:', data);
        updateTrackingDisplay(data);
    })
    .catch(error => {
        console.error('Error fetching tracking status:', error);
        // Don't show error message as this runs automatically
    });
}

function updateTrackingDisplay(data) {
    // Update status indicator
    const statusElement = document.getElementById('tracking-status');
    if (statusElement) {
        if (data.active) {
            statusElement.className = 'status-indicator active';
            statusElement.textContent = 'Active';
        } else {
            statusElement.className = 'status-indicator inactive';
            statusElement.textContent = 'Inactive';
        }
    }
    
    // Update statistics
    const stats = [
        { id: 'objects-detected', value: data.objects_detected || 0 },
        { id: 'tracking-accuracy', value: (data.accuracy || 0) + '%' },
        { id: 'detection-rate', value: (data.detection_rate || 0) + '/min' },
        { id: 'uptime', value: formatUptime(data.uptime || 0) }
    ];
    
    stats.forEach(stat => {
        const element = document.getElementById(stat.id);
        if (element) {
            element.textContent = stat.value;
        }
    });
    
    // Update tracking button state
    updateTrackerButton(data.active || false);
}

function formatUptime(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    } else if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    } else {
        return `${secs}s`;
    }
}

// Motion detection settings
function updateMotionSettings() {
    const sensitivity = document.getElementById('motion-sensitivity')?.value;
    const minArea = document.getElementById('min-area')?.value;
    const threshold = document.getElementById('threshold')?.value;
    
    const settings = {
        sensitivity: parseInt(sensitivity) || 100,
        min_area: parseInt(minArea) || 2000,
        threshold: parseInt(threshold) || 50
    };
    
    fetch('/api/motion_settings', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage('Motion detection settings updated', 'success');
        } else {
            showMessage('Failed to update settings: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        showMessage('Error updating motion settings: ' + error, 'error');
        console.error('Motion settings error:', error);
    });
}

// Tracking settings
function updateTrackingSettings() {
    const autoCalibration = document.getElementById('auto-calibration')?.checked;
    const trackingSpeed = document.getElementById('tracking-speed')?.value;
    const zoomFactor = document.getElementById('zoom-factor')?.value;
    
    const settings = {
        auto_calibration: autoCalibration || false,
        tracking_speed: parseFloat(trackingSpeed) || 1.0,
        zoom_factor: parseFloat(zoomFactor) || 2.0
    };
    
    fetch('/api/tracking_settings', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage('Tracking settings updated', 'success');
        } else {
            showMessage('Failed to update settings: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        showMessage('Error updating tracking settings: ' + error, 'error');
        console.error('Tracking settings error:', error);
    });
}

// Clear tracking history
function clearTrackingHistory() {
    if (confirm('Are you sure you want to clear all tracking history?')) {
        fetch('/api/auto_tracker/clear_history', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showMessage('Tracking history cleared', 'success');
                refreshTrackingStatus();
            } else {
                showMessage('Failed to clear history: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(error => {
            showMessage('Error clearing tracking history: ' + error, 'error');
            console.error('Clear history error:', error);
        });
    }
}

// Export tracking data
function exportTrackingData() {
    fetch('/api/auto_tracker/export')
    .then(response => {
        if (response.ok) {
            return response.blob();
        } else {
            throw new Error('Export failed');
        }
    })
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `tracking_data_${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        showMessage('Tracking data exported', 'success');
    })
    .catch(error => {
        showMessage('Error exporting tracking data: ' + error, 'error');
        console.error('Export error:', error);
    });
}

// Client-side auto tracking functions
function toggleClientAutoTracking() {
    const btn = document.getElementById('enable-tracking-btn');
    if (!btn) return;
    
    // Check actual motion detection state, not button text
    const isCurrentlyActive = window.motionDetectionActive === true;
    
    if (!isCurrentlyActive) {
        // Start client-side motion detection
        if (typeof startClientMotionDetection === 'function') {
            startClientMotionDetection();
            updateTrackingButtonState(true);
            showMessage('Client-side motion detection started', 'success');
        } else {
            showMessage('Motion detection functions not available', 'error');
        }
    } else {
        // Stop client-side motion detection
        if (typeof stopClientMotionDetection === 'function') {
            stopClientMotionDetection();
            updateTrackingButtonState(false);
            showMessage('Client-side motion detection stopped', 'success');
        } else {
            showMessage('Motion detection functions not available', 'error');
        }
    }
}

// Update tracking button state based on actual tracking status
function updateTrackingButtonState(isActive) {
    const btn = document.getElementById('enable-tracking-btn');
    const statusElement = document.getElementById('tracking-enabled-status');
    
    if (btn) {
        if (isActive) {
            btn.textContent = 'Disable Tracking';
            btn.classList.remove('btn-success');
            btn.classList.add('btn-danger');
        } else {
            btn.textContent = 'Enable Tracking';
            btn.classList.remove('btn-danger');
            btn.classList.add('btn-success');
        }
    }
    
    if (statusElement) {
        statusElement.textContent = isActive ? 'Enabled' : 'Disabled';
        statusElement.style.color = isActive ? '#4CAF50' : '#666';
    }
}

function saveCurrentImage() {
    showMessage('Save Current Image feature not implemented yet', 'info');
    console.log('Save current image function called');
}

function downloadCurrentImage() {
    showMessage('Download Current Image feature not implemented yet', 'info');
    console.log('Download current image function called');
}

function toggleRecording() {
    const btn = document.getElementById('record-btn');
    if (!btn) return;
    
    if (btn.textContent.includes('🔴')) {
        btn.textContent = '⏹️ Stop Record';
        btn.classList.remove('btn-warning');
        btn.classList.add('btn-danger');
        showMessage('Recording started (feature not fully implemented)', 'info');
    } else {
        btn.textContent = '🔴 Record';
        btn.classList.remove('btn-danger');
        btn.classList.add('btn-warning');
        showMessage('Recording stopped', 'info');
    }
}

function toggleAutoRecord() {
    const btn = document.getElementById('auto-record-btn');
    if (!btn) return;
    
    if (btn.textContent.includes('📹')) {
        btn.textContent = '⏹️ Stop Auto-Record';
        btn.classList.remove('btn-secondary');
        btn.classList.add('btn-danger');
        showMessage('Auto-recording enabled (feature not fully implemented)', 'info');
    } else {
        btn.textContent = '📹 Auto-Record';
        btn.classList.remove('btn-danger');
        btn.classList.add('btn-secondary');
        showMessage('Auto-recording disabled', 'info');
    }
}

// Initialize auto-tracking camera feeds
function initializeAutoTrackingFeeds() {
    console.log('Initializing auto-tracking camera feeds');
    
    // Initialize IR motion feed
    const irMotionFeed = document.getElementById('ir-motion-feed');
    if (irMotionFeed && irMotionFeed.dataset.src) {
        irMotionFeed.src = irMotionFeed.dataset.src;
        irMotionFeed.onerror = function() {
            console.warn('Failed to load IR motion feed');
        };
        irMotionFeed.onload = function() {
            console.log('IR motion feed loaded successfully');
        };
    }
    
    // Initialize HQ motion feed
    const hqMotionFeed = document.getElementById('hq-motion-feed');
    if (hqMotionFeed && hqMotionFeed.dataset.src) {
        hqMotionFeed.src = hqMotionFeed.dataset.src;
        hqMotionFeed.onerror = function() {
            console.warn('Failed to load HQ motion feed');
        };
        hqMotionFeed.onload = function() {
            console.log('HQ motion feed loaded successfully');
        };
    }
    
    showMessage('Auto-tracking camera feeds initialized', 'info');
}

// Update motion sensitivity
function updateSensitivity() {
    const slider = document.getElementById('motion-sensitivity');
    const display = document.getElementById('sensitivity-display');
    const statusValue = document.getElementById('sensitivity-value');
    
    if (slider && display) {
        const value = parseInt(slider.value);
        display.textContent = value;
        
        if (statusValue) {
            let level = 'Low';
            if (value >= 30 && value < 70) level = 'Medium';
            else if (value >= 70) level = 'High';
            statusValue.textContent = level;
        }
        
        console.log('Motion sensitivity updated to:', value);
        showMessage(`Motion sensitivity set to ${value}`, 'info');
    }
}

// Motor tracking state
let motorTrackingActive = false;
let motorTrackingInterval = null;
let lastMotorMove = 0;
const MOTOR_MOVE_COOLDOWN = 1000; // 1 second between motor moves (reduced for better tracking)

// Toggle motor tracking on/off
function toggleMotorTracking() {
    if (motorTrackingActive) {
        stopAutoTracking();
    } else {
        startAutoTracking();
    }
}

// Update motor tracking button state
function updateMotorTrackingButton(isActive) {
    const btn = document.getElementById('motor-tracking-btn');
    if (btn) {
        if (isActive) {
            btn.textContent = '⏹️ Stop Motor Tracking';
            btn.classList.remove('btn-success');
            btn.classList.add('btn-danger');
        } else {
            btn.textContent = '🚀 Start Motor Tracking';
            btn.classList.remove('btn-danger');
            btn.classList.add('btn-success');
        }
    }
}

// Motor control functions for Auto-Tracking section
function startAutoTracking() {
    // First enable the motors
    fetch('/api/pan_tilt/motors', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: true })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage('Motors enabled for auto-tracking', 'success');
            // Then start keepalive to prevent motors from timing out
            return fetch('/api/pan_tilt/keepalive', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: true })
            });
        } else {
            throw new Error(data.error || 'Failed to enable motors');
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Start the motor tracking loop
            motorTrackingActive = true;
            startMotorTrackingLoop();
            updateMotorTrackingButton(true);
            showMessage('Auto-tracking system started (motors enabled + tracking active)', 'success');
            updateAutoTrackingStatus();
        } else {
            showMessage('Motors enabled but keepalive failed: ' + (data.error || 'Unknown error'), 'warning');
        }
    })
    .catch(error => {
        showMessage('Error starting auto-tracking: ' + error, 'error');
        console.error('Auto-tracking start error:', error);
    });
}

function stopAutoTracking() {
    // Stop the tracking loop first
    motorTrackingActive = false;
    if (motorTrackingInterval) {
        clearInterval(motorTrackingInterval);
        motorTrackingInterval = null;
    }
    
    // Stop keepalive first
    fetch('/api/pan_tilt/keepalive', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: false })
    })
    .then(response => response.json())
    .then(data => {
        // Then disable motors
        return fetch('/api/pan_tilt/motors', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: false })
        });
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            updateMotorTrackingButton(false);
            showMessage('Auto-tracking stopped (motors disabled)', 'success');
            updateAutoTrackingStatus();
        } else {
            showMessage("Failed to disable motors: " + (data.error || "Unknown error"), "error");
        }
    })
    .catch(error => {
        showMessage('Error stopping auto-tracking: ' + error, 'error');
        console.error('Auto-tracking stop error:', error);
    });
}

function calibrateAutoTracking() {
    // Home the pan-tilt system to center position
    fetch('/api/pan_tilt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'home' })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage('Motors homed to center position', 'success');
        } else {
            showMessage('Calibration failed: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        showMessage('Error calibrating motors: ' + error, 'error');
        console.error('Calibration error:', error);
    });
}

function updateAutoTrackingStatus() {
    // Check pan-tilt status to determine if motors are active
    fetch('/api/pan_tilt', {
        method: 'GET'
    })
    .then(response => response.json())
    .then(data => {
        console.log('Pan-tilt status:', data);
        const statusElement = document.getElementById('auto-tracking-status');
        if (statusElement) {
            const motorsEnabled = data.motors_enabled && data.keepalive_enabled;
            const isFullyActive = motorsEnabled && motorTrackingActive;
            
            if (isFullyActive) {
                statusElement.textContent = 'Active (Tracking)';
                statusElement.style.color = '#4CAF50';
            } else if (motorsEnabled) {
                statusElement.textContent = 'Motors Ready';
                statusElement.style.color = '#ff9800';
            } else {
                statusElement.textContent = 'Inactive';
                statusElement.style.color = '#666';
            }
        }
    })
    .catch(error => {
        console.error('Error fetching pan-tilt status:', error);
        const statusElement = document.getElementById('auto-tracking-status');
        if (statusElement) {
            statusElement.textContent = 'Error';
            statusElement.style.color = '#f44336';
        }
    });
}

// Motor tracking loop that responds to detected motion
function startMotorTrackingLoop() {
    if (motorTrackingInterval) {
        clearInterval(motorTrackingInterval);
    }
    
    motorTrackingInterval = setInterval(() => {
        if (!motorTrackingActive) return;
        
        // Enhanced debug logging to understand the state
        const debugInfo = {
            timestamp: new Date().toLocaleTimeString(),
            motorTrackingActive,
            motionStateExists: typeof motionState !== 'undefined',
            motionDetectionActive: window.motionDetectionActive,
            motionStateStructure: typeof motionState !== 'undefined' ? {
                hasIr: !!motionState.ir,
                hasMotionAreas: !!(motionState.ir && motionState.ir.motionAreas),
                motionAreasCount: motionState.ir && motionState.ir.motionAreas ? motionState.ir.motionAreas.length : 0,
                actualMotionAreas: motionState.ir && motionState.ir.motionAreas ? motionState.ir.motionAreas : []
            } : 'undefined'
        };
        
        // Only log every 5 seconds to reduce spam, or when motion is detected
        const shouldLog = (Date.now() - (window.lastMotorDebugLog || 0) > 5000) || 
                         (debugInfo.motionStateStructure && debugInfo.motionStateStructure.motionAreasCount > 0);
        
        if (shouldLog) {
            console.log('🎯 Motor tracking debug:', debugInfo);
            window.lastMotorDebugLog = Date.now();
        }
        
        // Check if motion detection is active and has detected objects
        if (typeof motionState === 'undefined') {
            // No motion state available
            return;
        }
        
        if (!window.motionDetectionActive) {
            // Motion detection not active - this is required for motor tracking
            if (shouldLog) {
                console.log('⚠️ Motor tracking active but motion detection is OFF. Enable motion detection first.');
            }
            return;
        }
        
        if (motionState.ir && 
            motionState.ir.motionAreas && 
            motionState.ir.motionAreas.length > 0) {
            
            console.log('Motion areas found:', motionState.ir.motionAreas);
            
            // Get the largest motion area (most significant detection)
            const largestMotionArea = motionState.ir.motionAreas.reduce((largest, current) => {
                const currentArea = current.width * current.height;
                const largestArea = largest.width * largest.height;
                return currentArea > largestArea ? current : largest;
            });
            
            if (largestMotionArea) { // Any motion area is valid
                const now = Date.now();
                if (now - lastMotorMove > MOTOR_MOVE_COOLDOWN) {
                    console.log('Tracking motion area:', largestMotionArea);
                    trackMotionArea(largestMotionArea);
                    lastMotorMove = now;
                } else {
                    console.log('Motor move on cooldown, remaining:', MOTOR_MOVE_COOLDOWN - (now - lastMotorMove), 'ms');
                }
            } else {
                console.log('No valid motion area found');
            }
        }
    }, 200); // Check for motion every 200ms for better responsiveness
}

// Calculate motor movement based on motion area position
function trackMotionArea(motionArea) {
    // Get actual resolution from motion detection system
    const irCanvas = document.getElementById('ir-motion-canvas');
    const irFeed = document.getElementById('ir-motion-feed');
    
    // Use motion detection canvas resolution (this is what motion coordinates are based on)
    let cameraWidth = 640;
    let cameraHeight = 480;
    
    if (irCanvas) {
        cameraWidth = irCanvas.width;
        cameraHeight = irCanvas.height;
        console.log('📐 Using canvas resolution:', {cameraWidth, cameraHeight});
    } else if (irFeed) {
        // Fallback to image element dimensions
        cameraWidth = irFeed.width || irFeed.offsetWidth || 640;
        cameraHeight = irFeed.height || irFeed.offsetHeight || 480;
        console.log('📐 Using feed element resolution:', {cameraWidth, cameraHeight});
    } else {
        console.warn('📐 Using default resolution (no canvas/feed found):', {cameraWidth, cameraHeight});
    }
    
    // Calculate center of motion area
    const motionCenterX = motionArea.x + motionArea.width / 2;
    const motionCenterY = motionArea.y + motionArea.height / 2;
    
    // Calculate center of camera view
    const cameraCenterX = cameraWidth / 2;
    const cameraCenterY = cameraHeight / 2;
    
    // Calculate how far from center the motion is (normalized -1 to 1)
    const offsetX = (motionCenterX - cameraCenterX) / cameraCenterX;
    const offsetY = (motionCenterY - cameraCenterY) / cameraCenterY;
    
    // Convert to motor movement with improved scaling
    // Reduced scaling factors for more precise movement
    const panMovement = offsetX * 8; // degrees (reduced from 10)
    const tiltMovement = -offsetY * 6; // degrees (reduced from 8, inverted because Y increases downward)
    
    // Convert to motor steps (1.8° per step for typical stepper motors)
    const panSteps = Math.round(panMovement / 1.8);
    const tiltSteps = Math.round(tiltMovement / 1.8);
    
    // Log detailed motion analysis
    console.log('🎯 Motion Analysis:', {
        motionArea: {x: motionArea.x, y: motionArea.y, w: motionArea.width, h: motionArea.height},
        motionCenter: {x: motionCenterX, y: motionCenterY},
        cameraCenter: {x: cameraCenterX, y: cameraCenterY},
        offsets: {x: offsetX.toFixed(3), y: offsetY.toFixed(3)},
        movement: {pan: panMovement.toFixed(2) + '°', tilt: tiltMovement.toFixed(2) + '°'},
        steps: {pan: panSteps, tilt: tiltSteps}
    });
    
    // More sensitive movement threshold (reduced from 0.2 to 0.1)
    if (Math.abs(offsetX) > 0.1 || Math.abs(offsetY) > 0.1) {
        console.log(`🚀 Moving motors: pan ${panSteps} steps (${panMovement.toFixed(2)}°), tilt ${tiltSteps} steps (${tiltMovement.toFixed(2)}°)`);
        
        // Send relative movement command to motors
        fetch('/api/pan_tilt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'move_relative',
                pan_steps: panSteps,
                tilt_steps: tiltSteps
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('✅ Motor movement successful:', data);
                // Update last successful tracking time
                window.lastSuccessfulTracking = Date.now();
            } else {
                console.warn('❌ Motor movement failed:', data.error);
            }
        })
        .catch(error => {
            console.error('💥 Motor movement error:', error);
        });
    } else {
        console.log(`📍 Motion too close to center (${offsetX.toFixed(3)}, ${offsetY.toFixed(3)}) - no movement needed`);
    }
}