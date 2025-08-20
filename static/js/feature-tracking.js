/**
 * Point-and-Click Feature Tracking
 * Allows users to select features on a zoomable still frame and track them with motors
 */

let featureTracking = {
    active: false,
    frameLoaded: false,
    selectedPoint: null,
    featureSelected: false,
    tracking: false,
    currentCamera: 'ir',
    canvas: null,
    ctx: null,
    image: null,
    scale: 1.0,
    offsetX: 0,
    offsetY: 0,
    isDragging: false,
    lastMousePos: { x: 0, y: 0 },
    minScale: 0.5,
    maxScale: 3.0,
    statusUpdateInterval: null
};

/**
 * Initialize feature tracking system
 */
function initializeFeatureTracking() {
    console.log('Initializing feature tracking system...');
    
    const canvas = document.getElementById('feature-tracking-canvas');
    if (!canvas) {
        console.error('Feature tracking canvas not found');
        return;
    }
    
    featureTracking.canvas = canvas;
    featureTracking.ctx = canvas.getContext('2d');
    
    // Set up event listeners
    setupFeatureTrackingEvents();
    
    // Update status periodically when tracking is active
    featureTracking.statusUpdateInterval = setInterval(() => {
        if (featureTracking.tracking) {
            updateFeatureTrackingStatus();
        }
    }, 2000);
    
    console.log('✅ Feature tracking system initialized');
}

/**
 * Set up event listeners for feature tracking
 */
function setupFeatureTrackingEvents() {
    const canvas = featureTracking.canvas;
    
    // Mouse events for panning and zooming
    canvas.addEventListener('mousedown', handleFeatureTrackingMouseDown);
    canvas.addEventListener('mousemove', handleFeatureTrackingMouseMove);
    canvas.addEventListener('mouseup', handleFeatureTrackingMouseUp);
    canvas.addEventListener('wheel', handleFeatureTrackingWheel, { passive: false });
    
    // Prevent context menu
    canvas.addEventListener('contextmenu', (e) => e.preventDefault());
    
    // Window resize
    window.addEventListener('resize', resizeFeatureTrackingCanvas);
}

/**
 * Load still frame for feature selection
 */
async function loadFeatureTrackingFrame(cameraType = 'ir') {
    try {
        showMessage('Loading frame for feature tracking...', 'info');
        
        featureTracking.currentCamera = cameraType;
        
        const response = await fetch(`/api/feature_tracker/still_frame/${cameraType}`);
        const data = await response.json();
        
        if (data.success) {
            // Create image from base64 data
            const img = new Image();
            img.onload = function() {
                featureTracking.image = img;
                featureTracking.frameLoaded = true;
                
                // Reset canvas state
                featureTracking.scale = 1.0;
                featureTracking.offsetX = 0;
                featureTracking.offsetY = 0;
                
                // Resize canvas to fit container
                resizeFeatureTrackingCanvas();
                
                // Draw the image
                drawFeatureTrackingFrame();
                
                showMessage(`Frame loaded successfully (${data.frame_shape[1]}×${data.frame_shape[0]})`, 'success');
                updateFeatureTrackingUI();
            };
            
            img.onerror = function() {
                showMessage('Error loading frame image', 'error');
            };
            
            img.src = `data:image/jpeg;base64,${data.frame_data}`;
            
        } else {
            showMessage('Failed to load frame: ' + data.error, 'error');
        }
        
    } catch (error) {
        console.error('Error loading feature tracking frame:', error);
        showMessage('Error loading frame: ' + error.message, 'error');
    }
}

/**
 * Draw the frame on canvas with current scale and offset
 */
