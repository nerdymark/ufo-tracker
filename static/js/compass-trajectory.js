// Compass and Trajectory Control Functions

let trajectoryOverlay = null;
let trajectoryOverlays = [];
let trajectoryEnabled = false;
let compassUpdateInterval = null;

// Initialize trajectory overlay when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Initialize overlays for both camera feeds
    initializeTrajectoryOverlays();

    // Start compass status updates
    updateCompassStatus();

    // Register with update manager if available (better performance)
    if (typeof updateManager !== 'undefined') {
        updateManager.register('compassStatus', updateCompassStatus, 3, false);
        updateManager.register('levelStatus', updateLevelStatus, 2, false);
    } else {
        // Fallback to setInterval
        setInterval(updateCompassStatus, 3000);
        setInterval(updateLevelStatus, 2000);
    }
});

function initializeTrajectoryOverlays() {
    // We'll initialize overlays when trajectories are enabled
    console.log('Trajectory overlay system ready');
}

// Compass Functions
async function calibrateCompass() {
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
                updateCompassStatus();
            } else {
                showNotification('Calibration failed: ' + (data.error || 'Unknown error'), 'error');
            }
        }
    } catch (error) {
        console.error('Error calibrating compass:', error);
        showNotification('Error calibrating compass', 'error');
    }
}

async function calibrateCompassNorth() {
    try {
        const response = await fetch('/api/sensor/compass/set_north', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification('North reference set to current heading!', 'success');
            updateCompassStatus();
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
            updateCompassStatus();
        } else {
            showNotification('Setting declination failed: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error setting magnetic declination:', error);
        showNotification('Error setting magnetic declination', 'error');
    }
}

async function calibrateLevelAndNorth() {
    try {
        // First check if device is level
        const levelResponse = await fetch('/api/sensor/is_level?tolerance=5');
        const levelData = await levelResponse.json();

        if (!levelData.success) {
            showNotification('Error checking level status', 'error');
            return;
        }

        if (!levelData.is_level) {
            showNotification(
                `Device is not level (tilt=${levelData.tilt_angle.toFixed(1)}°). Please level the device pointing upward and try again.`,
                'error'
            );
            return;
        }

        // Device is level, proceed with calibration
        showNotification('Device is level! Starting north calibration...', 'info');

        const response = await fetch('/api/sensor/calibrate/level_north', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                samples: 100,
                tolerance: 5.0
            })
        });

        const data = await response.json();

        if (data.success) {
            showNotification(data.message || 'Level-and-north calibration completed!', 'success');
            updateCompassStatus();

            // Invalidate compass cache to force refresh
            if (typeof apiCache !== 'undefined') {
                apiCache.invalidatePattern(/sensor.*compass/);
            }
        } else {
            showNotification('Calibration failed: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error in level-and-north calibration:', error);
        showNotification('Error during calibration', 'error');
    }
}

async function updateLevelStatus() {
    try {
        const response = await fetch('/api/sensor/is_level?tolerance=5');
        const data = await response.json();

        if (data.success) {
            const levelElement = document.getElementById('level-status');
            const tiltElement = document.getElementById('tilt-angle');

            if (levelElement) {
                levelElement.textContent = data.is_level ? '✓ Level' : '✗ Not Level';
                levelElement.className = data.is_level ? 'badge badge-success' : 'badge badge-warning';
            }

            if (tiltElement) {
                tiltElement.textContent = `${data.tilt_angle.toFixed(1)}°`;
            }
        }
    } catch (error) {
        console.warn('Level status not available:', error.message);
    }
}

async function updateCompassReading() {
    // This function is no longer needed as the MPU9250 provides real-time data
    // Just update the display with current data
    updateCompassStatus();
}

