// Image stacking and processing functionality

let stackedImageHandlers = false;
let stackingBuffers = { ir: [], hq: [] };
let stackingSettings = {
    ir: { count: 5, longExposure: false, juicedExposure: false, ignoreCount: false },
    hq: { count: 5, longExposure: false, juicedExposure: false, ignoreCount: false }
};
let stackingIntervals = { ir: null, hq: null };
// Track total frames processed for proper blending
let stackingFrameCounts = { ir: 0, hq: 0 };
// Persistent canvases for long exposure mode
let longExposureCanvases = { ir: null, hq: null };

// Image stacking controls
function setupStackedImageHandlers() {
    if (stackedImageHandlers) return; // Already setup
    
    stackedImageHandlers = true;
    
    // Setup click handlers for stacked images
    document.querySelectorAll('.stacked-preview img').forEach(img => {
        img.onclick = function() {
            if (this.src && !this.src.includes('base64')) {
                openImageModal(this.src);
            }
        };
    });
    
    // Initialize display values
    updateStackCount('ir');
    updateStackCount('hq');
}

function startStacking(camera) {
    showMessage(`Image stacking started for ${camera.toUpperCase()} camera`, 'success');
    updateStackingButton(camera, true);
    updateStackingStatus(camera, 'Active');
    
    // Start auto-stacking for this camera
    startAutoStackingForCamera(camera);
}

function stopStacking(camera) {
    showMessage(`Image stacking stopped for ${camera.toUpperCase()} camera`, 'success');
    updateStackingButton(camera, false);
    updateStackingStatus(camera, 'Stopped');
    
    // Stop auto-stacking for this camera
    stopAutoStackingForCamera(camera);
}

function updateStackingButton(camera, isActive) {
    const button = document.getElementById(`${camera}-start-stacking`);
    if (button) {
        button.disabled = false;
        if (isActive) {
            button.textContent = '⏹️ Stop Stacking';
            button.classList.remove('btn-success');
            button.classList.add('btn-danger');
            button.onclick = () => stopStacking(camera);
        } else {
            button.textContent = '📚 Start Stacking';
            button.classList.remove('btn-danger');
            button.classList.add('btn-success');
            button.onclick = () => startStacking(camera);
        }
    }
}

function updateStackingStatus(camera, status) {
    const statusElement = document.getElementById(`${camera}-stacking-status`);
    if (statusElement) {
        statusElement.textContent = status;
        
        switch (status.toLowerCase()) {
            case 'active':
                statusElement.style.color = '#4CAF50';
                break;
            case 'stopped':
            case 'inactive':
                statusElement.style.color = '#666';
                break;
            case 'error':
                statusElement.style.color = '#ff6b6b';
                break;
            default:
                statusElement.style.color = '#ffa500';
        }
    }
}

// Image alignment
function alignImages(camera) {
    showMessage(`Image alignment is handled automatically during client-side stacking for ${camera.toUpperCase()} camera`, 'info');
    console.log(`Client-side alignment for ${camera} camera - no server call needed`);
    
    // Refresh stacked preview
    refreshStackedPreview(camera);
}

function refreshStackedPreview(camera) {
    const img = document.getElementById(`${camera}-stacked-preview`);
    if (img) {
        const timestamp = Date.now();
        const newSrc = `/api/stacking/preview/${camera}?t=${timestamp}`;
        
        // Test if the preview exists
        const testImg = new Image();
        testImg.onload = function() {
            img.src = newSrc;
        };
        testImg.onerror = function() {
            console.warn(`No stacked preview available for ${camera} camera`);
        };
        testImg.src = newSrc;
    }
}

// Advanced processing
function enhanceImages(camera) {
    showMessage(`Image enhancement is handled automatically during client-side stacking for ${camera.toUpperCase()} camera`, 'info');
    console.log(`Client-side enhancement for ${camera} camera - no server call needed`);
    
    // Refresh stacked preview
    refreshStackedPreview(camera);
}

