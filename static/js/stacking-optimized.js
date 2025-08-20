// Optimized image stacking with minimal memory usage
// Instead of storing frames, we incrementally update a single canvas

let stackedImageHandlers = false;
let fullscreenStackingActive = false;
let fullscreenStackingImages = { ir: null, hq: null }; // Track fullscreen images
let stackingCanvases = { ir: null, hq: null };
let stackingContexts = { ir: null, hq: null };
let stackingFrameCounts = { ir: 0, hq: 0 };
let stackingSettings = {
    ir: { count: 5, longExposure: false, juicedExposure: false, infiniteExposure: false },
    hq: { count: 5, longExposure: false, juicedExposure: false, infiniteExposure: false }
};
let stackingIntervals = { ir: null, hq: null };
let tempCanvases = { ir: null, hq: null }; // For accumulation operations

// Initialize stacking canvas for a camera
function initStackingCanvas(camera) {
    if (!stackingCanvases[camera]) {
        stackingCanvases[camera] = document.createElement('canvas');
        stackingContexts[camera] = stackingCanvases[camera].getContext('2d', {
            willReadFrequently: true,
            alpha: false
        });
        
        // Create temp canvas for accumulation operations
        tempCanvases[camera] = document.createElement('canvas');
    }
    
    // Reset frame count
    stackingFrameCounts[camera] = 0;
}

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
    
    // Handle fullscreen events to ensure stacking continues
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    document.addEventListener('mozfullscreenchange', handleFullscreenChange);
    document.addEventListener('MSFullscreenChange', handleFullscreenChange);
}

function handleFullscreenChange() {
    const isFullscreen = !!(document.fullscreenElement || 
                           document.webkitFullscreenElement || 
                           document.mozFullScreenElement || 
                           document.msFullscreenElement);
    
    if (isFullscreen) {
        fullscreenStackingActive = true;
        // Ensure stacking continues during fullscreen
        for (const camera in stackingIntervals) {
            if (stackingIntervals[camera]) {
                // Restart interval to ensure it's active during fullscreen
                stopAutoStackingForCamera(camera);
                startAutoStackingForCamera(camera);
            }
        }
    } else {
        fullscreenStackingActive = false;
    }
}

function startStacking(camera) {
    showMessage(`Image stacking started for ${camera.toUpperCase()} camera`, 'success');
    updateStackingButton(camera, true);
    updateStackingStatus(camera, 'Active');
    
    // Initialize canvas if needed
    initStackingCanvas(camera);
    
    // Clear existing accumulation
    clearStackingCanvas(camera);
    
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
    // Update the preview from the current canvas
    if (stackingCanvases[camera]) {
        const preview = document.getElementById(`stacked-${camera}-preview`);
        if (preview) {
            preview.src = stackingCanvases[camera].toDataURL('image/jpeg', 0.9);
        }
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
    
    // Use the full resolution version if available, otherwise use the preview
    const dataUrl = preview.dataset.fullResolution || preview.src;
    
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
        // Clear the stacking canvas
        clearStackingCanvas(camera);
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
        stackingSettings[camera].infiniteExposure = checkbox.checked;
        
        if (checkbox.checked) {
            // Lock the slider and disable other modes
            if (slider) {
                slider.disabled = true;
                slider.style.opacity = '0.5';
            }
            
            // Disable other exposure modes
            const longExposureCheckbox = document.getElementById(`${camera}-long-exposure`);
            const juicedExposureCheckbox = document.getElementById(`${camera}-juiced-exposure`);
            if (longExposureCheckbox) {
                longExposureCheckbox.checked = false;
                stackingSettings[camera].longExposure = false;
            }
            if (juicedExposureCheckbox) {
                juicedExposureCheckbox.checked = false;
                stackingSettings[camera].juicedExposure = false;
            }
            
            // Don't clear canvas when enabling infinite mode - preserve existing stack
            showMessage(`Infinite stacking enabled for ${camera.toUpperCase()} camera - accumulating all frames`, 'info');
        } else {
            // Unlock the slider
            if (slider) {
                slider.disabled = false;
                slider.style.opacity = '1';
            }
            showMessage(`Frame count limit re-enabled for ${camera.toUpperCase()} camera`, 'info');
        }
    }
}

