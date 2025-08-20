// Client-side motion detection and tracking
let motionDetectionActive = false;
let motionDetectionInterval = null;
let previousFrame = null;
let motionSensitivity = 40;
let detectedObjects = [];
let frameCount = 0;
let lastFPSUpdate = Date.now();
let processingFPS = 0;

// Motion detection state
const motionState = {
    ir: {
        canvas: null,
        ctx: null,
        overlayCanvas: null,
        overlayCtx: null,
        cropCanvas: null,
        cropCtx: null,
        cropOverlayCanvas: null,
        cropOverlayCtx: null,
        previousImageData: null,
        motionAreas: []
    },
    hq: {
        canvas: null,
        ctx: null,
        annotationCanvas: null,
        annotationCtx: null,
        cropCanvas: null,
        cropCtx: null,
        motionAreas: []
    }
};

// Make motionState available globally for other modules
window.motionState = motionState;

// Initialize motion detection canvases
function initializeMotionDetection() {
    // IR camera canvases
    motionState.ir.canvas = document.getElementById('ir-motion-canvas');
    motionState.ir.overlayCanvas = document.getElementById('ir-overlay-canvas');
    motionState.ir.cropCanvas = document.getElementById('ir-crop-canvas');
    motionState.ir.cropOverlayCanvas = document.getElementById('ir-crop-overlay');
    
    if (motionState.ir.canvas && motionState.ir.overlayCanvas) {
        motionState.ir.ctx = motionState.ir.canvas.getContext('2d');
        motionState.ir.overlayCtx = motionState.ir.overlayCanvas.getContext('2d');
    }
    
    if (motionState.ir.cropCanvas) {
        motionState.ir.cropCtx = motionState.ir.cropCanvas.getContext('2d');
    }
    
    if (motionState.ir.cropOverlayCanvas) {
        motionState.ir.cropOverlayCtx = motionState.ir.cropOverlayCanvas.getContext('2d');
    }
    
    // HQ camera canvases
    motionState.hq.canvas = document.getElementById('hq-main-canvas');
    motionState.hq.annotationCanvas = document.getElementById('hq-annotation-canvas');
    motionState.hq.cropCanvas = document.getElementById('hq-crop-canvas');
    
    if (motionState.hq.canvas && motionState.hq.annotationCanvas) {
        motionState.hq.ctx = motionState.hq.canvas.getContext('2d');
        motionState.hq.annotationCtx = motionState.hq.annotationCanvas.getContext('2d');
    }
    
    if (motionState.hq.cropCanvas) {
        motionState.hq.cropCtx = motionState.hq.cropCanvas.getContext('2d');
    }
    
    console.log('Motion detection canvases initialized');
}

// Start client-side motion detection
function startClientMotionDetection() {
    if (motionDetectionActive) {
        console.log('Motion detection already active');
        return;
    }
    
    console.log('Starting client-side motion detection');
    motionDetectionActive = true;
    window.motionDetectionActive = motionDetectionActive;  // Keep window object synchronized
    
    // Initialize canvases
    initializeMotionDetection();
    
    // Start detection loop
    motionDetectionInterval = setInterval(() => {
        processMotionDetection();
    }, 100); // Process every 100ms (10 FPS)
    
    // Update UI
    const statusElement = document.getElementById('tracking-enabled-status');
    if (statusElement) {
        statusElement.textContent = 'Active';
        statusElement.style.color = '#4CAF50';
    }
    
    showMessage('Motion detection started', 'success');
}

// Stop client-side motion detection
function stopClientMotionDetection() {
    if (!motionDetectionActive) {
        console.log('Motion detection not active');
        return;
    }
    
    console.log('Stopping client-side motion detection');
    motionDetectionActive = false;
    window.motionDetectionActive = motionDetectionActive;  // Keep window object synchronized
    
    // Clear detection loop
    if (motionDetectionInterval) {
        clearInterval(motionDetectionInterval);
        motionDetectionInterval = null;
    }
    
    // Clear overlays
    clearOverlays();
    
    // Update UI
    const statusElement = document.getElementById('tracking-enabled-status');
    if (statusElement) {
        statusElement.textContent = 'Inactive';
        statusElement.style.color = '#666';
    }
    
    // Reset detected objects
    detectedObjects = [];
    updateDetectionStats();
    
    showMessage('Motion detection stopped', 'info');
}