function drawFeatureTrackingFrame() {
    if (!featureTracking.image || !featureTracking.ctx) return;
    
    const canvas = featureTracking.canvas;
    const ctx = featureTracking.ctx;
    const img = featureTracking.image;
    
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Calculate draw position and size
    const drawWidth = img.width * featureTracking.scale;
    const drawHeight = img.height * featureTracking.scale;
    const drawX = (canvas.width - drawWidth) / 2 + featureTracking.offsetX;
    const drawY = (canvas.height - drawHeight) / 2 + featureTracking.offsetY;
    
    // Draw image
    ctx.drawImage(img, drawX, drawY, drawWidth, drawHeight);
    
    // Draw selected point if exists
    if (featureTracking.selectedPoint) {
        const pointX = drawX + (featureTracking.selectedPoint.x * featureTracking.scale);
        const pointY = drawY + (featureTracking.selectedPoint.y * featureTracking.scale);
        
        // Draw crosshair
        ctx.strokeStyle = featureTracking.tracking ? '#ff0000' : '#00ff00';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(pointX - 10, pointY);
        ctx.lineTo(pointX + 10, pointY);
        ctx.moveTo(pointX, pointY - 10);
        ctx.lineTo(pointX, pointY + 10);
        ctx.stroke();
        
        // Draw circle
        ctx.beginPath();
        ctx.arc(pointX, pointY, 8, 0, 2 * Math.PI);
        ctx.stroke();
    }
    
    // Draw zoom level indicator
    ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
    ctx.fillRect(10, 10, 100, 30);
    ctx.fillStyle = '#ffffff';
    ctx.font = '14px Arial';
    ctx.fillText(`Zoom: ${(featureTracking.scale * 100).toFixed(0)}%`, 15, 30);
}

/**
 * Resize canvas to fit container
 */
function resizeFeatureTrackingCanvas() {
    const canvas = featureTracking.canvas;
    const container = canvas.parentElement;
    
    if (container) {
        canvas.width = container.clientWidth;
        canvas.height = Math.min(container.clientHeight, 600);
        
        if (featureTracking.frameLoaded) {
            drawFeatureTrackingFrame();
        }
    }
}

/**
 * Handle mouse down events
 */
function handleFeatureTrackingMouseDown(event) {
    const rect = featureTracking.canvas.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;
    
    if (event.button === 0) { // Left click
        if (event.shiftKey || event.ctrlKey) {
            // Pan mode
            featureTracking.isDragging = true;
            featureTracking.lastMousePos = { x: mouseX, y: mouseY };
        } else {
            // Feature selection mode
            selectFeatureAtPoint(mouseX, mouseY);
        }
    } else if (event.button === 2) { // Right click
        // Pan mode
        featureTracking.isDragging = true;
        featureTracking.lastMousePos = { x: mouseX, y: mouseY };
    }
}

/**
 * Handle mouse move events
 */
function handleFeatureTrackingMouseMove(event) {
    if (!featureTracking.isDragging) return;
    
    const rect = featureTracking.canvas.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;
    
    const deltaX = mouseX - featureTracking.lastMousePos.x;
    const deltaY = mouseY - featureTracking.lastMousePos.y;
    
    featureTracking.offsetX += deltaX;
    featureTracking.offsetY += deltaY;
    
    featureTracking.lastMousePos = { x: mouseX, y: mouseY };
    
    drawFeatureTrackingFrame();
}

/**
 * Handle mouse up events
 */
function handleFeatureTrackingMouseUp(event) {
    featureTracking.isDragging = false;
}

/**
 * Handle mouse wheel events for zooming
 */
function handleFeatureTrackingWheel(event) {
    event.preventDefault();
    
    const delta = event.deltaY > 0 ? -0.1 : 0.1;
    const newScale = Math.max(featureTracking.minScale, 
                             Math.min(featureTracking.maxScale, 
                                     featureTracking.scale + delta));
    
    if (newScale !== featureTracking.scale) {
        featureTracking.scale = newScale;
        drawFeatureTrackingFrame();
    }
}

/**
 * Select a feature at the specified canvas coordinates
 */
