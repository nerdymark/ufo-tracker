// Camera feed management and display

// Camera refresh and display functions
function refreshCamera(camera) {
    const img = document.getElementById(camera + '-feed');
    const previewImg = document.getElementById(camera + '-control-preview');
    
    if (img) {
        const timestamp = Date.now();
        const baseUrl = `http://${serverIP}:5001/${camera}_frame`;
        const newSrc = `${baseUrl}?t=${timestamp}`;
        
        // Create a new image to test loading
        const testImg = new Image();
        testImg.onload = function() {
            img.src = newSrc;
            if (previewImg) previewImg.src = newSrc;
        };
        testImg.onerror = function() {
            console.warn(`Failed to load ${camera} camera frame`);
        };
        testImg.src = newSrc;
    }
}

// Manual refresh buttons
function refreshIRCamera() {
    refreshCamera('ir');
    showMessage('IR camera refreshed', 'info');
}

function refreshHQCamera() {
    refreshCamera('hq');
    showMessage('HQ camera refreshed', 'info');
}

function refreshAllCameras() {
    refreshCamera('ir');
    refreshCamera('hq');
    showMessage('All cameras refreshed', 'info');
}

// Camera error handling
function handleImageError(img, camera) {
    console.error(`Error loading ${camera} camera image`);
    img.alt = `${camera.toUpperCase()} Camera - Connection Error`;
    img.style.backgroundColor = '#333';
    img.style.color = '#fff';
    img.style.display = 'flex';
    img.style.alignItems = 'center';
    img.style.justifyContent = 'center';
    img.style.fontSize = '14px';
}

// Image modal functions
function openImageModal(imageSrc) {
    const modal = document.getElementById('image-modal');
    const modalImg = document.getElementById('modal-image');
    if (modal && modalImg) {
        modal.style.display = 'flex';
        modalImg.src = imageSrc;
        document.body.style.overflow = 'hidden';
    }
}

function closeImageModal() {
    const modal = document.getElementById('image-modal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }
}

// Fullscreen image functions
function openFullscreen(camera) {
    const img = document.getElementById(camera + '-feed');
    if (img) {
        if (img.requestFullscreen) {
            img.requestFullscreen();
        } else if (img.webkitRequestFullscreen) {
            img.webkitRequestFullscreen();
        } else if (img.msRequestFullscreen) {
            img.msRequestFullscreen();
        }
        showMessage(`${camera.toUpperCase()} camera in fullscreen mode`, 'info');
    }
}

// Camera stream quality controls
function setCameraQuality(camera, quality) {
    fetch(`/api/camera_quality/${camera}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ quality: quality })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage(`${camera.toUpperCase()} quality set to ${quality}`, 'success');
            setTimeout(() => refreshCamera(camera), 1000);
        } else {
            showMessage('Quality change failed: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        showMessage('Error changing quality: ' + error, 'error');
        console.error('Quality change error:', error);
    });
}

// Camera recording controls
function startRecording(camera) {
    fetch(`/api/camera_record/${camera}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ action: 'start' })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage(`Recording started for ${camera.toUpperCase()} camera`, 'success');
            updateRecordingButton(camera, true);
        } else {
            showMessage('Recording failed: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        showMessage('Error starting recording: ' + error, 'error');
        console.error('Recording error:', error);
    });
}

function stopRecording(camera) {
    fetch(`/api/camera_record/${camera}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ action: 'stop' })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage(`Recording stopped for ${camera.toUpperCase()} camera`, 'success');
            updateRecordingButton(camera, false);
        } else {
            showMessage('Stop recording failed: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        showMessage('Error stopping recording: ' + error, 'error');
        console.error('Recording error:', error);
    });
}

function updateRecordingButton(camera, isRecording) {
    const button = document.getElementById(`${camera}-record-btn`);
    if (button) {
        if (isRecording) {
            button.innerHTML = '⏹️ Stop';
            button.classList.remove('btn-danger');
            button.classList.add('btn-warning');
            button.onclick = () => stopRecording(camera);
        } else {
            button.innerHTML = '🔴 Record';
            button.classList.remove('btn-warning');
            button.classList.add('btn-danger');
            button.onclick = () => startRecording(camera);
        }
    }
}

// Functions for the Live Streams view
function refreshStream(camera) {
    const img = document.getElementById(camera + '-live');
    if (img) {
        const originalSrc = img.src;
        img.src = '';
        setTimeout(() => {
            img.src = originalSrc + '?t=' + Date.now();
        }, 100);
        showMessage(`${camera.toUpperCase()} stream refreshed`, 'info');
    }
}

function captureFrame(camera) {
    fetch(`/api/capture_frame/${camera}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage(`Frame captured for ${camera.toUpperCase()} camera`, 'success');
            if (data.filename) {
                showMessage(`Saved as: ${data.filename}`, 'info');
            }
        } else {
            showMessage('Frame capture failed: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        showMessage('Error capturing frame: ' + error, 'error');
        console.error('Frame capture error:', error);
    });
}

function toggleFullscreen(camera) {
    const img = document.getElementById(camera + '-live') || document.getElementById(camera + '-motion-feed');
    if (img) {
        if (img.requestFullscreen) {
            img.requestFullscreen();
        } else if (img.webkitRequestFullscreen) {
            img.webkitRequestFullscreen();
        } else if (img.msRequestFullscreen) {
            img.msRequestFullscreen();
        }
        showMessage(`${camera.toUpperCase()} camera in fullscreen mode`, 'info');
    }
}

// Snapshot capture
function captureSnapshot(camera) {
    fetch(`/api/camera_snapshot/${camera}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage(`Snapshot captured for ${camera.toUpperCase()} camera`, 'success');
            if (data.filename) {
                showMessage(`Saved as: ${data.filename}`, 'info');
            }
        } else {
            showMessage('Snapshot failed: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        showMessage('Error capturing snapshot: ' + error, 'error');
        console.error('Snapshot error:', error);
    });
}