function saveStackedImage(camera) {
    console.log(`Attempting to save stacked image for ${camera} camera`);
    const preview = document.getElementById(`stacked-${camera}-preview`);
    console.log('Preview element:', preview);
    
    if (!preview || !preview.src) {
        showMessage(`No stacked image available for ${camera.toUpperCase()} camera. Add some frames first.`, 'warning');
        return;
    }
    
    // Check if it's a data URL (which is what we want for stacked images)
    const isDataUrl = preview.src.startsWith('data:image');
    
    if (!isDataUrl) {
        // Not a data URL, might be a regular image URL - skip
        showMessage(`No stacked image data available for ${camera.toUpperCase()} camera.`, 'warning');
        return;
    }
    
    // The src is already a data URL from our stacking, so we can send it directly
    const dataUrl = preview.src;
    
    console.log('Sending save request to server...');
    fetch('/api/save_stack', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            camera: camera,
            image: dataUrl
        })
    })
    .then(response => {
        console.log('Save response status:', response.status);
        return response.json();
    })
    .then(data => {
        console.log('Save response data:', data);
        if (data.success) {
            showMessage(`Stacked image saved: ${data.filename}`, 'success');
            // Refresh gallery if visible
            if (document.getElementById('gallery-content')) {
                console.log('Refreshing gallery after save...');
                refreshGallery();
            }
        } else {
            console.error('Save failed:', data.error);
            showMessage(`Failed to save stacked image: ${data.error}`, 'error');
        }
    })
    .catch(error => {
        console.error('Save fetch error:', error);
        showMessage('Error saving stacked image to server', 'warning');
    });
    
    // Also create a download link
    const a = document.createElement('a');
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    a.href = dataUrl;
    a.download = `stacked_${camera}_${timestamp}.jpg`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    
    console.log(`Download initiated for stacked ${camera} image`);
}

// Stacking settings
function updateStackingSettings(camera) {
    const frameCount = document.getElementById(`${camera}-frame-count`)?.value;
    const alignmentMethod = document.getElementById(`${camera}-alignment-method`)?.value;
    const stackingMode = document.getElementById(`${camera}-stacking-mode`)?.value;
    
    const settings = {
        frame_count: parseInt(frameCount) || 10,
        alignment_method: alignmentMethod || 'feature_based',
        stacking_mode: stackingMode || 'average'
    };
    
    // Update local settings (client-side only)
    stackingSettings[camera].count = settings.frame_count;
    
    showMessage(`Stacking settings updated for ${camera.toUpperCase()} camera`, 'success');
}

// Clear stacked images
function clearStackedImages(camera) {
    if (confirm(`Clear all stacked images for ${camera.toUpperCase()} camera?`)) {
        // Clear the stacking buffer
        clearStackingBuffer(camera);
        showMessage(`Stacked images cleared for ${camera.toUpperCase()} camera`, 'success');
    }
}

// Client-side stacking functions for HTML template
function updateStackCount(camera) {
    const slider = document.getElementById(`${camera}-stack-count`);
    const display = document.getElementById(`${camera}-stack-count-value`);
    
    if (slider && display) {
        const count = parseInt(slider.value);
        display.textContent = count;
        stackingSettings[camera].count = count;
        // Stack count updated
    }
}

function toggleLongExposure(camera) {
    const checkbox = document.getElementById(`${camera}-long-exposure`);
    if (checkbox) {
        stackingSettings[camera].longExposure = checkbox.checked;
        
        if (checkbox.checked) {
            showMessage(`Long exposure mode enabled for ${camera.toUpperCase()} camera`, 'info');
        } else {
            showMessage(`Long exposure mode disabled for ${camera.toUpperCase()} camera`, 'info');
        }
    }
}