async function updateCompassStatus() {
    try {
        // First try the MPU9250 endpoint which has both compass and orientation
        let response = await fetch('/api/sensor/mpu9250');
        let data = await response.json();
        
        if (data.success && data.data.compass) {
            const compassData = data.data.compass;
            
            // Update compass display elements
            const headingElement = document.getElementById('compass-heading');
            const statusElement = document.getElementById('compass-status');
            const trueHeadingElement = document.getElementById('compass-true-heading');
            const declinationElement = document.getElementById('compass-declination');
            
            if (headingElement) headingElement.textContent = `${compassData.heading.toFixed(1)}°`;
            if (statusElement) statusElement.textContent = compassData.calibrated ? 'Calibrated' : 'Not Calibrated';
            if (trueHeadingElement) trueHeadingElement.textContent = `${compassData.true_heading.toFixed(1)}°`;
            if (declinationElement) declinationElement.textContent = `${compassData.magnetic_declination.toFixed(1)}°`;
            
            // Update all trajectory overlays with compass data
            if (trajectoryEnabled && trajectoryOverlays.length > 0) {
                trajectoryOverlays.forEach(overlay => {
                    overlay.setCompass(compassData.true_heading, compassData.calibrated);
                });
            }
        } else {
            // Fallback to the compass-only endpoint
            response = await fetch('/api/sensor/compass');
            data = await response.json();
            
            if (data.success) {
                const compassData = data.data;
                
                // Update compass display elements
                const headingElement = document.getElementById('compass-heading');
                const statusElement = document.getElementById('compass-status');
                const trueHeadingElement = document.getElementById('compass-true-heading');
                const declinationElement = document.getElementById('compass-declination');
                
                if (headingElement) headingElement.textContent = `${compassData.heading.toFixed(1)}°`;
                if (statusElement) statusElement.textContent = compassData.calibrated ? 'Calibrated' : 'Not Calibrated';
                if (trueHeadingElement) trueHeadingElement.textContent = `${compassData.true_heading.toFixed(1)}°`;
                if (declinationElement) declinationElement.textContent = `${compassData.magnetic_declination.toFixed(1)}°`;
                
                // Update all trajectory overlays with compass data
                if (trajectoryEnabled && trajectoryOverlays.length > 0) {
                    trajectoryOverlays.forEach(overlay => {
                        overlay.setCompass(compassData.true_heading, compassData.calibrated);
                    });
                }
            } else {
                throw new Error(data.error || 'Compass data not available');
            }
        }
    } catch (error) {
        console.warn('Compass sensor not available:', error.message);
        // Update display to show sensor not initialized
        const headingElement = document.getElementById('compass-heading');
        const statusElement = document.getElementById('compass-status');
        
        if (headingElement) headingElement.textContent = '--°';
        if (statusElement) statusElement.textContent = 'Not Initialized';
    }
}

// FOV Functions
function updateFOV() {
    const horizontal = document.getElementById('fov-horizontal').value;
    const vertical = document.getElementById('fov-vertical').value;
    
    document.getElementById('fov-h-value').textContent = `${horizontal}°`;
    document.getElementById('fov-v-value').textContent = `${vertical}°`;
    
    // Don't override camera-specific FOV values
    // Each overlay uses its own FOV based on camera type
    console.log(`FOV sliders updated to ${horizontal}° × ${vertical}° (overlays use camera-specific FOV)`);
}

// Trajectory Functions
function toggleTrajectoryOverlay() {
    const button = document.getElementById('trajectory-toggle');
    
    if (!trajectoryEnabled) {
        // Enable trajectories
        enableTrajectories();
        button.textContent = '🛑 Disable Trajectories';
        button.classList.remove('btn-success');
        button.classList.add('btn-danger');
    } else {
        // Disable trajectories
        disableTrajectories();
        button.textContent = '🚀 Enable Trajectories';
        button.classList.remove('btn-danger');
        button.classList.add('btn-success');
    }
}

