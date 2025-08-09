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

// ============================================================================
// System Settings Functions
// ============================================================================

function updateGalleryStats() {
    const statsDiv = document.getElementById('gallery-stats');
    if (!statsDiv) return;
    
    fetch('/api/gallery/images')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const count = data.count || 0;
                const totalSize = data.images.reduce((sum, img) => sum + (img.size || 0), 0);
                const sizeMB = (totalSize / (1024 * 1024)).toFixed(1);
                const sizeGB = (totalSize / (1024 * 1024 * 1024)).toFixed(2);
                
                let displaySize = sizeGB > 1 ? `${sizeGB} GB` : `${sizeMB} MB`;
                
                statsDiv.innerHTML = `
                    📊 <strong>${count.toLocaleString()}</strong> detection images using <strong>${displaySize}</strong> of storage
                `;
                statsDiv.style.color = '#ccc';
            } else {
                statsDiv.innerHTML = '❌ Unable to load gallery statistics';
                statsDiv.style.color = '#ff6b6b';
            }
        })
        .catch(error => {
            console.error('Error loading gallery stats:', error);
            statsDiv.innerHTML = '❌ Error loading gallery statistics';
            statsDiv.style.color = '#ff6b6b';
        });
}

function clearAllGalleryFiles() {
    // Show confirmation dialog
    const confirmed = confirm(
        '⚠️ WARNING: This will permanently delete ALL detection images!\n\n' +
        'This action cannot be undone. Are you absolutely sure you want to continue?\n\n' +
        'Click OK to permanently delete all images, or Cancel to abort.'
    );
    
    if (!confirmed) {
        return; // User cancelled
    }
    
    // Second confirmation for such a destructive action
    const doubleConfirmed = confirm(
        '🛑 FINAL WARNING!\n\n' +
        'You are about to permanently delete all detection images. This cannot be undone!\n\n' +
        'Click OK to proceed with deletion, or Cancel to abort.'
    );
    
    if (!doubleConfirmed) {
        return; // User cancelled on second confirmation
    }
    
    // Show loading state
    const button = document.querySelector('button[onclick*="clearAllGalleryFiles"]');
    const originalText = button.innerHTML;
    button.innerHTML = '⏳ Deleting...';
    button.disabled = true;
    
    // Make API call to clear gallery
    fetch('/api/gallery/clear', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage(`✅ Successfully deleted all images! ${data.message}`, 'success');
            updateGalleryStats(); // Refresh stats
            
            // Also refresh the gallery view if it's currently open
            if (typeof refreshGallery === 'function') {
                refreshGallery();
            }
        } else {
            showMessage(`❌ Failed to clear gallery: ${data.error || 'Unknown error'}`, 'error');
        }
    })
    .catch(error => {
        console.error('Error clearing gallery:', error);
        showMessage('❌ Error clearing gallery: ' + error, 'error');
    })
    .finally(() => {
        // Restore button state
        button.innerHTML = originalText;
        button.disabled = false;
    });
}

// Placeholder functions for other system settings buttons
function saveSettings() {
    showMessage('💾 Settings saved successfully', 'success');
}

function resetSettings() {
    if (confirm('Are you sure you want to reset all settings to defaults?')) {
        showMessage('🔄 Settings reset to defaults', 'info');
    }
}

function exportConfig() {
    showMessage('📤 Config export feature coming soon', 'info');
}

function restartSystem() {
    if (confirm('Are you sure you want to restart the UFO Tracker system?')) {
        showMessage('🔄 System restart initiated...', 'warning');
    }
}

// Update gallery stats when settings section is shown
function updateSettingsSection() {
    updateGalleryStats();
}

// Override the showSection function to update stats when settings is shown
const originalShowSection = window.showSection;
if (originalShowSection) {
    window.showSection = function(sectionId) {
        originalShowSection(sectionId);
        if (sectionId === 'settings') {
            setTimeout(updateSettingsSection, 100);
        }
    };
}