// Memory-efficient incremental stacking
function updateStackedImage(camera) {
    console.log(`Updating stacked image for ${camera} camera`);
    
    // Simple approach: Just display the latest frame without heavy processing
    const preview = document.getElementById(`stacked-${camera}-preview`);
    if (!preview) {
        console.error(`Preview element not found: stacked-${camera}-preview`);
        return;
    }
    
    // Get current frame using fetch (avoids CORS issues)
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
                
                // Create image from dataURL
                const img = new Image();
                img.onload = function() {
                    console.log(`Image loaded for ${camera}: naturalWidth=${img.naturalWidth}, naturalHeight=${img.naturalHeight}, width=${img.width}, height=${img.height}`);
                    
                    // Initialize canvas if needed
                    if (!stackingCanvases[camera]) {
                        initStackingCanvas(camera);
                    }
                    
                    const canvas = stackingCanvases[camera];
                    const ctx = stackingContexts[camera];
                    const settings = stackingSettings[camera];
                    const tempCanvas = tempCanvases[camera];
                    
                    // Set canvas size on first frame - ensure we use native resolution
                    if (canvas.width === 0 || canvas.height === 0 || canvas.width === 300) {  // 300 is the default canvas size
                        canvas.width = img.naturalWidth || img.width;
                        canvas.height = img.naturalHeight || img.height;
                        tempCanvas.width = canvas.width;
                        tempCanvas.height = canvas.height;
                        console.log(`Canvas initialized for ${camera}: ${canvas.width}x${canvas.height}`);
                        console.log(`Image natural size: ${img.naturalWidth}x${img.naturalHeight}`);
                        console.log(`Image size: ${img.width}x${img.height}`);
                    }
        
        const tempCtx = tempCanvas.getContext('2d');
        
        // Increment frame count
        stackingFrameCounts[camera]++;
        const frameCount = stackingFrameCounts[camera];
        
        // Handle different stacking modes
        if (settings.infiniteExposure) {
            // Infinite exposure - true light accumulation with screen blend
            if (frameCount === 1) {
                ctx.drawImage(img, 0, 0);
            } else {
                // Use screen blend mode for true light accumulation
                ctx.globalCompositeOperation = 'screen';
                ctx.globalAlpha = 0.8;  // Strong accumulation
                ctx.drawImage(img, 0, 0);
                ctx.globalAlpha = 1.0;
                ctx.globalCompositeOperation = 'source-over';
            }
            
        } else if (settings.longExposure) {
            // Long exposure - use lighten for star trails
            if (frameCount === 1) {
                ctx.drawImage(img, 0, 0);
            } else {
                // Lighten keeps the brightest pixels from each frame
                ctx.globalCompositeOperation = 'lighten';
                ctx.drawImage(img, 0, 0);
                ctx.globalCompositeOperation = 'source-over';
            }
            
        } else if (settings.juicedExposure) {
            // Juiced exposure - strong additive blending
            if (frameCount === 1) {
                ctx.drawImage(img, 0, 0);
            } else {
                ctx.globalCompositeOperation = 'lighter';
                ctx.globalAlpha = 0.6;  // Increased from 0.3 for stronger effect
                ctx.drawImage(img, 0, 0);
                ctx.globalAlpha = 1.0;
                ctx.globalCompositeOperation = 'source-over';
            }
            
        } else {
            // Standard stacking mode - respect frame count limit
            if (!settings.infiniteExposure && frameCount > settings.count) {
                // If we've exceeded the frame count, clear and start over
                clearStackingCanvas(camera);
                stackingFrameCounts[camera] = 1;
                ctx.drawImage(img, 0, 0);
            } else if (frameCount === 1) {
                // First frame
                ctx.drawImage(img, 0, 0);
            } else {
                // Average blending for standard mode
                const weight = 1.0 / frameCount;
                tempCtx.clearRect(0, 0, tempCanvas.width, tempCanvas.height);
                tempCtx.drawImage(canvas, 0, 0);
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.globalAlpha = 1 - weight;
                ctx.drawImage(tempCanvas, 0, 0);
                ctx.globalAlpha = weight;
                ctx.drawImage(img, 0, 0);
                ctx.globalAlpha = 1.0;
            }
        }
        
        // Update preview
        const preview = document.getElementById(`stacked-${camera}-preview`);
        if (preview) {
            // Create a scaled version for display
            const displayCanvas = document.createElement('canvas');
            const displayCtx = displayCanvas.getContext('2d');
            
            // Get the actual size of the preview container
            const previewContainer = preview.parentElement;
            const containerRect = previewContainer.getBoundingClientRect();
            const maxWidth = Math.floor(containerRect.width);
            const maxHeight = Math.floor(containerRect.height);
            
            // Scale to fit the entire image (preserve aspect ratio, no cropping)
            const scaleWidth = maxWidth / canvas.width;
            const scaleHeight = maxHeight / canvas.height;
            const scale = Math.min(scaleWidth, scaleHeight);  // Use smaller scale to fit entire image
            
            displayCanvas.width = canvas.width * scale;
            displayCanvas.height = canvas.height * scale;
            
            console.log(`${camera} container: ${containerRect.width}x${containerRect.height}, canvas: ${canvas.width}x${canvas.height}`);
            console.log(`${camera} scale options: width=${scaleWidth.toFixed(3)}, height=${scaleHeight.toFixed(3)}, using=${scale.toFixed(3)}`);
            console.log(`${camera} final display: ${displayCanvas.width}x${displayCanvas.height}`);
            
            console.log(`${camera} display scaling: ${canvas.width}x${canvas.height} -> ${displayCanvas.width}x${displayCanvas.height} (scale: ${scale})`);
            
            // Draw the full resolution canvas scaled down to display size
            // Source: full canvas, Destination: scaled display canvas
            displayCtx.drawImage(canvas, 0, 0, canvas.width, canvas.height, 0, 0, displayCanvas.width, displayCanvas.height);
            
            // Set the preview to the scaled version
            preview.src = displayCanvas.toDataURL('image/jpeg', 0.95);
            preview.style.width = '100%';
            preview.style.height = '100%';
            preview.style.objectFit = 'cover';
            preview.style.imageRendering = 'auto';
            preview.style.cursor = 'pointer';
            preview.dataset.fullResolution = canvas.toDataURL('image/jpeg', 0.95); // Store full res for saving
            
            // Update fullscreen image if it exists
            if (fullscreenStackingImages[camera]) {
                fullscreenStackingImages[camera].src = canvas.toDataURL('image/jpeg', 0.95);
            }
            
            // Add click handler for fullscreen
            preview.onclick = function() {
                toggleStackedFullscreen(camera);
            };
        }
        
        console.log(`Frame ${frameCount} added to ${camera} stack`);
                };
                img.src = imageData;
            };
            reader.readAsDataURL(blob);
        })
        .catch(error => {
            console.error(`Error updating stacked image for ${camera}:`, error);
            showMessage(`Error loading ${camera.toUpperCase()} frame for stacking`, 'error');
        });
}

