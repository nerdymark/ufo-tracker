/**
 * UFO Tracker - Client-side JavaScript
 * Handles real-time updates and user interactions
 */

class UFOTrackerViewer {
    constructor() {
        this.updateInterval = null;
        this.isConnected = false;
        this.retryCount = 0;
        this.maxRetries = 5;
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.startPeriodicUpdates();
        console.log('UFO Tracker Viewer initialized');
    }
    
    bindEvents() {
        // Handle visibility change for performance optimization
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.stopPeriodicUpdates();
            } else {
                this.startPeriodicUpdates();
            }
        });
        
        // Handle window unload
        window.addEventListener('beforeunload', () => {
            this.cleanup();
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (event) => {
            this.handleKeyboard(event);
        });
    }
    
    handleKeyboard(event) {
        // Only handle keyboard shortcuts if no input field is focused
        if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
            return;
        }
        
        switch(event.key) {
            case 'r':
            case 'R':
                event.preventDefault();
                this.refreshAll();
                break;
            case 'f':
            case 'F':
                event.preventDefault();
                this.toggleFullscreen();
                break;
            case '1':
                event.preventDefault();
                this.switchCamera('ir');
                break;
            case '2':
                event.preventDefault();
                this.switchCamera('hq');
                break;
            case 'Escape':
                event.preventDefault();
                this.exitFullscreen();
                break;
        }
    }
    
    startPeriodicUpdates() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        
        // Update every 2 seconds
        this.updateInterval = setInterval(() => {
            this.updateStatus();
        }, 2000);
        
        // Initial update
        this.updateStatus();
    }
    
    stopPeriodicUpdates() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }
    
    async updateStatus() {
        try {
            await Promise.all([
                this.updateSystemStatus(),
                this.updateDetectionStatus(),
                this.updatePanTiltStatus()
            ]);
            
            this.isConnected = true;
            this.retryCount = 0;
            this.updateConnectionStatus(true);
            
        } catch (error) {
            console.error('Error updating status:', error);
            this.handleConnectionError();
        }
    }
    
    async updateSystemStatus() {
        const response = await fetch('/api/system_status');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        this.processSystemStatus(data);
        return data;
    }
    
    async updateDetectionStatus() {
        const response = await fetch('/detection_status');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        this.processDetectionStatus(data);
        return data;
    }
    
    async updatePanTiltStatus() {
        const response = await fetch('/api/pan_tilt');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        this.processPanTiltStatus(data);
        return data;
    }
    
    processSystemStatus(data) {
        // Update camera status indicators
        this.updateStatusElement('ir-status', data.cameras?.ir_camera, 'IR Camera');
        this.updateStatusElement('hq-status', data.cameras?.hq_camera, 'HQ Camera');
        
        // Update timestamp
        const timestampElement = document.getElementById('last-update');
        if (timestampElement) {
            timestampElement.textContent = new Date().toLocaleTimeString();
        }
    }
    
    processDetectionStatus(data) {
        if (data.error) {
            console.warn('Detection status error:', data.error);
            return;
        }
        
        // Update detection statistics
        this.updateTextElement('current-detections', data.current_detections || 0);
        this.updateTextElement('total-detections', data.total_detections || 0);
        this.updateTextElement('detection-fps', (data.fps || 0).toFixed(1));
        
        // Update last detection time
        const lastDetection = data.last_detection;
        if (lastDetection) {
            const date = new Date(lastDetection);
            this.updateTextElement('last-detection', date.toLocaleTimeString());
        } else {
            this.updateTextElement('last-detection', 'Never');
        }
        
        // Update detection status indicator
        this.updateStatusElement('detection-status', data.running, 'Motion Detection');
    }
    
    processPanTiltStatus(data) {
        // Update pan-tilt status
        let statusText = 'Placeholder';
        let position = 'N/A';
        
        if (data.status === 'placeholder') {
            statusText = 'Placeholder';
        } else if (data.current_position) {
            const pan = data.current_position.pan || 0;
            const tilt = data.current_position.tilt || 0;
            position = `${pan.toFixed(1)}°, ${tilt.toFixed(1)}°`;
            statusText = data.connected ? 'Connected' : 'Disconnected';
        }
        
        // Update pan-tilt status in viewer pages
        this.updateTextElement('pantilt-position', position);
        this.updateTextElement('tracking-status', statusText);
    }
    
    updateStatusElement(elementId, status, label) {
        const element = document.getElementById(elementId);
        if (!element) return;
        
        const dot = element.querySelector('.status-dot');
        const text = element.querySelector('span:last-child');
        
        if (!dot || !text) return;
        
        // Remove all status classes
        dot.className = 'status-dot';
        
        if (status === true) {
            dot.classList.add('active');
            text.textContent = 'Active';
        } else if (status === false) {
            dot.classList.add('inactive');
            text.textContent = 'Inactive';
        } else {
            dot.classList.add('placeholder');
            text.textContent = 'Placeholder';
        }
    }
    
    updateTextElement(elementId, value) {
        const element = document.getElementById(elementId);
        if (element) {
            element.textContent = value;
        }
    }
    
    handleConnectionError() {
        this.isConnected = false;
        this.retryCount++;
        
        if (this.retryCount <= this.maxRetries) {
            console.log(`Connection error, retrying (${this.retryCount}/${this.maxRetries})...`);
            setTimeout(() => {
                this.updateStatus();
            }, 5000); // Retry after 5 seconds
        } else {
            console.error('Max retries reached, stopping automatic updates');
            this.stopPeriodicUpdates();
        }
        
        this.updateConnectionStatus(false);
    }
    
    updateConnectionStatus(connected) {
        // Update UI to reflect connection status
        const statusElements = document.querySelectorAll('.status-dot');
        statusElements.forEach(dot => {
            if (connected) {
                dot.classList.remove('loading');
            } else {
                dot.classList.add('loading');
            }
        });
        
        // Show connection status message
        if (!connected && this.retryCount > 0) {
            this.showNotification('Connection lost, retrying...', 'warning');
        } else if (connected && this.retryCount > 0) {
            this.showNotification('Connection restored', 'success');
        }
    }
    
    showNotification(message, type = 'info', duration = 3000) {
        // Create notification element if it doesn't exist
        let notification = document.getElementById('notification');
        if (!notification) {
            notification = document.createElement('div');
            notification.id = 'notification';
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 1rem 1.5rem;
                border-radius: 4px;
                color: white;
                font-weight: bold;
                z-index: 1000;
                opacity: 0;
                transition: opacity 0.3s ease;
            `;
            document.body.appendChild(notification);
        }
        
        // Set notification style based on type
        const colors = {
            info: '#3498db',
            success: '#27ae60',
            warning: '#f39c12',
            error: '#e74c3c'
        };
        
        notification.style.backgroundColor = colors[type] || colors.info;
        notification.textContent = message;
        notification.style.opacity = '1';
        
        // Auto-hide notification
        setTimeout(() => {
            notification.style.opacity = '0';
        }, duration);
    }
    
    refreshAll() {
        console.log('Refreshing all data...');
        this.updateStatus();
        this.showNotification('Data refreshed', 'success');
    }
    
    switchCamera(camera) {
        if (typeof switchCamera === 'function') {
            switchCamera(camera);
        }
    }
    
    toggleFullscreen() {
        if (typeof toggleFullscreen === 'function') {
            toggleFullscreen();
        }
    }
    
    exitFullscreen() {
        if (document.fullscreenElement) {
            document.exitFullscreen();
        }
    }
    
    cleanup() {
        this.stopPeriodicUpdates();
        console.log('UFO Tracker Viewer cleaned up');
    }
}

// Utility functions
function formatUptime(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    } else {
        return `${secs}s`;
    }
}

function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString();
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    }
}

// API helper functions
class UFOTrackerAPI {
    static async makeRequest(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
            ...options
        };
        
        try {
            const response = await fetch(url, defaultOptions);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error(`API request failed for ${url}:`, error);
            throw error;
        }
    }
    
    static async getSystemStatus() {
        return this.makeRequest('/api/system_status');
    }
    
    static async getDetectionStatus() {
        return this.makeRequest('/detection_status');
    }
    
    static async getPanTiltStatus() {
        return this.makeRequest('/api/pan_tilt');
    }
    
    static async controlPanTilt(action, data = {}) {
        return this.makeRequest('/api/pan_tilt', {
            method: 'POST',
            body: JSON.stringify({ action, ...data })
        });
    }
}

// Initialize the viewer when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.ufoTrackerViewer = new UFOTrackerViewer();
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { UFOTrackerViewer, UFOTrackerAPI };
}
