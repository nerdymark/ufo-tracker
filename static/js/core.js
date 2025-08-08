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