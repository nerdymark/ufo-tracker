// Image gallery and browser functionality

// Gallery management
function refreshGallery() {
    fetch('/api/gallery/images')
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            displayGalleryImages(data.images || []);
            showMessage(`Gallery refreshed - ${data.images?.length || 0} images found`, 'info');
        } else {
            showMessage('Failed to load gallery: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        showMessage('Error loading gallery: ' + error, 'error');
        console.error('Gallery error:', error);
    });
}

function displayGalleryImages(images) {
    const galleryContent = document.getElementById('gallery-content');
    if (!galleryContent) return;
    
    if (images.length === 0) {
        galleryContent.innerHTML = '<div class="no-images">No images found</div>';
        return;
    }
    
    const galleryHtml = images.map(image => `
        <div class="gallery-item">
            <img src="${image.url}" alt="${image.name}" 
                 onclick="openImageModal('${image.url}')"
                 onerror="this.style.display='none'">
            <div class="gallery-item-info">
                <div class="gallery-item-name">${image.name}</div>
                <div class="gallery-item-date">${formatDate(image.date)}</div>
                <div class="gallery-item-size">${formatFileSize(image.size)}</div>
            </div>
            <div class="gallery-item-actions">
                <button class="btn btn-small btn-primary" onclick="downloadImage('${image.url}', '${image.name}')">
                    📥 Download
                </button>
                <button class="btn btn-small btn-danger" onclick="deleteImage('${image.name}')">
                    🗑️ Delete
                </button>
            </div>
        </div>
    `).join('');
    
    galleryContent.innerHTML = galleryHtml;
}

function formatDate(dateString) {
    try {
        const date = new Date(dateString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    } catch (e) {
        return dateString;
    }
}

function formatFileSize(bytes) {
    if (!bytes) return '0 B';
    
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function downloadImage(url, filename) {
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    showMessage(`Downloading ${filename}`, 'info');
}

function deleteImage(filename) {
    if (confirm(`Are you sure you want to delete ${filename}?`)) {
        fetch('/api/gallery/delete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ filename: filename })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showMessage(`${filename} deleted`, 'success');
                refreshGallery();
            } else {
                showMessage('Delete failed: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(error => {
            showMessage('Error deleting image: ' + error, 'error');
            console.error('Delete error:', error);
        });
    }
}

function clearGallery() {
    if (confirm('Are you sure you want to delete ALL images in the gallery?')) {
        fetch('/api/gallery/clear', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showMessage('Gallery cleared', 'success');
                refreshGallery();
            } else {
                showMessage('Clear failed: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(error => {
            showMessage('Error clearing gallery: ' + error, 'error');
            console.error('Clear error:', error);
        });
    }
}

function exportGallery() {
    fetch('/api/gallery/export')
    .then(response => {
        if (response.ok) {
            return response.blob();
        } else {
            throw new Error('Export failed');
        }
    })
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `gallery_export_${new Date().toISOString().split('T')[0]}.zip`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        showMessage('Gallery exported', 'success');
    })
    .catch(error => {
        showMessage('Error exporting gallery: ' + error, 'error');
        console.error('Export error:', error);
    });
}

// Upload functionality
function uploadImages() {
    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;
    input.accept = 'image/*';
    
    input.onchange = function(event) {
        const files = event.target.files;
        if (files.length === 0) return;
        
        const formData = new FormData();
        for (let i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }
        
        showMessage(`Uploading ${files.length} image(s)...`, 'info');
        
        fetch('/api/gallery/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showMessage(`${data.uploaded} image(s) uploaded successfully`, 'success');
                refreshGallery();
            } else {
                showMessage('Upload failed: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(error => {
            showMessage('Error uploading images: ' + error, 'error');
            console.error('Upload error:', error);
        });
    };
    
    input.click();
}