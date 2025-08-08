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