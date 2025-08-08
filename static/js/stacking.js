// Image stacking and processing functionality

let stackedImageHandlers = false;
let stackingBuffers = { ir: [], hq: [] };
let stackingSettings = {
    ir: { count: 5, longExposure: false, infiniteExposure: false },
    hq: { count: 5, longExposure: false, infiniteExposure: false }
};
let stackingIntervals = { ir: null, hq: null };

// Image stacking controls
function setupStackedImageHandlers() {
    if (stackedImageHandlers) return; // Already setup
    
    console.log('Setting up stacked image handlers');
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
    const button = document.getElementById(`${camera}-start-stacking`);
    const status = document.getElementById(`${camera}-stacking-status`);
    
    if (button) {
        button.disabled = true;
        button.textContent = 'Starting...';
    }
    
    if (status) {
        status.textContent = 'Initializing...';
        status.style.color = '#ffa500';
    }
    
    fetch('/api/stacking/start/' + camera, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        console.log('Stacking start response:', data);
        if (data.success) {
            showMessage(`Image stacking started for ${camera.toUpperCase()} camera`, 'success');
            updateStackingButton(camera, true);
            updateStackingStatus(camera, 'Active');
        } else {
            showMessage('Stacking failed: ' + (data.error || 'Unknown error'), 'error');
            updateStackingButton(camera, false);
            updateStackingStatus(camera, 'Error');
        }
    })
    .catch(error => {
        showMessage('Error starting stacking: ' + error, 'error');
        console.error('Stacking error:', error);
        updateStackingButton(camera, false);
        updateStackingStatus(camera, 'Error');
    });
}

