// Utility functions and message system

// Message system
function showMessage(message, type = 'info') {
    console.log(`${type.toUpperCase()}: ${message}`);
    
    // Create message element
    const messageDiv = document.createElement('div');
    messageDiv.className = `message message-${type}`;
    messageDiv.textContent = message;
    
    // Style the message
    messageDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 16px;
        border-radius: 6px;
        color: white;
        font-weight: 500;
        z-index: 10000;
        max-width: 400px;
        word-wrap: break-word;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        transition: all 0.3s ease;
        transform: translateX(100%);
    `;
    
    // Set background color based on type
    switch (type) {
        case 'success':
            messageDiv.style.backgroundColor = '#4CAF50';
            break;
        case 'error':
            messageDiv.style.backgroundColor = '#f44336';
            break;
        case 'warning':
            messageDiv.style.backgroundColor = '#ff9800';
            break;
        case 'info':
        default:
            messageDiv.style.backgroundColor = '#2196F3';
            break;
    }
    
    // Add to page
    document.body.appendChild(messageDiv);
    
    // Animate in
    setTimeout(() => {
        messageDiv.style.transform = 'translateX(0)';
    }, 100);
    
    // Auto remove after delay
    const duration = type === 'error' ? 5000 : 3000;
    setTimeout(() => {
        messageDiv.style.transform = 'translateX(100%)';
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.parentNode.removeChild(messageDiv);
            }
        }, 300);
    }, duration);
    
    // Click to dismiss
    messageDiv.onclick = function() {
        messageDiv.style.transform = 'translateX(100%)';
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.parentNode.removeChild(messageDiv);
            }
        }, 300);
    };
}

// Utility functions
function formatTimestamp(timestamp) {
    try {
        const date = new Date(timestamp);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    } catch (e) {
        return timestamp;
    }
}

function formatDuration(seconds) {
    if (seconds < 60) {
        return `${Math.floor(seconds)}s`;
    } else if (seconds < 3600) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}m ${secs}s`;
    } else {
        const hours = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        return `${hours}h ${mins}m`;
    }
}

function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function debounce(func, wait, immediate) {
    let timeout;
    return function executedFunction() {
        const context = this;
        const args = arguments;
        
        const later = function() {
            timeout = null;
            if (!immediate) func.apply(context, args);
        };
        
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        
        if (callNow) func.apply(context, args);
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
    };
}

// Loading spinner utility
function showLoadingSpinner(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        const spinner = document.createElement('div');
        spinner.className = 'loading-spinner';
        spinner.innerHTML = '⏳';
        spinner.style.cssText = `
            display: inline-block;
            margin-left: 8px;
            animation: spin 1s linear infinite;
        `;
        element.appendChild(spinner);
    }
}

function hideLoadingSpinner(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        const spinner = element.querySelector('.loading-spinner');
        if (spinner) {
            spinner.remove();
        }
    }
}

// CSS animation for spinner
if (!document.querySelector('style[data-spinner]')) {
    const style = document.createElement('style');
    style.setAttribute('data-spinner', 'true');
    style.textContent = `
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    `;
    document.head.appendChild(style);
}

// Local storage helpers
function saveToLocalStorage(key, value) {
    try {
        localStorage.setItem(key, JSON.stringify(value));
        return true;
    } catch (e) {
        console.warn('Failed to save to localStorage:', e);
        return false;
    }
}

function loadFromLocalStorage(key, defaultValue = null) {
    try {
        const item = localStorage.getItem(key);
        return item ? JSON.parse(item) : defaultValue;
    } catch (e) {
        console.warn('Failed to load from localStorage:', e);
        return defaultValue;
    }
}

// URL parameter helpers
function getUrlParameter(name) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(name);
}

function updateUrlParameter(key, value) {
    const url = new URL(window.location);
    if (value) {
        url.searchParams.set(key, value);
    } else {
        url.searchParams.delete(key);
    }
    window.history.replaceState({}, '', url);
}

// Device detection
function isMobileDevice() {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}

function isTouchDevice() {
    return 'ontouchstart' in window || navigator.maxTouchPoints > 0;
}

// Network status
function checkNetworkStatus() {
    return fetch('/api/health', { method: 'HEAD', timeout: 5000 })
        .then(() => true)
        .catch(() => false);
}

// Browser compatibility
function isModernBrowser() {
    return !!(window.fetch && window.Promise && window.Symbol);
}

// Error handling
window.addEventListener('error', function(e) {
    console.error('Global error caught:', e.error);
    showMessage('An unexpected error occurred', 'error');
});

window.addEventListener('unhandledrejection', function(e) {
    console.error('Unhandled promise rejection:', e.reason);
    showMessage('A network or processing error occurred', 'error');
});

// Performance monitoring
function measurePerformance(name, func) {
    const start = performance.now();
    const result = func();
    const end = performance.now();
    console.log(`${name} took ${end - start} milliseconds`);
    return result;
}

// Export commonly used functions to global scope
window.showMessage = showMessage;
window.formatTimestamp = formatTimestamp;
window.formatDuration = formatDuration;
window.formatBytes = formatBytes;
window.debounce = debounce;
window.throttle = throttle;