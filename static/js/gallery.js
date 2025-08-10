// Image gallery and browser functionality

// Gallery management
function refreshGallery() {
    console.log('Refreshing gallery...');
    fetch('/api/gallery/images')
    .then(response => {
        console.log('Gallery response status:', response.status);
        return response.json();
    })
    .then(data => {
        console.log('Gallery data received:', data);
        if (data.success) {
            console.log('Number of images:', data.images?.length || 0);
            displayGalleryImages(data.images || []);
            showMessage(`Gallery refreshed - ${data.images?.length || 0} images found`, 'info');
        } else {
            console.error('Gallery failed:', data.error);
            showMessage('Failed to load gallery: ' + (data.error || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        console.error('Gallery fetch error:', error);
        showMessage('Error loading gallery: ' + error, 'error');
    });
}

function displayGalleryImages(images) {
    const galleryContent = document.getElementById('gallery-content');
    if (!galleryContent) return;
    
    if (images.length === 0) {
        galleryContent.innerHTML = '<div class="no-images">No images found</div>';
        return;
    }
    
    const galleryHtml = images.map(image => {
        // For delete, just use the filename without the path
        // The server will figure out which directory it's in
        const deleteFilename = image.name;
        console.log(`Gallery item: ${image.name}, type: ${image.type}, delete will use: ${deleteFilename}`);
        
        return `
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
                <button class="btn btn-small btn-danger" onclick="deleteImage('${deleteFilename}')">
                    🗑️ Delete
                </button>
            </div>
        </div>
    `}).join('');
    
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
    console.log('Attempting to delete:', filename);
    if (confirm(`Are you sure you want to delete ${filename}?`)) {
        console.log('User confirmed deletion');
        fetch('/api/gallery/delete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ filename: filename })
        })
        .then(response => {
            console.log('Delete response status:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('Delete response data:', data);
            if (data.success) {
                showMessage(`${filename} deleted`, 'success');
                refreshGallery();
            } else {
                console.error('Delete failed:', data.error);
                showMessage('Delete failed: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(error => {
            console.error('Delete fetch error:', error);
            showMessage('Error deleting image: ' + error, 'error');
        });
    } else {
        console.log('User cancelled deletion');
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

// Filter functionality for image browser
function filterImages(type) {
    console.log(`Filtering images by type: ${type}`);
    // For now, just refresh the gallery - filtering can be implemented later
    refreshGallery();
    
    // Update filter button states
    const filterButtons = document.querySelectorAll('[id^="filter-"]');
    filterButtons.forEach(btn => {
        btn.classList.remove('active');
        btn.classList.add('btn-secondary');
        btn.classList.remove('btn-primary');
    });
    
    // Set active filter button
    const activeButton = document.getElementById(`filter-${type}`);
    if (activeButton) {
        activeButton.classList.remove('btn-secondary');
        activeButton.classList.add('btn-primary', 'active');
    }
    
    showMessage(`Showing ${type === 'all' ? 'all' : type} images`, 'info');
}