function stopStacking(camera) {
    const button = document.getElementById(`${camera}-start-stacking`);
    const status = document.getElementById(`${camera}-stacking-status`);
    
    if (button) {
        button.disabled = true;
        button.textContent = 'Stopping...';
    }
    
    fetch('/api/stacking/stop/' + camera, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        console.log('Stacking stop response:', data);
        if (data.success) {
            showMessage(`Image stacking stopped for ${camera.toUpperCase()} camera`, 'success');
            updateStackingButton(camera, false);
            updateStackingStatus(camera, 'Stopped');
        } else {
            showMessage('Stop stacking failed: ' + (data.error || 'Unknown error'), 'error');
            updateStackingButton(camera, false);
            updateStackingStatus(camera, 'Error');
        }
    })
    .catch(error => {
        showMessage('Error stopping stacking: ' + error, 'error');
        console.error('Stacking error:', error);
        updateStackingButton(camera, false);
        updateStackingStatus(camera, 'Error');
    });
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
    showMessage(`Starting image alignment for ${camera.toUpperCase()} camera...`, 'info');
    
    fetch('/api/alignment/start/' + camera, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        console.log('Alignment response:', data);
        if (data.success) {
            showMessage(`Image alignment completed for ${camera.toUpperCase()} camera`, 'success');
            // Refresh stacked preview if available
            refreshStackedPreview(camera);
        } else {
            showMessage('Alignment failed: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        showMessage('Error during alignment: ' + error, 'error');
        console.error('Alignment error:', error);
    });
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
    showMessage(`Starting image enhancement for ${camera.toUpperCase()} camera...`, 'info');
    
    fetch('/api/processing/enhance/' + camera, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        console.log('Enhancement response:', data);
        if (data.success) {
            showMessage(`Image enhancement completed for ${camera.toUpperCase()} camera`, 'success');
            refreshStackedPreview(camera);
        } else {
            showMessage('Enhancement failed: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        showMessage('Error during enhancement: ' + error, 'error');
        console.error('Enhancement error:', error);
    });
}

function saveStackedImage(camera) {
    const preview = document.getElementById(`stacked-${camera}-preview`);
    
    if (!preview || !preview.src || preview.src.includes('base64')) {
        // If no stacked image available, generate one first
        if (stackingBuffers[camera].length > 0) {
            performClientSideStacking(camera);
            setTimeout(() => saveStackedImage(camera), 1000); // Retry after stacking
            return;
        } else {
            showMessage(`No stacked image available for ${camera.toUpperCase()} camera. Add some frames first.`, 'warning');
            return;
        }
    }
    
    // Convert image to blob and save it
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const img = new Image();
    
    img.onload = function() {
        canvas.width = img.width;
        canvas.height = img.height;
        ctx.drawImage(img, 0, 0);
        
        canvas.toBlob(function(blob) {
            // Create download link
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
            a.href = url;
            a.download = `stacked_${camera}_${timestamp}.jpg`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            showMessage(`Stacked image downloaded for ${camera.toUpperCase()} camera`, 'success');
            console.log(`Stacked image saved for ${camera}`);
        }, 'image/jpeg', 0.9);
    };
    
    img.onerror = function() {
        showMessage(`Error accessing stacked image for ${camera.toUpperCase()} camera`, 'error');
    };
    
    img.src = preview.src;
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
    
    fetch('/api/stacking/settings/' + camera, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage(`Stacking settings updated for ${camera.toUpperCase()} camera`, 'success');
        } else {
            showMessage('Settings update failed: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        showMessage('Error updating stacking settings: ' + error, 'error');
        console.error('Stacking settings error:', error);
    });
}

// Clear stacked images
function clearStackedImages(camera) {
    if (confirm(`Clear all stacked images for ${camera.toUpperCase()} camera?`)) {
        fetch('/api/stacking/clear/' + camera, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showMessage(`Stacked images cleared for ${camera.toUpperCase()} camera`, 'success');
                // Clear preview
                const img = document.getElementById(`${camera}-stacked-preview`);
                if (img) {
                    img.src = '';
                }
            } else {
                showMessage('Clear failed: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(error => {
            showMessage('Error clearing stacked images: ' + error, 'error');
            console.error('Clear error:', error);
        });
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
        console.log(`${camera} stack count updated to:`, count);
    }
}

function toggleLongExposure(camera) {
    const checkbox = document.getElementById(`${camera}-long-exposure`);
    if (checkbox) {
        stackingSettings[camera].longExposure = checkbox.checked;
        console.log(`${camera} long exposure:`, checkbox.checked);
        
        if (checkbox.checked) {
            showMessage(`Long exposure mode enabled for ${camera.toUpperCase()} camera`, 'info');
        } else {
            showMessage(`Long exposure mode disabled for ${camera.toUpperCase()} camera`, 'info');
        }
    }
}

function toggleInfiniteExposure(camera) {
    const checkbox = document.getElementById(`${camera}-infinite-exposure`);
    if (checkbox) {
        stackingSettings[camera].infiniteExposure = checkbox.checked;
        console.log(`${camera} infinite exposure:`, checkbox.checked);
        
        if (checkbox.checked) {
            showMessage(`Infinite exposure mode enabled for ${camera.toUpperCase()} camera`, 'info');
            // Disable long exposure if infinite is enabled
            const longExposureCheckbox = document.getElementById(`${camera}-long-exposure`);
            if (longExposureCheckbox) {
                longExposureCheckbox.checked = false;
                stackingSettings[camera].longExposure = false;
            }
        } else {
            showMessage(`Infinite exposure mode disabled for ${camera.toUpperCase()} camera`, 'info');
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
                
                // Add to stacking buffer
                stackingBuffers[camera].push({
                    data: imageData,
                    timestamp: Date.now()
                });
                
                // Keep only the specified number of frames
                const maxFrames = stackingSettings[camera].count;
                if (stackingBuffers[camera].length > maxFrames) {
                    stackingBuffers[camera] = stackingBuffers[camera].slice(-maxFrames);
                }
                
                // Perform client-side stacking
                performClientSideStacking(camera);
                
                console.log(`${camera} stacking buffer size:`, stackingBuffers[camera].length);
                showMessage(`Frame added to ${camera.toUpperCase()} stacking buffer (${stackingBuffers[camera].length}/${maxFrames})`, 'info');
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
    
    // Clear the preview image
    const preview = document.getElementById(`stacked-${camera}-preview`);
    if (preview) {
        preview.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTI4MCIgaGVpZ2h0PSI3MjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjEyODAiIGhlaWdodD0iNzIwIiBmaWxsPSIjMDAwIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGRvbWluYW50LWJhc2VsaW5lPSJtaWRkbGUiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZpbGw9IndoaXRlIj5TdGFja2luZyBidWZmZXIgY2xlYXJlZDwvdGV4dD48L3N2Zz4=';
    }
    
    console.log(`${camera} stacking buffer cleared`);
    showMessage(`Stacking buffer cleared for ${camera.toUpperCase()} camera`, 'success');
}

function performClientSideStacking(camera) {
    const buffer = stackingBuffers[camera];
    const settings = stackingSettings[camera];
    
    if (buffer.length === 0) {
        console.log(`No frames in ${camera} buffer for stacking`);
        return;
    }
    
    console.log(`Performing client-side stacking for ${camera} with ${buffer.length} frames`);
    
    // Create canvas for stacking operations
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    
    // Set canvas size (will be updated when first image loads)
    canvas.width = 640;
    canvas.height = 480;
    
    // Load all images and stack them
    const images = [];
    let loadedCount = 0;
    
    buffer.forEach((frameData, index) => {
        const img = new Image();
        img.onload = function() {
            images[index] = img;
            loadedCount++;
            
            // Update canvas size based on first image
            if (index === 0) {
                canvas.width = img.width;
                canvas.height = img.height;
            }
            
            // When all images are loaded, perform stacking
            if (loadedCount === buffer.length) {
                stackImages(camera, canvas, ctx, images, settings);
            }
        };
        img.onerror = function() {
            console.error(`Failed to load image ${index} for stacking`);
            loadedCount++;
            if (loadedCount === buffer.length) {
                stackImages(camera, canvas, ctx, images.filter(Boolean), settings);
            }
        };
        img.src = frameData.data;
    });
}

function stackImages(camera, canvas, ctx, images, settings) {
    if (images.length === 0) {
        console.error('No valid images for stacking');
        return;
    }
    
    const width = canvas.width;
    const height = canvas.height;
    
    // Clear canvas
    ctx.clearRect(0, 0, width, height);
    
    if (settings.infiniteExposure) {
        // Infinite exposure: additive blending
        ctx.globalCompositeOperation = 'lighter';
        images.forEach(img => {
            ctx.drawImage(img, 0, 0, width, height);
        });
    } else if (settings.longExposure) {
        // Long exposure: maximum pixel values
        ctx.globalCompositeOperation = 'lighten';
        images.forEach(img => {
            ctx.drawImage(img, 0, 0, width, height);
        });
    } else {
        // Normal stacking: average
        ctx.globalAlpha = 1.0 / images.length;
        images.forEach(img => {
            ctx.drawImage(img, 0, 0, width, height);
        });
        ctx.globalAlpha = 1.0;
    }
    
    // Reset composite operation
    ctx.globalCompositeOperation = 'source-over';
    
    // Update preview image
    const preview = document.getElementById(`stacked-${camera}-preview`);
    if (preview) {
        preview.src = canvas.toDataURL('image/jpeg', 0.9);
    }
    
    console.log(`Client-side stacking completed for ${camera} with ${images.length} frames`);
    showMessage(`Stacked image updated for ${camera.toUpperCase()} (${images.length} frames)`, 'success');
}

// Auto-stacking management
function startAutoStacking() {
    console.log('Starting auto-stacking for IR and HQ cameras');
    
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

function stopAutoStacking() {
    if (stackingIntervals.ir) {
        clearInterval(stackingIntervals.ir);
        stackingIntervals.ir = null;
    }
    
    if (stackingIntervals.hq) {
        clearInterval(stackingIntervals.hq);
        stackingIntervals.hq = null;
    }
    
    console.log('Auto-stacking stopped');
}