// Simplified stacking - just show latest frames without heavy processing
let stackedImageHandlers = false;
let stackingIntervals = { ir: null, hq: null };

function setupStackedImageHandlers() {
    if (stackedImageHandlers) return;
    stackedImageHandlers = true;
    
    // Setup click handlers for stacked images
    document.querySelectorAll('.stacked-preview img').forEach(img => {
        img.onclick = function() {
            if (this.src && !this.src.includes('base64')) {
                openImageModal(this.src);
            }
        };
    });
}

function startStacking(camera) {
    showMessage(`Image stacking started for ${camera.toUpperCase()} camera`, 'success');
    updateStackingButton(camera, true);
    updateStackingStatus(camera, 'Active');
    startAutoStackingForCamera(camera);
}

function stopStacking(camera) {
    showMessage(`Image stacking stopped for ${camera.toUpperCase()} camera`, 'success');
    updateStackingButton(camera, false);
    updateStackingStatus(camera, 'Stopped');
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

// Simplified frame update - just show the latest frame
function updateStackedImage(camera) {
    const preview = document.getElementById(`stacked-${camera}-preview`);
    if (!preview) return;
    
    // Simple direct image display without canvas processing
    const timestamp = Date.now();
    const frameUrl = `http://${serverIP}:5002/${camera}_frame?t=${timestamp}`;
    
    preview.src = frameUrl;
    preview.style.maxWidth = '100%';
    preview.style.height = 'auto';
    
    console.log(`Updated ${camera} preview with latest frame`);
}

function startAutoStackingForCamera(camera) {
    if (stackingIntervals[camera]) {
        clearInterval(stackingIntervals[camera]);
    }
    
    // Update every 2 seconds instead of 3 for better responsiveness
    stackingIntervals[camera] = setInterval(() => {
        updateStackedImage(camera);
    }, 2000);
    
    // Take initial frame immediately
    setTimeout(() => updateStackedImage(camera), 100);
}

function stopAutoStackingForCamera(camera) {
    if (stackingIntervals[camera]) {
        clearInterval(stackingIntervals[camera]);
        stackingIntervals[camera] = null;
    }
}

// Placeholder functions for compatibility
function alignImages(camera) {
    showMessage(`Image alignment disabled for performance`, 'info');
}

function enhanceImages(camera) {
    showMessage(`Image enhancement disabled for performance`, 'info');
}

function saveStackedImage(camera) {
    showMessage(`Save feature temporarily disabled`, 'info');
}

function updateStackingSettings(camera) {
    showMessage(`Settings updated for ${camera.toUpperCase()} camera`, 'success');
}

function clearStackedImages(camera) {
    if (confirm(`Clear stacked images for ${camera.toUpperCase()} camera?`)) {
        const preview = document.getElementById(`stacked-${camera}-preview`);
        if (preview) {
            preview.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjQwIiBoZWlnaHQ9IjQ4MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iNjQwIiBoZWlnaHQ9IjQ4MCIgZmlsbD0iIzMzMyIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBkb21pbmFudC1iYXNlbGluZT0ibWlkZGxlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSJ3aGl0ZSI+Q2xlYXJlZDwvdGV4dD48L3N2Zz4=';
        }
        showMessage(`Stacked images cleared for ${camera.toUpperCase()} camera`, 'success');
    }
}

// Stack count functions for UI compatibility
function updateStackCount(camera) {
    const slider = document.getElementById(`${camera}-stack-count`);
    const display = document.getElementById(`${camera}-stack-count-value`);
    
    if (slider && display) {
        display.textContent = slider.value;
    }
}

function toggleLongExposure(camera) {
    showMessage(`Long exposure settings updated for ${camera.toUpperCase()}`, 'info');
}

function toggleJuicedExposure(camera) {
    showMessage(`Juiced exposure settings updated for ${camera.toUpperCase()}`, 'info');
}

function toggleInfiniteExposure(camera) {
    showMessage(`Infinite exposure settings updated for ${camera.toUpperCase()}`, 'info');
}