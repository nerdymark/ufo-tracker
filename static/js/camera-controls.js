// Camera controls and settings management

// Camera control status tracking
let cameraControlStatus = { ir: 'inactive', hq: 'inactive' };
let dynamicModeState = { ir: false, hq: false };

// Update camera control status indicator
function updateControlStatus(camera, status) {
    cameraControlStatus[camera] = status;
    const statusIndicator = document.getElementById(camera + '-control-status');
    if (statusIndicator) {
        statusIndicator.className = 'status-indicator ' + status;
        statusIndicator.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    }
}

// Camera settings management
function applySettings(camera) {
    updateControlStatus(camera, 'updating');
    
    const exposure = document.getElementById(camera + '-exposure').value;
    const gain = document.getElementById(camera + '-gain').value;
    const autoExposure = document.getElementById(camera + '-auto-exposure').checked;
    const brightness = document.getElementById(camera + '-brightness').value;
    const contrast = document.getElementById(camera + '-contrast').value;
    
    const settings = {
        exposure_time: parseInt(exposure),
        gain: parseFloat(gain),
        auto_exposure: autoExposure,
        brightness: parseFloat(brightness),
        contrast: parseFloat(contrast)
    };
    
    fetch('/api/camera_settings/' + camera, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings)
    })
    .then(response => response.json())
    .then(data => {
        console.log('Camera settings response:', data);
        if (data.success) {
            updateControlStatus(camera, 'active');
            showMessage('Settings applied successfully', 'success');
            
            // Refresh camera preview after settings change
            setTimeout(() => refreshCamera(camera), 1000);
        } else {
            updateControlStatus(camera, 'inactive');
            showMessage('Settings failed: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        updateControlStatus(camera, 'inactive');
        showMessage('Error applying settings: ' + error, 'error');
        console.error('Settings error:', error);
    });
}

// Auto exposure toggle
function updateAutoExposure(camera) {
    const checkbox = document.getElementById(camera + '-auto-exposure');
    const exposureSlider = document.getElementById(camera + '-exposure');
    const gainSlider = document.getElementById(camera + '-gain');
    
    if (checkbox.checked) {
        exposureSlider.disabled = true;
        gainSlider.disabled = true;
        exposureSlider.style.opacity = '0.5';
        gainSlider.style.opacity = '0.5';
    } else {
        exposureSlider.disabled = false;
        gainSlider.disabled = false;
        exposureSlider.style.opacity = '1';
        gainSlider.style.opacity = '1';
    }
}

// Dynamic exposure mode toggle
function toggleDynamicMode(camera) {
    updateControlStatus(camera, 'updating');
    
    fetch('/api/camera_dynamic_exposure/' + camera, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        console.log(`Dynamic exposure response for ${camera}:`, data);
        if (data.success) {
            updateControlStatus(camera, 'active');
            showMessage(`Dynamic exposure applied: ${data.adjustment}`, 'success');
            
            // Update sliders with new settings if provided
            if (data.settings) {
                document.getElementById(camera + '-exposure').value = data.settings.exposure_time;
                document.getElementById(camera + '-gain').value = data.settings.gain;
                document.getElementById(camera + '-brightness').value = data.settings.brightness;
                document.getElementById(camera + '-contrast').value = data.settings.contrast;
                
                // Update displays
                updateExposureDisplay(camera);
                updateGainDisplay(camera);
                updateBrightnessDisplay(camera);
                updateContrastDisplay(camera);
            }
            
            // Toggle button appearance
            dynamicModeState[camera] = !dynamicModeState[camera];
            const button = document.getElementById(camera + '-dynamic-toggle');
            if (dynamicModeState[camera]) {
                button.classList.remove('btn-info');
                button.classList.add('btn-success');
                button.innerHTML = '📊 Dynamic On';
            } else {
                button.classList.remove('btn-success');
                button.classList.add('btn-info');
                button.innerHTML = '📊 Dynamic Mode';
            }
            
            // Refresh preview after camera adjusts
            setTimeout(() => refreshCamera(camera), 1000);
        } else {
            updateControlStatus(camera, 'inactive');
            showMessage('Dynamic exposure failed: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        updateControlStatus(camera, 'inactive');
        showMessage('Error applying dynamic exposure: ' + error, 'error');
        console.error('Dynamic exposure error:', error);
    });
}

// Auto-tune camera with comprehensive sampling
function autoTuneCamera(camera, quickMode = false) {
    updateControlStatus(camera, 'updating');
    showMessage(`Starting ${quickMode ? 'quick' : 'comprehensive'} auto-tune for ${camera.toUpperCase()} camera...`, 'info');
    
    fetch('/api/camera_auto_tune/' + camera, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ quick_mode: quickMode })
    })
    .then(response => response.json())
    .then(data => {
        console.log(`Auto-tune response for ${camera}:`, data);
        if (data.success) {
            updateControlStatus(camera, 'active');
            showMessage(`Auto-tune complete: ${data.message}`, 'success');
            
            // Update sliders with new settings
            if (data.settings) {
                document.getElementById(camera + '-exposure').value = data.settings.exposure_time;
                document.getElementById(camera + '-gain').value = data.settings.gain;
                document.getElementById(camera + '-brightness').value = data.settings.brightness;
                document.getElementById(camera + '-contrast').value = data.settings.contrast;
                
                // Update displays
                updateExposureDisplay(camera);
                updateGainDisplay(camera);
                updateBrightnessDisplay(camera);
                updateContrastDisplay(camera);
            }
            
            // Refresh preview after camera adjusts
            setTimeout(() => refreshCamera(camera), 1000);
        } else {
            updateControlStatus(camera, 'inactive');
            showMessage('Auto-tune failed: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        updateControlStatus(camera, 'inactive');
        showMessage('Error during auto-tuning: ' + error, 'error');
        console.error('Auto-tune error:', error);
    });
}

// Fine-tune current camera settings
function fineTuneCamera(camera) {
    updateControlStatus(camera, 'updating');
    showMessage(`Starting fine-tuning for ${camera.toUpperCase()} camera...`, 'info');
    
    fetch('/api/camera_fine_tune/' + camera, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        console.log(`Fine-tune response for ${camera}:`, data);
        if (data.success) {
            updateControlStatus(camera, 'active');
            showMessage(`Fine-tuning complete: ${data.improvement || data.message}`, 'success');
            
            // Update sliders with improved settings
            if (data.settings) {
                document.getElementById(camera + '-exposure').value = data.settings.exposure_time;
                document.getElementById(camera + '-gain').value = data.settings.gain;
                document.getElementById(camera + '-brightness').value = data.settings.brightness;
                document.getElementById(camera + '-contrast').value = data.settings.contrast;
                
                // Update displays
                updateExposureDisplay(camera);
                updateGainDisplay(camera);
                updateBrightnessDisplay(camera);
                updateContrastDisplay(camera);
            }
            
            // Refresh preview after camera adjusts
            setTimeout(() => refreshCamera(camera), 1000);
        } else {
            updateControlStatus(camera, 'inactive');
            showMessage('Fine-tuning failed: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        updateControlStatus(camera, 'inactive');
        showMessage('Error during fine-tuning: ' + error, 'error');
        console.error('Fine-tune error:', error);
    });
}

// Preset mode functions
function setDayMode(camera) {
    updateControlStatus(camera, 'updating');
    
    fetch('/api/camera_day_mode/' + camera, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        console.log('Day mode response:', data);
        if (data.success) {
            updateControlStatus(camera, 'active');
            showMessage('Day mode applied', 'success');
            
            // Update sliders with new settings
            if (data.settings) {
                document.getElementById(camera + '-exposure').value = data.settings.exposure_time;
                document.getElementById(camera + '-gain').value = data.settings.gain;
                document.getElementById(camera + '-brightness').value = data.settings.brightness;
                document.getElementById(camera + '-contrast').value = data.settings.contrast;
                
                // Update displays
                updateExposureDisplay(camera);
                updateGainDisplay(camera);
                updateBrightnessDisplay(camera);
                updateContrastDisplay(camera);
            }
            
            // Refresh preview after camera adjusts
            setTimeout(() => refreshCamera(camera), 1000);
        } else {
            updateControlStatus(camera, 'inactive');
            showMessage('Day mode failed: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        updateControlStatus(camera, 'inactive');
        showMessage('Error setting day mode: ' + error, 'error');
        console.error('Day mode error:', error);
    });
}

function setNightMode(camera) {
    updateControlStatus(camera, 'updating');
    
    fetch('/api/camera_night_mode/' + camera, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        console.log('Night mode response:', data);
        if (data.success) {
            updateControlStatus(camera, 'active');
            showMessage('Night mode applied', 'success');
            
            // Update sliders with new settings
            if (data.settings) {
                document.getElementById(camera + '-exposure').value = data.settings.exposure_time;
                document.getElementById(camera + '-gain').value = data.settings.gain;
                document.getElementById(camera + '-brightness').value = data.settings.brightness;
                document.getElementById(camera + '-contrast').value = data.settings.contrast;
                
                // Update displays
                updateExposureDisplay(camera);
                updateGainDisplay(camera);
                updateBrightnessDisplay(camera);
                updateContrastDisplay(camera);
            }
            
            // Refresh preview after camera adjusts
            setTimeout(() => refreshCamera(camera), 1000);
        } else {
            updateControlStatus(camera, 'inactive');
            showMessage('Night mode failed: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        updateControlStatus(camera, 'inactive');
        showMessage('Error setting night mode: ' + error, 'error');
        console.error('Night mode error:', error);
    });
}

// Display update functions for sliders
function updateExposureDisplay(camera) {
    const slider = document.getElementById(camera + '-exposure');
    const display = document.getElementById(camera + '-exposure-value');
    if (slider && display) {
        const value = parseInt(slider.value);
        if (value >= 1000000) {
            // Convert to seconds for values >= 1 second
            display.textContent = (value / 1000000).toFixed(1) + 's';
        } else {
            // Keep milliseconds for values < 1 second
            display.textContent = (value / 1000).toFixed(1) + 'ms';
        }
    }
}

function updateGainDisplay(camera) {
    const slider = document.getElementById(camera + '-gain');
    const display = document.getElementById(camera + '-gain-value');
    if (slider && display) {
        display.textContent = parseFloat(slider.value).toFixed(1) + 'x';
    }
}

function updateBrightnessDisplay(camera) {
    const slider = document.getElementById(camera + '-brightness');
    const display = document.getElementById(camera + '-brightness-value');
    if (slider && display) {
        const value = parseFloat(slider.value);
        display.textContent = (value >= 0 ? '+' : '') + value.toFixed(1);
    }
}

function updateContrastDisplay(camera) {
    const slider = document.getElementById(camera + '-contrast');
    const display = document.getElementById(camera + '-contrast-value');
    if (slider && display) {
        display.textContent = parseFloat(slider.value).toFixed(1) + 'x';
    }
}