function clearStackingCanvas(camera) {
    if (stackingCanvases[camera]) {
        const ctx = stackingContexts[camera];
        ctx.clearRect(0, 0, stackingCanvases[camera].width, stackingCanvases[camera].height);
        stackingFrameCounts[camera] = 0;
    }
    
    // Clear the preview image
    const preview = document.getElementById(`stacked-${camera}-preview`);
    if (preview) {
        // Use the futuristic SVG placeholder
        const placeholderSvg = camera === 'ir' ? 
            'PHN2ZyB3aWR0aD0iMTI4MCIgaGVpZ2h0PSI3MjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CiAgPGRlZnM+CiAgICA8bGluZWFyR3JhZGllbnQgaWQ9ImJnR3JhZDEyODAiIHgxPSIwJSIgeTE9IjAlIiB4Mj0iMTAwJSIgeTI9IjEwMCUiPgogICAgICA8c3RvcCBvZmZzZXQ9IjAlIiBzdG9wLWNvbG9yPSIjMDAxMTIyIiBzdG9wLW9wYWNpdHk9IjEiIC8+CiAgICAgIDxzdG9wIG9mZnNldD0iNTAlIiBzdG9wLWNvbG9yPSIjMDAwODE0IiBzdG9wLW9wYWNpdHk9IjEiIC8+CiAgICAgIDxzdG9wIG9mZnNldD0iMTAwJSIgc3RvcC1jb2xvcj0iIzFhMDAzMyIgc3RvcC1vcGFjaXR5PSIxIiAvPgogICAgPC9saW5lYXJHcmFkaWVudD4KICAgIDxsaW5lYXJHcmFkaWVudCBpZD0idGV4dEdyYWQxMjgwIiB4MT0iMCUiIHkxPSIwJSIgeDI9IjEwMCUiIHkyPSIwJSI+CiAgICAgIDxzdG9wIG9mZnNldD0iMCUiIHN0b3AtY29sb3I9IiMwMGZmZmYiIHN0b3Atb3BhY2l0eT0iMC44IiAvPgogICAgICA8c3RvcCBvZmZzZXQ9IjUwJSIgc3RvcC1jb2xvcj0iIzY0YzhmZiIgc3RvcC1vcGFjaXR5PSIxIiAvPgogICAgICA8c3RvcCBvZmZzZXQ9IjEwMCUiIHN0b3AtY29sb3I9IiMwMGZmZmYiIHN0b3Atb3BhY2l0eT0iMC44IiAvPgogICAgPC9saW5lYXJHcmFkaWVudD4KICAgIDxmaWx0ZXIgaWQ9Imdsb3cxMjgwIj4KICAgICAgPGZlR2F1c3NpYW5CbHVyIHN0ZERldmlhdGlvbj0iMyIgcmVzdWx0PSJjb2xvcmVkQmx1ciIvPgogICAgICA8ZmVNZXJnZT4gCiAgICAgICAgPGZlTWVyZ2VOb2RlIGluPSJjb2xvcmVkQmx1ciIvPgogICAgICAgIDxmZU1lcmdlTm9kZSBpbj0iU291cmNlR3JhcGhpYyIvPgogICAgICA8L2ZlTWVyZ2U+CiAgICA8L2ZpbHRlcj4KICAgIDxmaWx0ZXIgaWQ9InNjYW4xMjgwIj4KICAgICAgPGZlVHVyYnVsZW5jZSBiYXNlRnJlcXVlbmN5PSIwLjkiIG51bU9jdGF2ZXM9IjQiIHJlc3VsdD0ibm9pc2UiLz4KICAgICAgPGZlQ29sb3JNYXRyaXggaW49Im5vaXNlIiB0eXBlPSJzYXR1cmF0ZSIgdmFsdWVzPSIwIi8+CiAgICAgIDxmZUNvbXBvbmVudFRyYW5zZmVyPgogICAgICAgIDxmZUZ1bmNBIHR5cGU9ImRpc2NyZXRlIiB0YWJsZVZhbHVlcz0iMC41IDAuMiAwLjggMC4zIDAuMSAwLjciLz4KICAgICAgPC9mZUNvbXBvbmVudFRyYW5zZmVyPgogICAgPC9maWx0ZXI+CiAgPC9kZWZzPgogIDwhLS0gQmFja2dyb3VuZCAtLT4KICA8cmVjdCB3aWR0aD0iMTI4MCIgaGVpZ2h0PSI3MjAiIGZpbGw9InVybCgjYmdHcmFkMTI4MCkiLz4KICA8IS0tIEdyaWQgcGF0dGVybiAtLT4KICA8cGF0dGVybiBpZD0iZ3JpZDEyODAiIHdpZHRoPSI0MCIgaGVpZ2h0PSI0MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+CiAgICA8cGF0aCBkPSJNIDQwIDAgTCAwIDAgMCA0MCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMDBmZmZmIiBzdHJva2Utd2lkdGg9IjAuNSIgb3BhY2l0eT0iMC4xNSIvPgogIDwvcGF0dGVybj4KICA8cmVjdCB3aWR0aD0iMTI4MCIgaGVpZ2h0PSI3MjAiIGZpbGw9InVybCgjZ3JpZDEyODApIi8+CiAgPCEtLSBTY2FuIGxpbmVzIC0tPgogIDxyZWN0IHdpZHRoPSIxMjgwIiBoZWlnaHQ9IjcyMCIgZmlsbD0idXJsKCNzY2FuMTI4MCkiIG9wYWNpdHk9IjAuMSIvPgogIDwhLS0gQm9yZGVyIC0tPgogIDxyZWN0IHg9IjIiIHk9IjIiIHdpZHRoPSIxMjc2IiBoZWlnaHQ9IjcxNiIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMDBmZmZmIiBzdHJva2Utd2lkdGg9IjIiIG9wYWNpdHk9IjAuNiIvPgogIDwhLS0gQ29ybmVyIGFjY2VudHMgLS0+CiAgPHBhdGggZD0iTSAxMCAxMCBMIDMwIDEwIEwgMzAgMzAiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzY0YzhmZiIgc3Ryb2tlLXdpZHRoPSIzIiBvcGFjaXR5PSIwLjgiLz4KICA8cGF0aCBkPSJNIDEyNzAgMTAgTCAxMjUwIDEwIEwgMTI1MCAzMCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjNjRjOGZmIiBzdHJva2Utd2lkdGg9IjMiIG9wYWNpdHk9IjAuOCIvPgogIDxwYXRoIGQ9Ik0gMTAgNzEwIEwgMzAgNzEwIEwgMzAgNjkwIiBmaWxsPSJub25lIiBzdHJva2U9IiM2NGM4ZmYiIHN0cm9rZS13aWR0aD0iMyIgb3BhY2l0eT0iMC44Ii8+CiAgPHBhdGggZD0iTSAxMjcwIDcxMCBMIDEyNTAgNzEwIEwgMTI1MCA2OTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzY0YzhmZiIgc3Ryb2tlLXdpZHRoPSIzIiBvcGFjaXR5PSIwLjgiLz4KICA8IS0tIEljb24gLS0+CiAgPHRleHQgeD0iNjQwIiB5PSIzNDAiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZvbnQtZmFtaWx5PSJtb25vc3BhY2UiIGZvbnQtc2l6ZT0iOTAiIGZpbGw9InVybCgjdGV4dEdyYWQxMjgwKSIgZmlsdGVyPSJ1cmwoI2dsb3cxMjgwKSI+8J+TmjwvdGV4dD4KICA8IS0tIE1haW4gdGV4dCAtLT4KICA8dGV4dCB4PSI2NDAiIHk9IjM3MCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZm9udC1mYW1pbHk9IidDb3VyaWVyIE5ldycsIG1vbm9zcGFjZSIgZm9udC13ZWlnaHQ9ImJvbGQiIGZvbnQtc2l6ZT0iNDgiIGZpbGw9InVybCgjdGV4dEdyYWQxMjgwKSIgZmlsdGVyPSJ1cmwoI2dsb3cxMjgwKSI+U1RBQ0tJTkcgSVIgQ0xFQVJFRC4uLjwvdGV4dD4KICA8IS0tIFN0YXR1cyBpbmRpY2F0b3IgLS0+CiAgPGNpcmNsZSBjeD0iMTI1MCIgY3k9IjMwIiByPSI0IiBmaWxsPSIjMDBmZjAwIiBvcGFjaXR5PSIwLjgiPgogICAgPGFuaW1hdGUgYXR0cmlidXRlTmFtZT0ib3BhY2l0eSIgdmFsdWVzPSIwLjg7MC4zOzAuOCIgZHVyPSIycyIgcmVwZWF0Q291bnQ9ImluZGVmaW5pdGUiLz4KICA8L2NpcmNsZT4KICA8IS0tIExvYWRpbmcgYW5pbWF0aW9uIC0tPgogIDxyZWN0IHg9IjU5MCIgeT0iMzg1IiB3aWR0aD0iMTAwIiBoZWlnaHQ9IjQiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzAwZmZmZiIgc3Ryb2tlLXdpZHRoPSIyIiBvcGFjaXR5PSIwLjUiLz4KICA8cmVjdCB4PSI1OTAiIHk9IjM4NSIgd2lkdGg9IjIwIiBoZWlnaHQ9IjQiIGZpbGw9IiM2NGM4ZmYiPgogICAgPGFuaW1hdGVUcmFuc2Zvcm0gYXR0cmlidXRlTmFtZT0idHJhbnNmb3JtIiB0eXBlPSJ0cmFuc2xhdGUiIHZhbHVlcz0iMCwwOyA4MCwwOyAwLDAiIGR1cj0iM3MiIHJlcGVhdENvdW50PSJpbmRlZmluaXRlIi8+CiAgPC9yZWN0Pgo8L3N2Zz4=' :
            'PHN2ZyB3aWR0aD0iMTI4MCIgaGVpZ2h0PSI3MjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CiAgPGRlZnM+CiAgICA8bGluZWFyR3JhZGllbnQgaWQ9ImJnR3JhZDEyODAiIHgxPSIwJSIgeTE9IjAlIiB4Mj0iMTAwJSIgeTI9IjEwMCUiPgogICAgICA8c3RvcCBvZmZzZXQ9IjAlIiBzdG9wLWNvbG9yPSIjMDAxMTIyIiBzdG9wLW9wYWNpdHk9IjEiIC8+CiAgICAgIDxzdG9wIG9mZnNldD0iNTAlIiBzdG9wLWNvbG9yPSIjMDAwODE0IiBzdG9wLW9wYWNpdHk9IjEiIC8+CiAgICAgIDxzdG9wIG9mZnNldD0iMTAwJSIgc3RvcC1jb2xvcj0iIzFhMDAzMyIgc3RvcC1vcGFjaXR5PSIxIiAvPgogICAgPC9saW5lYXJHcmFkaWVudD4KICAgIDxsaW5lYXJHcmFkaWVudCBpZD0idGV4dEdyYWQxMjgwIiB4MT0iMCUiIHkxPSIwJSIgeDI9IjEwMCUiIHkyPSIwJSI+CiAgICAgIDxzdG9wIG9mZnNldD0iMCUiIHN0b3AtY29sb3I9IiMwMGZmZmYiIHN0b3Atb3BhY2l0eT0iMC44IiAvPgogICAgICA8c3RvcCBvZmZzZXQ9IjUwJSIgc3RvcC1jb2xvcj0iIzY0YzhmZiIgc3RvcC1vcGFjaXR5PSIxIiAvPgogICAgICA8c3RvcCBvZmZzZXQ9IjEwMCUiIHN0b3AtY29sb3I9IiMwMGZmZmYiIHN0b3Atb3BhY2l0eT0iMC44IiAvPgogICAgPC9saW5lYXJHcmFkaWVudD4KICAgIDxmaWx0ZXIgaWQ9Imdsb3cxMjgwIj4KICAgICAgPGZlR2F1c3NpYW5CbHVyIHN0ZERldmlhdGlvbj0iMyIgcmVzdWx0PSJjb2xvcmVkQmx1ciIvPgogICAgICA8ZmVNZXJnZT4gCiAgICAgICAgPGZlTWVyZ2VOb2RlIGluPSJjb2xvcmVkQmx1ciIvPgogICAgICAgIDxmZU1lcmdlTm9kZSBpbj0iU291cmNlR3JhcGhpYyIvPgogICAgICA8L2ZlTWVyZ2U+CiAgICA8L2ZpbHRlcj4KICAgIDxmaWx0ZXIgaWQ9InNjYW4xMjgwIj4KICAgICAgPGZlVHVyYnVsZW5jZSBiYXNlRnJlcXVlbmN5PSIwLjkiIG51bU9jdGF2ZXM9IjQiIHJlc3VsdD0ibm9pc2UiLz4KICAgICAgPGZlQ29sb3JNYXRyaXggaW49Im5vaXNlIiB0eXBlPSJzYXR1cmF0ZSIgdmFsdWVzPSIwIi8+CiAgICAgIDxmZUNvbXBvbmVudFRyYW5zZmVyPgogICAgICAgIDxmZUZ1bmNBIHR5cGU9ImRpc2NyZXRlIiB0YWJsZVZhbHVlcz0iMC41IDAuMiAwLjggMC4zIDAuMSAwLjciLz4KICAgICAgPC9mZUNvbXBvbmVudFRyYW5zZmVyPgogICAgPC9maWx0ZXI+CiAgPC9kZWZzPgogIDwhLS0gQmFja2dyb3VuZCAtLT4KICA8cmVjdCB3aWR0aD0iMTI4MCIgaGVpZ2h0PSI3MjAiIGZpbGw9InVybCgjYmdHcmFkMTI4MCkiLz4KICA8IS0tIEdyaWQgcGF0dGVybiAtLT4KICA8cGF0dGVybiBpZD0iZ3JpZDEyODAiIHdpZHRoPSI0MCIgaGVpZ2h0PSI0MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+CiAgICA8cGF0aCBkPSJNIDQwIDAgTCAwIDAgMCA0MCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMDBmZmZmIiBzdHJva2Utd2lkdGg9IjAuNSIgb3BhY2l0eT0iMC4xNSIvPgogIDwvcGF0dGVybj4KICA8cmVjdCB3aWR0aD0iMTI4MCIgaGVpZ2h0PSI3MjAiIGZpbGw9InVybCgjZ3JpZDEyODApIi8+CiAgPCEtLSBTY2FuIGxpbmVzIC0tPgogIDxyZWN0IHdpZHRoPSIxMjgwIiBoZWlnaHQ9IjcyMCIgZmlsbD0idXJsKCNzY2FuMTI4MCkiIG9wYWNpdHk9IjAuMSIvPgogIDwhLS0gQm9yZGVyIC0tPgogIDxyZWN0IHg9IjIiIHk9IjIiIHdpZHRoPSIxMjc2IiBoZWlnaHQ9IjcxNiIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMDBmZmZmIiBzdHJva2Utd2lkdGg9IjIiIG9wYWNpdHk9IjAuNiIvPgogIDwhLS0gQ29ybmVyIGFjY2VudHMgLS0+CiAgPHBhdGggZD0iTSAxMCAxMCBMIDMwIDEwIEwgMzAgMzAiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzY0YzhmZiIgc3Ryb2tlLXdpZHRoPSIzIiBvcGFjaXR5PSIwLjgiLz4KICA8cGF0aCBkPSJNIDEyNzAgMTAgTCAxMjUwIDEwIEwgMTI1MCAzMCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjNjRjOGZmIiBzdHJva2Utd2lkdGg9IjMiIG9wYWNpdHk9IjAuOCIvPgogIDxwYXRoIGQ9Ik0gMTAgNzEwIEwgMzAgNzEwIEwgMzAgNjkwIiBmaWxsPSJub25lIiBzdHJva2U9IiM2NGM4ZmYiIHN0cm9rZS13aWR0aD0iMyIgb3BhY2l0eT0iMC44Ii8+CiAgPHBhdGggZD0iTSAxMjcwIDcxMCBMIDEyNTAgNzEwIEwgMTI1MCA2OTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzY0YzhmZiIgc3Ryb2tlLXdpZHRoPSIzIiBvcGFjaXR5PSIwLjgiLz4KICA8IS0tIEljb24gLS0+CiAgPHRleHQgeD0iNjQwIiB5PSIzNDAiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZvbnQtZmFtaWx5PSJtb25vc3BhY2UiIGZvbnQtc2l6ZT0iOTAiIGZpbGw9InVybCgjdGV4dEdyYWQxMjgwKSIgZmlsdGVyPSJ1cmwoI2dsb3cxMjgwKSI+8J+TmjwvdGV4dD4KICA8IS0tIE1haW4gdGV4dCAtLT4KICA8dGV4dCB4PSI2NDAiIHk9IjM3MCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZm9udC1mYW1pbHk9IidDb3VyaWVyIE5ldycsIG1vbm9zcGFjZSIgZm9udC13ZWlnaHQ9ImJvbGQiIGZvbnQtc2l6ZT0iNDgiIGZpbGw9InVybCgjdGV4dEdyYWQxMjgwKSIgZmlsdGVyPSJ1cmwoI2dsb3cxMjgwKSI+U1RBQ0tJTkcgSFEgQ0xFQVJFRC4uLjwvdGV4dD4KICA8IS0tIFN0YXR1cyBpbmRpY2F0b3IgLS0+CiAgPGNpcmNsZSBjeD0iMTI1MCIgY3k9IjMwIiByPSI0IiBmaWxsPSIjMDBmZjAwIiBvcGFjaXR5PSIwLjgiPgogICAgPGFuaW1hdGUgYXR0cmlidXRlTmFtZT0ib3BhY2l0eSIgdmFsdWVzPSIwLjg7MC4zOzAuOCIgZHVyPSIycyIgcmVwZWF0Q291bnQ9ImluZGVmaW5pdGUiLz4KICA8L2NpcmNsZT4KICA8IS0tIExvYWRpbmcgYW5pbWF0aW9uIC0tPgogIDxyZWN0IHg9IjU5MCIgeT0iMzg1IiB3aWR0aD0iMTAwIiBoZWlnaHQ9IjQiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzAwZmZmZiIgc3Ryb2tlLXdpZHRoPSIyIiBvcGFjaXR5PSIwLjUiLz4KICA8cmVjdCB4PSI1OTAiIHk9IjM4NSIgd2lkdGg9IjIwIiBoZWlnaHQ9IjQiIGZpbGw9IiM2NGM4ZmYiPgogICAgPGFuaW1hdGVUcmFuc2Zvcm0gYXR0cmlidXRlTmFtZT0idHJhbnNmb3JtIiB0eXBlPSJ0cmFuc2xhdGUiIHZhbHVlcz0iMCwwOyA4MCwwOyAwLDAiIGR1cj0iM3MiIHJlcGVhdENvdW50PSJpbmRlZmluaXRlIi8+CiAgPC9yZWN0Pgo8L3N2Zz4=';
        
        preview.src = `data:image/svg+xml;base64,${placeholderSvg}`;
    }
    
    showMessage(`Stacking buffer cleared for ${camera.toUpperCase()} camera`, 'success');
}