// Process motion detection for both cameras
function processMotionDetection() {
    if (!motionDetectionActive) return;
    
    // Process IR camera for motion detection
    const irImage = document.getElementById('ir-motion-feed');
    if (irImage && irImage.complete && irImage.naturalWidth > 0) {
        detectMotionInImage('ir', irImage);
    }
    
    // Update FPS counter
    frameCount++;
    const now = Date.now();
    if (now - lastFPSUpdate > 1000) {
        processingFPS = frameCount;
        frameCount = 0;
        lastFPSUpdate = now;
        
        const fpsElement = document.getElementById('ir-processing-fps');
        if (fpsElement) {
            fpsElement.textContent = processingFPS;
        }
    }
}

// Detect motion in a single image
function detectMotionInImage(camera, imageElement) {
    const state = motionState[camera];
    if (!state.canvas || !state.ctx) return;
    
    // Draw current frame to canvas
    state.ctx.drawImage(imageElement, 0, 0, state.canvas.width, state.canvas.height);
    const currentImageData = state.ctx.getImageData(0, 0, state.canvas.width, state.canvas.height);
    
    if (state.previousImageData) {
        // Calculate motion difference
        const motionAreas = calculateMotionDifference(
            state.previousImageData,
            currentImageData,
            motionSensitivity
        );
        
        // Update motion areas
        state.motionAreas = motionAreas;
        
        // Draw overlays
        if (camera === 'ir') {
            drawIROverlay(motionAreas);
        }
        
        // Annotate HQ camera based on IR motion
        if (camera === 'ir' && motionAreas.length > 0) {
            annotateHQCamera(motionAreas);
        }
        
        // Update detection statistics
        updateDetectionStats(motionAreas);
    }
    
    // Store current frame for next comparison
    state.previousImageData = currentImageData;
}

// Calculate motion difference between two frames
function calculateMotionDifference(previousData, currentData, threshold) {
    const motionAreas = [];
    const width = previousData.width;
    const height = previousData.height;
    const blockSize = 20; // Check in 20x20 pixel blocks
    
    for (let y = 0; y < height; y += blockSize) {
        for (let x = 0; x < width; x += blockSize) {
            let motionSum = 0;
            let pixelCount = 0;
            
            // Check block for motion
            for (let by = 0; by < blockSize && y + by < height; by++) {
                for (let bx = 0; bx < blockSize && x + bx < width; bx++) {
                    const idx = ((y + by) * width + (x + bx)) * 4;
                    
                    // Calculate pixel difference (using grayscale)
                    const prevGray = (previousData.data[idx] + previousData.data[idx + 1] + previousData.data[idx + 2]) / 3;
                    const currGray = (currentData.data[idx] + currentData.data[idx + 1] + currentData.data[idx + 2]) / 3;
                    const diff = Math.abs(currGray - prevGray);
                    
                    if (diff > threshold) {
                        motionSum += diff;
                        pixelCount++;
                    }
                }
            }
            
            // If significant motion in block, record it
            if (pixelCount > (blockSize * blockSize * 0.1)) { // More than 10% of pixels moved
                motionAreas.push({
                    x: x,
                    y: y,
                    width: blockSize,
                    height: blockSize,
                    intensity: motionSum / pixelCount
                });
            }
        }
    }
    
    // Merge adjacent motion areas
    return mergeMotionAreas(motionAreas);
}

