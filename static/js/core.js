// Core dashboard functionality
// Global variables
let autoRefreshIntervals = { ir: null, hq: null, system: null };
let refreshInterval = 10000; // 10 seconds default for performance

// Dashboard initialization
function initializeDashboard() {
    console.log('Page loaded. toggleMotors function exists:', typeof toggleMotors);
    console.log('motor-toggle-btn element exists:', document.getElementById('motor-toggle-btn'));
    updateSystemTime();
    setInterval(updateSystemTime, 1000);
    initializeStepSize();
    
    // Don't initialize auto-tracking status on page load - only when in autotrack mode
    // refreshTrackingStatus();
    
    // Set default view to cameras
    showSection('cameras');
    setViewMode('live'); // Start with live streams
    
    // Initialize interval display
    refreshIntervalDisplay();
    
    // Initialize live streams
    initializeLiveStreams();
    
    // Initialize status bar immediately
    refreshSystemStatus();
    
    // Set up periodic status updates (every 5 seconds)
    setInterval(refreshSystemStatus, 5000);
    
    console.log('Dashboard initialized');
}

// System time update
function updateSystemTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('en-US', { 
        hour12: false, 
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit' 
    });
    const dateString = now.toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
    
    const timeElement = document.getElementById('current-time');
    const dateElement = document.getElementById('current-date');
    const systemTimeElement = document.getElementById('system-time');
    
    if (timeElement) timeElement.textContent = timeString;
    if (dateElement) dateElement.textContent = dateString;
    if (systemTimeElement) systemTimeElement.textContent = `${dateString} ${timeString}`;
}

// Initialize live camera streams
function initializeLiveStreams() {
    const irStream = document.getElementById('ir-live');
    const hqStream = document.getElementById('hq-live');
    
    if (irStream && irStream.dataset.src) {
        irStream.src = irStream.dataset.src;
        console.log('IR live stream initialized');
    }
    
    if (hqStream && hqStream.dataset.src) {
        hqStream.src = hqStream.dataset.src;
        console.log('HQ live stream initialized');
    }
}

// Step size management
function updateStepSize() {
    const slider = document.getElementById('step-size');
    const display = document.getElementById('step-size-value');
    const stepSize = parseInt(slider.value);
    
    if (display) {
        display.textContent = stepSize;
    }
    
    // Store step size in local storage for persistence
    localStorage.setItem('panTiltStepSize', stepSize);
}

// Initialize step size from localStorage on page load
function initializeStepSize() {
    const savedStepSize = localStorage.getItem('panTiltStepSize');
    if (savedStepSize) {
        const slider = document.getElementById('step-size');
        const display = document.getElementById('step-size-value');
        if (slider) {
            slider.value = savedStepSize;
            if (display) {
                display.textContent = savedStepSize;
            }
        }
    }
}

// Refresh system status bar
function refreshSystemStatus() {
    // Fetch system status from API
    fetch('/api/system_status')
        .then(response => response.json())
        .then(data => {
            // Update IR camera status
            const irStatus = document.getElementById('ir-status-bar');
            const irIndicator = document.getElementById('ir-indicator-bar');
            if (irStatus && data.cameras) {
                const irActive = data.cameras.ir && data.cameras.ir.active;
                irStatus.textContent = irActive ? 'Active' : 'Inactive';
                if (irIndicator) {
                    irIndicator.style.backgroundColor = irActive ? '#4CAF50' : '#666';
                }
            }
            
            // Update HQ camera status
            const hqStatus = document.getElementById('hq-status-bar');
            const hqIndicator = document.getElementById('hq-indicator-bar');
            if (hqStatus && data.cameras) {
                const hqActive = data.cameras.hq && data.cameras.hq.active;
                hqStatus.textContent = hqActive ? 'Active' : 'Inactive';
                if (hqIndicator) {
                    hqIndicator.style.backgroundColor = hqActive ? '#4CAF50' : '#666';
                }
            }
            
            // Update Motion detection status
            const motionStatus = document.getElementById('motion-status-bar');
            const motionIndicator = document.getElementById('motion-indicator-bar');
            if (motionStatus) {
                // Check if motion detection is active (client-side)
                const motionActive = window.motionDetectionActive || false;
                motionStatus.textContent = motionActive ? 'Tracking' : 'Idle';
                if (motionIndicator) {
                    motionIndicator.style.backgroundColor = motionActive ? '#ffa500' : '#666';
                }
            }
            
            // Update Storage status
            const storageStatus = document.getElementById('storage-status-bar');
            const storageIndicator = document.getElementById('storage-indicator-bar');
            if (storageStatus && data.storage) {
                const usedPercent = Math.round((data.storage.used / data.storage.total) * 100);
                storageStatus.textContent = `${usedPercent}%`;
                if (storageIndicator) {
                    // Color code based on usage
                    let color = '#4CAF50'; // Green
                    if (usedPercent > 80) color = '#ff6b6b'; // Red
                    else if (usedPercent > 60) color = '#ffa500'; // Orange
                    storageIndicator.style.backgroundColor = color;
                }
            }
        })
        .catch(error => {
            console.error('Error fetching system status:', error);
            // Set all to error state
            ['ir-status-bar', 'hq-status-bar', 'motion-status-bar', 'storage-status-bar'].forEach(id => {
                const element = document.getElementById(id);
                if (element) element.textContent = 'Error';
            });
            ['ir-indicator-bar', 'hq-indicator-bar', 'motion-indicator-bar', 'storage-indicator-bar'].forEach(id => {
                const element = document.getElementById(id);
                if (element) element.style.backgroundColor = '#ff6b6b';
            });
        });
}

// Initialize the dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', initializeDashboard);

// Cleanup function for page unload  
window.addEventListener('beforeunload', function(event) {
    // Stop all auto refresh intervals
    Object.values(autoRefreshIntervals).forEach(interval => {
        if (interval) {
            clearInterval(interval);
        }
    });
    
    // Clear pan/tilt auto refresh if running
    if (window.panTiltAutoRefresh) {
        clearInterval(window.panTiltAutoRefresh);
    }
});