async function selectFeatureAtPoint(canvasX, canvasY) {
    if (!featureTracking.frameLoaded || !featureTracking.image) {
        showMessage('No frame loaded for feature selection', 'warning');
        return;
    }
    
    try {
        // Convert canvas coordinates to image coordinates
        const canvas = featureTracking.canvas;
        const img = featureTracking.image;
        
        const drawWidth = img.width * featureTracking.scale;
        const drawHeight = img.height * featureTracking.scale;
        const drawX = (canvas.width - drawWidth) / 2 + featureTracking.offsetX;
        const drawY = (canvas.height - drawHeight) / 2 + featureTracking.offsetY;
        
        const imageX = (canvasX - drawX) / featureTracking.scale;
        const imageY = (canvasY - drawY) / featureTracking.scale;
        
        // Check if click is within image bounds
        if (imageX < 0 || imageX >= img.width || imageY < 0 || imageY >= img.height) {
            showMessage('Please click within the image area', 'warning');
            return;
        }
        
        showMessage('Selecting feature...', 'info');
        
        const response = await fetch('/api/feature_tracker/select', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                x: Math.round(imageX),
                y: Math.round(imageY),
                camera_type: featureTracking.currentCamera
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            featureTracking.selectedPoint = {
                x: data.feature_point[0],
                y: data.feature_point[1]
            };
            featureTracking.featureSelected = true;
            
            drawFeatureTrackingFrame();
            updateFeatureTrackingUI();
            
            showMessage(`Feature selected at (${data.feature_point[0]}, ${data.feature_point[1]})`, 'success');
        } else {
            showMessage('Feature selection failed: ' + data.error, 'error');
        }
        
    } catch (error) {
        console.error('Error selecting feature:', error);
        showMessage('Error selecting feature: ' + error.message, 'error');
    }
}

/**
 * Start feature tracking
 */
async function startFeatureTracking() {
    if (!featureTracking.featureSelected) {
        showMessage('Please select a feature first', 'warning');
        return;
    }
    
    try {
        showMessage('Starting feature tracking...', 'info');
        
        const response = await fetch('/api/feature_tracker/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (data.success) {
            featureTracking.tracking = true;
            drawFeatureTrackingFrame(); // Update crosshair color
            updateFeatureTrackingUI();
            showMessage('Feature tracking started - motors will follow the selected feature', 'success');
        } else {
            showMessage('Failed to start tracking: ' + data.error, 'error');
        }
        
    } catch (error) {
        console.error('Error starting feature tracking:', error);
        showMessage('Error starting tracking: ' + error.message, 'error');
    }
}

/**
 * Stop feature tracking
 */