// Fullscreen support for stacked images
function toggleStackedFullscreen(camera) {
    const preview = document.getElementById(`stacked-${camera}-preview`);
    if (!preview || !preview.dataset.fullResolution) {
        showMessage(`No stacked image available for fullscreen`, 'warning');
        return;
    }
    
    // Create a temporary image element with the full resolution data
    const fullscreenImg = document.createElement('img');
    fullscreenImg.src = preview.dataset.fullResolution;
    
    // Store reference for live updates
    fullscreenStackingImages[camera] = fullscreenImg;
    fullscreenImg.style.width = '100%';
    fullscreenImg.style.height = '100%';
    fullscreenImg.style.objectFit = 'contain';
    fullscreenImg.style.background = 'black';
    
    // Add fullscreen styles
    fullscreenImg.style.position = 'fixed';
    fullscreenImg.style.top = '0';
    fullscreenImg.style.left = '0';
    fullscreenImg.style.zIndex = '9999';
    fullscreenImg.style.cursor = 'pointer';
    
    // Add escape key handler
    const escapeHandler = function(event) {
        if (event.key === 'Escape') {
            exitStackedFullscreen();
        }
    };
    
    // Add click handler to exit
    fullscreenImg.onclick = exitStackedFullscreen;
    
    function exitStackedFullscreen() {
        document.removeEventListener('keydown', escapeHandler);
        if (fullscreenImg.parentNode) {
            fullscreenImg.parentNode.removeChild(fullscreenImg);
        }
        // Clear the reference so updates stop
        fullscreenStackingImages[camera] = null;
    }
    
    // Add to DOM and set up event listeners
    document.addEventListener('keydown', escapeHandler);
    document.body.appendChild(fullscreenImg);
    
    showMessage(`${camera.toUpperCase()} stacked image in fullscreen mode - Press ESC or click to exit`, 'info');
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

// Export the clearStackingBuffer function for global use
window.clearStackingBuffer = clearStackingCanvas;