function toggleJuicedExposure(camera) {
    const checkbox = document.getElementById(`${camera}-juiced-exposure`);
    if (checkbox) {
        stackingSettings[camera].juicedExposure = checkbox.checked;
        
        if (checkbox.checked) {
            showMessage(`Juiced exposure mode enabled for ${camera.toUpperCase()} camera`, 'info');
        } else {
            showMessage(`Juiced exposure mode disabled for ${camera.toUpperCase()} camera`, 'info');
        }
    }
}

function toggleIgnoreCount(camera) {
    const checkbox = document.getElementById(`${camera}-ignore-count`);
    const slider = document.getElementById(`${camera}-stack-count`);
    
    if (checkbox) {
        stackingSettings[camera].ignoreCount = checkbox.checked;
        
        if (checkbox.checked) {
            // Disable the slider when ignoring count
            if (slider) {
                slider.disabled = true;
                slider.style.opacity = '0.5';
            }
            showMessage(`Ignore count enabled for ${camera.toUpperCase()} camera - stacking all frames`, 'info');
        } else {
            // Enable the slider when respecting count
            if (slider) {
                slider.disabled = false;
                slider.style.opacity = '1';
            }
            showMessage(`Ignore count disabled for ${camera.toUpperCase()} camera`, 'info');
        }
    }
}

function updateStackedImage(camera) {
    console.log(`Updating stacked image for ${camera} camera`);
    
    // Get current frame from frame service
    const frameUrl = `http://${serverIP}:5002/${camera}_frame?t=${Date.now()}`;
    
    fetch(frameUrl)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.blob();
        })
        .then(blob => {
            const reader = new FileReader();
            reader.onload = function(e) {
                const imageData = e.target.result;
                
                // Increment total frame count for proper blending
                stackingFrameCounts[camera]++;
                
                // Memory-efficient approach: limit buffer size more aggressively
                stackingBuffers[camera].push({
                    data: imageData,
                    timestamp: Date.now()
                });
                
                // Keep only a small rolling buffer (max 3 frames) to prevent memory issues
                const maxBufferFrames = stackingSettings[camera].ignoreCount ? 5 : 3;
                if (stackingBuffers[camera].length > maxBufferFrames) {
                    // Remove oldest frame to prevent memory accumulation
                    stackingBuffers[camera].shift();
                }
                
                // Perform client-side stacking
                performClientSideStacking(camera);
                
                // Buffer size tracking removed for cleaner output
            };
            reader.readAsDataURL(blob);
        })
        .catch(error => {
            console.error(`Error updating stacked image for ${camera}:`, error);
            showMessage(`Error updating ${camera.toUpperCase()} stacked image: ${error.message}`, 'error');
        });
}

function clearStackingBuffer(camera) {
    stackingBuffers[camera] = [];
    stackingFrameCounts[camera] = 0;
    // Clear long exposure canvas
    if (longExposureCanvases[camera]) {
        longExposureCanvases[camera] = null;
    }
    
    // Clear the preview image
    const preview = document.getElementById(`stacked-${camera}-preview`);
    if (preview) {
        preview.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTI4MCIgaGVpZ2h0PSI3MjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjEyODAiIGhlaWdodD0iNzIwIiBmaWxsPSIjMDAwIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGRvbWluYW50LWJhc2VsaW5lPSJtaWRkbGUiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZpbGw9IndoaXRlIj5TdGFja2luZyBidWZmZXIgY2xlYXJlZDwvdGV4dD48L3N2Zz4=';
    }
    
    showMessage(`Stacking buffer cleared for ${camera.toUpperCase()} camera`, 'success');
}

function performClientSideStacking(camera) {
    const buffer = stackingBuffers[camera];
    const settings = stackingSettings[camera];
    
    if (buffer.length === 0) {
        console.log(`No frames in ${camera} buffer for stacking`);
        return;
    }
    
    // Create canvas for stacking operations
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    
    // Process frames sequentially to avoid memory issues
    processFramesSequentially(camera, canvas, ctx, buffer, settings, 0);
}

