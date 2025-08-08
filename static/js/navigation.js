// Navigation and view management

let currentViewMode = 'live'; // Default view mode
let viewModes = ['live', 'autotrack', 'stacked', 'gallery']; // Available modes

// Show section and update navigation
function showSection(sectionId) {
    // Hide all sections first
    const sections = ['cameras', 'controls', 'detection', 'browser', 'autotrack', 'stacked', 'gallery'];
    sections.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.style.display = 'none';
        }
    });
    
    // Show the requested section
    const targetSection = document.getElementById(sectionId);
    if (targetSection) {
        targetSection.style.display = 'block';
    }
    
    // Update navigation tabs
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    const activeTab = document.querySelector(`.nav-tab[onclick*="${sectionId}"]`);
    if (activeTab) {
        activeTab.classList.add('active');
    }
    
    // Handle special section initialization
    if (sectionId === 'stacked') {
        setupStackedImageHandlers();
    } else if (sectionId === 'browser') {
        refreshGallery();
    }
    
    // Start/stop auto refresh based on section
    startAutoRefresh(sectionId);
}

// View mode management for camera sections
function setViewMode(mode) {
    if (!viewModes.includes(mode)) {
        console.warn('Invalid view mode:', mode);
        return;
    }
    
    currentViewMode = mode;
    
    // Hide all mode-specific content
    const modeElements = {
        'live': document.getElementById('live-cameras'),
        'autotrack': document.getElementById('autotrack-cameras'),
        'stacked': document.getElementById('stacked-cameras'),
        'gallery': document.getElementById('gallery-images')
    };
    
    Object.values(modeElements).forEach(element => {
        if (element) {
            element.style.display = 'none';
        }
    });
    
    // Show the selected mode
    const targetElement = modeElements[mode];
    if (targetElement) {
        targetElement.style.display = 'block';
    }
    
    // Update view mode buttons
    updateViewButtons();
    
    // Handle mode-specific initialization
    if (mode === 'stacked') {
        setupStackedImageHandlers();
        startAutoStacking();
    } else if (mode === 'autotrack') {
        if (typeof refreshTrackingStatus === 'function') {
            refreshTrackingStatus();
        }
    } else if (mode === 'gallery') {
        if (typeof refreshGallery === 'function') {
            refreshGallery();
        }
    }
    
    // Stop auto-stacking when leaving stacked mode
    if (currentViewMode === 'stacked' && mode !== 'stacked') {
        stopAutoStacking();
    }
    
    // Start appropriate auto refresh
    startAutoRefresh(mode);
    
    console.log('View mode changed to:', mode);
}

// Update view mode button states
function updateViewButtons() {
    const buttons = {
        'live': document.querySelector('button[onclick*="setViewMode(\'live\')"]'),
        'autotrack': document.querySelector('button[onclick*="setViewMode(\'autotrack\')"]'),
        'stacked': document.querySelector('button[onclick*="setViewMode(\'stacked\')"]'),
        'gallery': document.querySelector('button[onclick*="setViewMode(\'gallery\')"]')
    };
    
    // Remove active class from all buttons
    Object.values(buttons).forEach(button => {
        if (button) {
            button.classList.remove('btn-primary');
            button.classList.add('btn-secondary');
        }
    });
    
    // Add active class to current mode button
    const activeButton = buttons[currentViewMode];
    if (activeButton) {
        activeButton.classList.remove('btn-secondary');
        activeButton.classList.add('btn-primary');
    }
}

// Auto refresh management
function startAutoRefresh(section) {
    // Clear existing intervals
    Object.keys(autoRefreshIntervals).forEach(key => {
        if (autoRefreshIntervals[key]) {
            clearInterval(autoRefreshIntervals[key]);
            autoRefreshIntervals[key] = null;
        }
    });
    
    // Start appropriate refresh based on section
    if (section === 'live' || section === 'cameras' || section === 'stacked') {
        // Refresh camera feeds (only for static frames, not live streams)
        if (section !== 'live') {
            autoRefreshIntervals.ir = setInterval(() => refreshCamera('ir'), refreshInterval);
            autoRefreshIntervals.hq = setInterval(() => refreshCamera('hq'), refreshInterval);
        }
    } else if (section === 'autotrack') {
        // Refresh tracking status
        if (typeof refreshTrackingStatus === 'function') {
            autoRefreshIntervals.system = setInterval(refreshTrackingStatus, refreshInterval);
        }
    }
    
    console.log(`Auto refresh started for section: ${section}`);
}

// Stop all auto refresh
function stopAutoRefresh() {
    Object.keys(autoRefreshIntervals).forEach(key => {
        if (autoRefreshIntervals[key]) {
            clearInterval(autoRefreshIntervals[key]);
            autoRefreshIntervals[key] = null;
        }
    });
    console.log('Auto refresh stopped');
}

// Refresh interval controls
function setRefreshInterval(seconds) {
    refreshInterval = seconds * 1000;
    refreshIntervalDisplay();
    
    // Restart auto refresh with new interval
    if (currentViewMode) {
        startAutoRefresh(currentViewMode);
    }
}

function refreshIntervalDisplay() {
    const display = document.getElementById('refresh-interval-display');
    if (display) {
        display.textContent = `${refreshInterval / 1000}s`;
    }
}