// Merge adjacent motion areas into larger bounding boxes
function mergeMotionAreas(areas) {
    if (areas.length === 0) return [];
    
    const merged = [];
    const used = new Array(areas.length).fill(false);
    
    for (let i = 0; i < areas.length; i++) {
        if (used[i]) continue;
        
        let minX = areas[i].x;
        let minY = areas[i].y;
        let maxX = areas[i].x + areas[i].width;
        let maxY = areas[i].y + areas[i].height;
        let totalIntensity = areas[i].intensity;
        let count = 1;
        
        // Find all adjacent areas
        for (let j = i + 1; j < areas.length; j++) {
            if (used[j]) continue;
            
            const area = areas[j];
            // Check if areas are adjacent or overlapping
            if (!(area.x > maxX + 20 || area.x + area.width < minX - 20 ||
                  area.y > maxY + 20 || area.y + area.height < minY - 20)) {
                minX = Math.min(minX, area.x);
                minY = Math.min(minY, area.y);
                maxX = Math.max(maxX, area.x + area.width);
                maxY = Math.max(maxY, area.y + area.height);
                totalIntensity += area.intensity;
                count++;
                used[j] = true;
            }
        }
        
        merged.push({
            x: minX,
            y: minY,
            width: maxX - minX,
            height: maxY - minY,
            intensity: totalIntensity / count
        });
    }
    
    return merged;
}

// Draw overlay on IR camera
function drawIROverlay(motionAreas) {
    const ctx = motionState.ir.overlayCtx;
    if (!ctx) return;
    
    // Clear previous overlay
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    
    // Draw motion areas
    ctx.strokeStyle = '#00ff00';
    ctx.lineWidth = 2;
    ctx.fillStyle = 'rgba(0, 255, 0, 0.1)';
    
    motionAreas.forEach(area => {
        ctx.beginPath();
        ctx.rect(area.x, area.y, area.width, area.height);
        ctx.stroke();
        ctx.fill();
        
        // Draw intensity label
        ctx.fillStyle = '#00ff00';
        ctx.font = '12px monospace';
        ctx.fillText(`${Math.round(area.intensity)}`, area.x + 2, area.y - 2);
    });
    
    // Show IR zoom window for first detected object
    if (motionAreas.length > 0 && motionState.ir.cropCtx) {
        showIRCropWindow(motionAreas[0]);
    } else {
        hideIRCropWindow();
    }
}

// Annotate HQ camera based on motion
function annotateHQCamera(motionAreas) {
    const ctx = motionState.hq.annotationCtx;
    if (!ctx) return;
    
    // Clear previous annotations
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    
    // Draw motion boxes
    ctx.strokeStyle = '#ffff00';
    ctx.lineWidth = 2;
    ctx.setLineDash([5, 5]);
    
    motionAreas.forEach((area, index) => {
        ctx.beginPath();
        ctx.rect(area.x, area.y, area.width, area.height);
        ctx.stroke();
        
        // Draw label
        ctx.fillStyle = '#ffff00';
        ctx.font = 'bold 14px monospace';
        ctx.fillText(`Object ${index + 1}`, area.x + 2, area.y - 5);
    });
    
    ctx.setLineDash([]);
    
    // Update annotation count
    const annotationsElement = document.getElementById('annotations-count');
    if (annotationsElement) {
        annotationsElement.textContent = motionAreas.length;
    }
    
    // Show crop window for first detected object
    if (motionAreas.length > 0 && motionState.hq.cropCtx) {
        showCropWindow(motionAreas[0]);
    } else {
        hideCropWindow();
    }
}