function enableTrajectories() {
    console.log('Enabling trajectory overlays...');
    trajectoryEnabled = true;
    
    // Function to create overlays for currently visible camera containers
    function createOverlaysForVisibleContainers() {
        const cameraContainers = [
            // Live Streams
            { element: document.querySelector('#ir-live')?.parentElement, id: 'ir-live-overlay', name: 'IR Live' },
            { element: document.querySelector('#hq-live')?.parentElement, id: 'hq-live-overlay', name: 'HQ Live' },
            // Camera Controls
            { element: document.querySelector('#ir-control-preview')?.parentElement, id: 'ir-control-overlay', name: 'IR Control' },
            { element: document.querySelector('#hq-control-preview')?.parentElement, id: 'hq-control-overlay', name: 'HQ Control' },
            // Motion Detection
            { element: document.querySelector('#ir-motion-feed')?.parentElement, id: 'ir-motion-overlay', name: 'IR Motion' },
            { element: document.querySelector('#hq-motion-feed')?.parentElement, id: 'hq-motion-overlay', name: 'HQ Motion' },
            // Stacking
            { element: document.querySelector('#stacked-ir-preview')?.parentElement, id: 'stacked-ir-overlay', name: 'IR Stacking' },
            { element: document.querySelector('#stacked-hq-preview')?.parentElement, id: 'stacked-hq-overlay', name: 'HQ Stacking' },
            // Feature Aligned
            { element: document.querySelector('#aligned-preview')?.parentElement, id: 'aligned-overlay', name: 'Feature Aligned' }
        ];
        
        console.log('Found camera containers:', cameraContainers.map(c => ({ name: c.name, found: !!c.element })));
        
        // Create overlays for each visible camera container
        cameraContainers.forEach(container => {
            if (container.element) {
                // Check if this container is actually visible
                const containerRect = container.element.getBoundingClientRect();
                const isVisible = containerRect.width > 0 && containerRect.height > 0 && 
                                container.element.offsetParent !== null;
                
                if (isVisible) {
                    console.log(`Creating overlay for ${container.name} (${container.id})`);
                    
                    // Give the container an ID if it doesn't have one
                    if (!container.element.id) {
                        container.element.id = container.id;
                    }
                    
                    // Check if overlay already exists for this container
                    const existingOverlay = trajectoryOverlays.find(o => o.container?.id === container.element.id);
                    if (existingOverlay) {
                        console.log(`Overlay already exists for ${container.name}`);
                        return;
                    }
                    
                    // Determine camera type based on container name
                    const cameraType = container.name.toLowerCase().includes('hq') ? 'hq' : 'ir';
                    console.log(`Creating ${cameraType} overlay for ${container.name}`);
                    
                    // Create overlay for this container with correct camera type
                    const overlay = new TrajectoryOverlay(container.element.id, cameraType);
                    overlay.enableProjection(true);
                    
                    // Don't override FOV - let the overlay use its camera-specific FOV
                    // (The FOV is already set based on cameraType in the constructor)
                    
                    // Update settings
                    overlay.showSatellites = document.getElementById('show-satellites').checked;
                    overlay.showAircraft = document.getElementById('show-aircraft').checked;
                    
                    // Store the main overlay reference for control
                    if (!trajectoryOverlay) {
                        trajectoryOverlay = overlay;
                    }
                    
                    // Store all overlays for cleanup
                    trajectoryOverlays.push(overlay);
                } else {
                    console.log(`Container ${container.name} found but not visible`);
                }
            } else {
                console.log(`No container found for ${container.name}`);
            }
        });
    }
    
    // Create overlays for currently visible containers
    createOverlaysForVisibleContainers();
    
    // Set up observer to create overlays when new views become visible
    if (window.MutationObserver) {
        const observer = new MutationObserver(function(mutations) {
            if (trajectoryEnabled) {
                mutations.forEach(function(mutation) {
                    if (mutation.type === 'attributes' && 
                        (mutation.attributeName === 'style' || mutation.attributeName === 'class')) {
                        // Check for newly visible containers
                        setTimeout(createOverlaysForVisibleContainers, 100);
                    }
                });
            }
        });
        
        // Observe changes to the main container
        const mainContainer = document.body;
        observer.observe(mainContainer, {
            attributes: true,
            subtree: true,
            attributeFilter: ['style', 'class']
        });
        
        // Store observer for cleanup
        window.trajectoryObserver = observer;
    }
    
    console.log(`Created ${trajectoryOverlays.length} trajectory overlays`);
    
    document.getElementById('projection-status').textContent = 'Active';
    
    // Start updating trajectory counts
    updateTrajectoryCounts();
}