async function stopFeatureTracking() {
    try {
        showMessage('Stopping feature tracking...', 'info');
        
        const response = await fetch('/api/feature_tracker/stop', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (data.success) {
            featureTracking.tracking = false;
            drawFeatureTrackingFrame(); // Update crosshair color
            updateFeatureTrackingUI();
            showMessage('Feature tracking stopped', 'info');
        } else {
            showMessage('Error stopping tracking: ' + data.error, 'error');
        }
        
    } catch (error) {
        console.error('Error stopping feature tracking:', error);
        showMessage('Error stopping tracking: ' + error.message, 'error');
    }
}

/**
 * Clear feature selection
 */
async function clearFeatureSelection() {
    try {
        const response = await fetch('/api/feature_tracker/clear', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (data.success) {
            featureTracking.selectedPoint = null;
            featureTracking.featureSelected = false;
            featureTracking.tracking = false;
            
            drawFeatureTrackingFrame();
            updateFeatureTrackingUI();
            
            showMessage('Feature selection cleared', 'info');
        } else {
            showMessage('Error clearing selection: ' + data.error, 'error');
        }
        
    } catch (error) {
        console.error('Error clearing feature selection:', error);
        showMessage('Error clearing selection: ' + error.message, 'error');
    }
}

/**
 * Update feature tracking status from server
 */
async function updateFeatureTrackingStatus() {
    try {
        const response = await fetch('/api/feature_tracker/status');
        const data = await response.json();
        
        if (data.success) {
            const status = data.status;
            
            // Update local state
            featureTracking.tracking = status.tracking_active;
            featureTracking.featureSelected = status.has_selected_feature;
            
            if (status.target_point) {
                featureTracking.selectedPoint = {
                    x: status.target_point[0],
                    y: status.target_point[1]
                };
            }
            
            // Update UI
            updateFeatureTrackingUI();
            
            // Redraw if needed
            if (featureTracking.frameLoaded) {
                drawFeatureTrackingFrame();
            }
        }
        
    } catch (error) {
        console.debug('Error updating feature tracking status:', error);
    }
}

/**
 * Update the feature tracking UI elements
 */
function updateFeatureTrackingUI() {
    // Update camera selection buttons
    document.querySelectorAll('.feature-camera-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.getAttribute('data-camera') === featureTracking.currentCamera) {
            btn.classList.add('active');
        }
    });
    
    // Update control buttons
    const loadBtn = document.getElementById('load-feature-frame-btn');
    const selectBtn = document.getElementById('feature-select-status');
    const startBtn = document.getElementById('start-feature-tracking-btn');
    const stopBtn = document.getElementById('stop-feature-tracking-btn');
    const clearBtn = document.getElementById('clear-feature-selection-btn');
    
    if (loadBtn) {
        loadBtn.disabled = false;
    }
    
    if (selectBtn) {
        selectBtn.textContent = featureTracking.featureSelected ? 
            '✅ Feature Selected' : '⭕ No Feature Selected';
        selectBtn.className = 'feature-status ' + 
            (featureTracking.featureSelected ? 'status-good' : 'status-waiting');
    }
    
    if (startBtn) {
        startBtn.disabled = !featureTracking.featureSelected || featureTracking.tracking;
        startBtn.textContent = featureTracking.tracking ? '🔴 Tracking Active' : '▶️ Start Tracking';
        startBtn.className = featureTracking.tracking ? 
            'btn btn-danger' : 'btn btn-success';
    }
    
    if (stopBtn) {
        stopBtn.disabled = !featureTracking.tracking;
        stopBtn.style.display = featureTracking.tracking ? 'inline-block' : 'none';
    }
    
    if (clearBtn) {
        clearBtn.disabled = !featureTracking.featureSelected;
    }
    
    // Update instructions
    const instructions = document.getElementById('feature-tracking-instructions');
    if (instructions) {
        if (!featureTracking.frameLoaded) {
            instructions.innerHTML = `
                <p>📷 <strong>Step 1:</strong> Load a still frame from IR or HQ camera</p>
                <p>🎯 <strong>Step 2:</strong> Click on a feature in the image to select it</p>
                <p>🚀 <strong>Step 3:</strong> Start tracking to follow the feature with motors</p>
            `;
        } else if (!featureTracking.featureSelected) {
            instructions.innerHTML = `
                <p>🎯 <strong>Click on any feature</strong> in the image to select it for tracking</p>
                <p>💡 <strong>Tips:</strong> Hold Shift+Click or Right-click+drag to pan • Scroll to zoom</p>
            `;
        } else if (!featureTracking.tracking) {
            instructions.innerHTML = `
                <p>✅ <strong>Feature selected!</strong> Click "Start Tracking" to begin motor tracking</p>
                <p>🔄 The motors will automatically move to keep the feature centered</p>
            `;
        } else {
            instructions.innerHTML = `
                <p>🔴 <strong>Active tracking!</strong> Motors are following the selected feature</p>
                <p>🌐 <strong>You can now navigate to other pages</strong> - tracking continues in background</p>
            `;
        }
    }
}

/**
 * Toggle feature tracking (unified start/stop button)
 */
async function toggleFeatureTracking() {
    if (featureTracking.tracking) {
        await stopFeatureTracking();
    } else {
        await startFeatureTracking();
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize if the feature tracking container exists
    if (document.getElementById('feature-tracking-container')) {
        setTimeout(() => {
            initializeFeatureTracking();
            updateFeatureTrackingUI();
        }, 1000);
    }
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (featureTracking.statusUpdateInterval) {
        clearInterval(featureTracking.statusUpdateInterval);
    }
});

console.log('Feature Tracking JavaScript loaded');