// Show IR cropped zoom window with detection overlay
function showIRCropWindow(area) {
    const cropWindow = document.getElementById('ir-crop-window');
    const irImage = document.getElementById('ir-motion-feed');
    
    if (!cropWindow || !irImage || !motionState.ir.cropCtx) return;
    
    // Position crop window (opposite side of detection)
    cropWindow.style.display = 'block';
    if (area.x < 320) {  // If detection is on left half, show zoom on right
        cropWindow.style.left = 'auto';
        cropWindow.style.right = '10px';
    } else {  // If detection is on right half, show zoom on left
        cropWindow.style.left = '10px';
        cropWindow.style.right = 'auto';
    }
    cropWindow.style.top = '10px';
    
    // Draw zoomed crop
    const cropSize = 200;
    const sourceX = Math.max(0, area.x - 20);
    const sourceY = Math.max(0, area.y - 20);
    const sourceWidth = Math.min(area.width + 40, irImage.width - sourceX);
    const sourceHeight = Math.min(area.height + 40, irImage.height - sourceY);
    
    // Draw the zoomed image
    motionState.ir.cropCtx.drawImage(
        irImage,
        sourceX, sourceY, sourceWidth, sourceHeight,
        0, 0, cropSize, cropSize
    );
    
    // Draw detection overlay on zoom
    if (motionState.ir.cropOverlayCtx) {
        const ctx = motionState.ir.cropOverlayCtx;
        ctx.clearRect(0, 0, cropSize, cropSize);
        
        // Calculate scaled position of detection box
        const scaleX = cropSize / sourceWidth;
        const scaleY = cropSize / sourceHeight;
        const boxX = (area.x - sourceX) * scaleX;
        const boxY = (area.y - sourceY) * scaleY;
        const boxWidth = area.width * scaleX;
        const boxHeight = area.height * scaleY;
        
        // Draw detection box
        ctx.strokeStyle = '#00ff00';
        ctx.lineWidth = 2;
        ctx.fillStyle = 'rgba(0, 255, 0, 0.1)';
        ctx.beginPath();
        ctx.rect(boxX, boxY, boxWidth, boxHeight);
        ctx.stroke();
        ctx.fill();
        
        // Draw center crosshair
        ctx.strokeStyle = '#00ff00';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(boxX + boxWidth/2 - 10, boxY + boxHeight/2);
        ctx.lineTo(boxX + boxWidth/2 + 10, boxY + boxHeight/2);
        ctx.moveTo(boxX + boxWidth/2, boxY + boxHeight/2 - 10);
        ctx.lineTo(boxX + boxWidth/2, boxY + boxHeight/2 + 10);
        ctx.stroke();
        
        // Draw intensity label
        ctx.fillStyle = '#00ff00';
        ctx.font = 'bold 12px monospace';
        ctx.fillText(`INT: ${Math.round(area.intensity)}`, 5, 15);
    }
}

// Hide IR crop window
function hideIRCropWindow() {
    const cropWindow = document.getElementById('ir-crop-window');
    if (cropWindow) {
        cropWindow.style.display = 'none';
    }
}

// Show cropped zoom window
function showCropWindow(area) {
    const cropWindow = document.getElementById('hq-crop-window');
    const hqImage = document.getElementById('hq-motion-feed');
    
    if (!cropWindow || !hqImage || !motionState.hq.cropCtx) return;
    
    // Position crop window
    cropWindow.style.display = 'block';
    cropWindow.style.left = (area.x + area.width + 10) + 'px';
    cropWindow.style.top = area.y + 'px';
    
    // Draw zoomed crop
    const cropSize = 200;
    const sourceX = Math.max(0, area.x - 20);
    const sourceY = Math.max(0, area.y - 20);
    const sourceWidth = Math.min(area.width + 40, hqImage.width - sourceX);
    const sourceHeight = Math.min(area.height + 40, hqImage.height - sourceY);
    
    motionState.hq.cropCtx.drawImage(
        hqImage,
        sourceX, sourceY, sourceWidth, sourceHeight,
        0, 0, cropSize, cropSize
    );
    
    // Update crop status
    const cropStatusElement = document.getElementById('crop-active-status');
    if (cropStatusElement) {
        cropStatusElement.textContent = 'Yes';
        cropStatusElement.style.color = '#4CAF50';
    }
}

// Hide crop window
function hideCropWindow() {
    const cropWindow = document.getElementById('hq-crop-window');
    if (cropWindow) {
        cropWindow.style.display = 'none';
    }
    
    const cropStatusElement = document.getElementById('crop-active-status');
    if (cropStatusElement) {
        cropStatusElement.textContent = 'No';
        cropStatusElement.style.color = '#666';
    }
}

// Clear all overlays
function clearOverlays() {
    if (motionState.ir.overlayCtx) {
        motionState.ir.overlayCtx.clearRect(0, 0, 
            motionState.ir.overlayCanvas.width, 
            motionState.ir.overlayCanvas.height);
    }
    
    if (motionState.ir.cropOverlayCtx) {
        motionState.ir.cropOverlayCtx.clearRect(0, 0, 200, 200);
    }
    
    if (motionState.hq.annotationCtx) {
        motionState.hq.annotationCtx.clearRect(0, 0,
            motionState.hq.annotationCanvas.width,
            motionState.hq.annotationCanvas.height);
    }
    
    hideIRCropWindow();
    hideCropWindow();
}