// Function to create overlays when navigating to a new section
function createOverlaysForNewSection() {
    if (!trajectoryEnabled) return;
    
    console.log('Creating overlays for new section...');
    
    // Run the same logic as enableTrajectories but for newly visible containers
    const cameraContainers = [
        // Live Streams
        { element: document.querySelector('#ir-live')?.parentElement, id: 'ir-live-overlay', name: 'IR Live' },
        { element: document.querySelector('#hq-live')?.parentElement, id: 'hq-live-overlay', name: 'HQ Live' },
        // Camera Controls
        { element: document.querySelector('#ir-control-preview')?.parentElement, id: 'ir-control-overlay', name: 'IR Control' },
        { element: document.querySelector('#hq-control-preview')?.parentElement, id: 'hq-control-overlay', name: 'HQ Control' },
        // Motion Detection
        { element: document.querySelector('#ir-motion-feed')?.parentElement, id: 'ir-motion-overlay', name: 'IR Motion' },
        { element: document.querySelector('#hq-motion-feed')?.parentElement, id: 'hq-motion-overlay', name: 'HQ Motion' },
        // Stacking
        { element: document.querySelector('#stacked-ir-preview')?.parentElement, id: 'stacked-ir-overlay', name: 'IR Stacking' },
        { element: document.querySelector('#stacked-hq-preview')?.parentElement, id: 'stacked-hq-overlay', name: 'HQ Stacking' },
        // Feature Aligned
        { element: document.querySelector('#aligned-preview')?.parentElement, id: 'aligned-overlay', name: 'Feature Aligned' }
    ];
    
    console.log('Found camera containers for new section:', cameraContainers.map(c => ({ name: c.name, found: !!c.element })));
    
    // Create overlays for each newly visible camera container
    cameraContainers.forEach(container => {
        if (container.element) {
            // Check if this container is actually visible
            const containerRect = container.element.getBoundingClientRect();
            const isVisible = containerRect.width > 0 && containerRect.height > 0 && 
                            container.element.offsetParent !== null;
            
            if (isVisible) {
                // Check if overlay already exists for this container
                const existingOverlay = trajectoryOverlays.find(o => o.container?.id === container.element.id);
                if (existingOverlay) {
                    console.log(`Overlay already exists for ${container.name}`);
                    return;
                }
                
                console.log(`Creating new overlay for ${container.name} (${container.id})`);
                
                // Give the container an ID if it doesn't have one
                if (!container.element.id) {
                    container.element.id = container.id;
                }
                
                // Create overlay for this container
                const overlay = new TrajectoryOverlay(container.element.id);
                overlay.enableProjection(true);
                
                // Set current FOV
                const horizontal = parseFloat(document.getElementById('fov-horizontal').value);
                const vertical = parseFloat(document.getElementById('fov-vertical').value);
                overlay.setFOV(horizontal, vertical);
                
                // Update settings
                overlay.showSatellites = document.getElementById('show-satellites').checked;
                overlay.showAircraft = document.getElementById('show-aircraft').checked;
                
                // Set current compass if available
                if (typeof updateCompassStatus === 'function') {
                    updateCompassStatus().then(() => {
                        // Compass data will be updated in the background
                    });
                }
                
                // Store all overlays for cleanup
                trajectoryOverlays.push(overlay);
            } else {
                console.log(`Container ${container.name} found but not visible`);
            }
        }
    });
    
    console.log(`Total trajectory overlays after section change: ${trajectoryOverlays.length}`);
}

function disableTrajectories() {
    trajectoryEnabled = false;
    
    // Clean up all overlays
    trajectoryOverlays.forEach(overlay => {
        overlay.enableProjection(false);
        overlay.destroy();
    });
    
    trajectoryOverlays = [];
    trajectoryOverlay = null;
    
    // Clean up the mutation observer
    if (window.trajectoryObserver) {
        window.trajectoryObserver.disconnect();
        window.trajectoryObserver = null;
    }
    
    document.getElementById('projection-status').textContent = 'Disabled';
    document.getElementById('sat-count').textContent = '--';
    document.getElementById('aircraft-count').textContent = '--';
}

function refreshTrajectories() {
    if (trajectoryEnabled && trajectoryOverlays.length > 0) {
        trajectoryOverlays.forEach(overlay => {
            overlay.updateProjections();
        });
        showNotification('Trajectories refreshed', 'success');
    }
}

function updateTrajectorySettings() {
    const showSatellites = document.getElementById('show-satellites').checked;
    const showAircraft = document.getElementById('show-aircraft').checked;
    
    trajectoryOverlays.forEach(overlay => {
        overlay.showSatellites = showSatellites;
        overlay.showAircraft = showAircraft;
        overlay.updateProjections();
    });
}

async function updateTrajectoryCounts() {
    if (!trajectoryEnabled) return;
    
    try {
        // Get satellite count
        const satResponse = await fetch('/api/satellites/visible');
        if (satResponse.ok) {
            const satData = await satResponse.json();
            document.getElementById('sat-count').textContent = satData.count || 0;
        }
        
        // Get aircraft count
        const acResponse = await fetch('/api/aircraft');
        if (acResponse.ok) {
            const acData = await acResponse.json();
            document.getElementById('aircraft-count').textContent = acData.count || 0;
        }
    } catch (error) {
        console.error('Error updating trajectory counts:', error);
    }
    
    // Schedule next update
    if (trajectoryEnabled) {
        setTimeout(updateTrajectoryCounts, 10000);
    }
}

// Helper function to show notifications
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
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);