function processFramesSequentially(camera, canvas, ctx, buffer, settings, frameIndex) {
    if (frameIndex >= buffer.length) {
        // All frames processed, update preview
        updateStackedPreview(camera, canvas);
        return;
    }
    
    const img = new Image();
    img.onload = function() {
        // Set canvas size based on first image
        if (frameIndex === 0) {
            canvas.width = img.width;
            canvas.height = img.height;
            
            // Clear canvas for first frame
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
        
        // Set composite mode for EVERY frame, not just the first
        if (settings.juicedExposure) {
            ctx.globalCompositeOperation = 'lighter';
            // Reduced alpha to prevent overexposure - each frame adds 30% brightness
            ctx.globalAlpha = 0.3;
        } else if (settings.longExposure) {
            ctx.globalCompositeOperation = 'lighten';
            ctx.globalAlpha = 1.0;
        } else {
            ctx.globalCompositeOperation = 'source-over';
            // Use total frame count for proper averaging, not buffer length
            const totalFrames = stackingFrameCounts[camera];
            if (settings.ignoreCount) {
                // Ignore count mode - use rolling average with buffer length
                ctx.globalAlpha = 1.0 / buffer.length;
            } else {
                // Standard mode - respect max frame count
                ctx.globalAlpha = 1.0 / Math.min(totalFrames, settings.count);
            }
        }
        
        // Draw the frame onto the canvas
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        
        // Process next frame
        processFramesSequentially(camera, canvas, ctx, buffer, settings, frameIndex + 1);
    };
    
    img.onerror = function() {
        console.error(`Failed to load image ${frameIndex} for stacking`);
        // Skip this frame and continue with next
        processFramesSequentially(camera, canvas, ctx, buffer, settings, frameIndex + 1);
    };
    
    img.src = buffer[frameIndex].data;
}

function updateStackedPreview(camera, canvas) {
    // Reset composite operation
    const ctx = canvas.getContext('2d');
    ctx.globalCompositeOperation = 'source-over';
    ctx.globalAlpha = 1.0;
    
    // Update preview image
    const preview = document.getElementById(`stacked-${camera}-preview`);
    if (preview) {
        preview.src = canvas.toDataURL('image/jpeg', 0.9);
    }
    
    // Client-side stacking completed
}

// Auto-stacking management
function startAutoStacking() {
    // Starting auto-stacking for both cameras
    
    // Clear any existing intervals
    stopAutoStacking();
    
    // Start auto-stacking for both cameras every 3 seconds
    stackingIntervals.ir = setInterval(() => {
        updateStackedImage('ir');
    }, 3000);
    
    stackingIntervals.hq = setInterval(() => {
        updateStackedImage('hq');
    }, 3000);
    
    // Take initial frames immediately
    setTimeout(() => updateStackedImage('ir'), 500);
    setTimeout(() => updateStackedImage('hq'), 1000);
    
    showMessage('Auto-stacking started for both cameras', 'info');
}

function startAutoStackingForCamera(camera) {
    // Starting auto-stacking for camera
    
    // Clear any existing interval for this camera
    if (stackingIntervals[camera]) {
        clearInterval(stackingIntervals[camera]);
    }
    
    // Start auto-stacking for this camera every 3 seconds
    stackingIntervals[camera] = setInterval(() => {
        updateStackedImage(camera);
    }, 3000);
    
    // Take initial frame immediately
    setTimeout(() => updateStackedImage(camera), 500);
}

function stopAutoStackingForCamera(camera) {
    // Stopping auto-stacking for camera
    
    if (stackingIntervals[camera]) {
        clearInterval(stackingIntervals[camera]);
        stackingIntervals[camera] = null;
    }
}

function stopAutoStacking() {
    // Stopping auto-stacking for both cameras
    
    if (stackingIntervals.ir) {
        clearInterval(stackingIntervals.ir);
        stackingIntervals.ir = null;
    }
    
    if (stackingIntervals.hq) {
        clearInterval(stackingIntervals.hq);
        stackingIntervals.hq = null;
    }
    
    // Auto-stacking stopped
}