// Update detection statistics
function updateDetectionStats(motionAreas = []) {
    // Update motion detected status
    const motionStatusElement = document.getElementById('motion-detected-status');
    if (motionStatusElement) {
        motionStatusElement.textContent = motionAreas.length > 0 ? 'Yes' : 'No';
        motionStatusElement.style.color = motionAreas.length > 0 ? '#4CAF50' : '#666';
    }
    
    // Update objects count
    const objectsCountElement = document.getElementById('objects-tracked-count');
    if (objectsCountElement) {
        objectsCountElement.textContent = motionAreas.length;
    }
    
    // Update motion objects count in IR panel
    const motionObjectsElement = document.getElementById('motion-objects-count');
    if (motionObjectsElement) {
        motionObjectsElement.textContent = motionAreas.length;
    }
    
    // Auto-capture if enabled and sufficient motion detected
    if (motionAreas.length >= autoCapture.threshold && autoCapture.enabled) {
        captureMotionSnapshot(motionAreas);
    }
}

// Auto-capture settings
let autoCapture = {
    enabled: false,  // Disabled by default to prevent save errors
    threshold: 2,
    lastCapture: 0,
    minInterval: 5000  // Minimum 5 seconds between captures
};

// Capture motion detection snapshot with annotations
function captureMotionSnapshot(motionAreas = [], camera = 'hq') {
    // Prevent too frequent captures
    const now = Date.now();
    if (now - autoCapture.lastCapture < autoCapture.minInterval) {
        return;
    }
    
    autoCapture.lastCapture = now;
    
    // Prepare detection info
    const detectionInfo = {
        'Processing FPS': processingFPS,
        'Sensitivity': motionSensitivity,
        'Auto Capture': autoCapture.enabled ? 'Yes' : 'No'
    };
    
    // Send to server for annotation and saving
    fetch('/api/motion/capture_with_annotations', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            camera: camera,
            motionAreas: motionAreas,
            detectionInfo: detectionInfo
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage(`Motion snapshot saved: ${data.filename}`, 'success');
            console.log(`Captured motion snapshot: ${data.filename} (${data.objects_detected} objects)`);
            
            // Refresh gallery if visible
            if (typeof refreshGallery === 'function' && document.getElementById('gallery-content')) {
                refreshGallery();
            }
        } else {
            console.error('Failed to capture motion snapshot:', data.error);
            // Only show error message if this was a manual capture (not auto-capture)
            if (!autoCapture.enabled) {
                showMessage(`Failed to capture snapshot: ${data.error}`, 'error');
            }
        }
    })
    .catch(error => {
        console.error('Error capturing motion snapshot:', error);
        // Only show error message if this was a manual capture (not auto-capture)
        if (!autoCapture.enabled) {
            showMessage('Error capturing motion snapshot', 'error');
        }
    });
}

// Manual capture function for button
function manualMotionCapture() {
    const camera = document.getElementById('motion-camera-select')?.value || 'hq';
    const currentMotionAreas = motionState.ir.motionAreas || [];
    
    captureMotionSnapshot(currentMotionAreas, camera);
}

// Hook into existing tracking functions
const originalToggleTracking = window.toggleClientAutoTracking;
window.toggleClientAutoTracking = function() {
    const btn = document.getElementById('enable-tracking-btn');
    if (!btn) return;
    
    if (btn.textContent.includes('Enable')) {
        startClientMotionDetection();
        startAutoTracker();
    } else {
        stopClientMotionDetection();
        stopAutoTracker();
    }
};

// Update sensitivity when slider changes
const originalUpdateSensitivity = window.updateSensitivity;
window.updateSensitivity = function() {
    const slider = document.getElementById('motion-sensitivity');
    if (slider) {
        motionSensitivity = parseInt(slider.value);
    }
    
    // Call original function if it exists
    if (originalUpdateSensitivity) {
        originalUpdateSensitivity();
    }
};

console.log('Motion detection module loaded');