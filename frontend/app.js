const API_URL = 'http://127.0.0.1:8000';

// DOM Elements
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const tabs = document.querySelectorAll('.tab');
const tabContents = document.querySelectorAll('.tab-content');

// Webcam Elements
const videoElement = document.getElementById('videoElement');
const canvasElement = document.getElementById('canvasElement');
const startCameraBtn = document.getElementById('start-camera');
const captureBtn = document.getElementById('capture-image');
let stream = null;

// State Views
const initialState = document.getElementById('initial-state');
const loadingState = document.getElementById('loading-state');
const dataState = document.getElementById('data-state');
const resultsContainer = document.getElementById('results-container');

// Results Elements
const scannedImagePreview = document.getElementById('scanned-image-preview');
const cropBadge = document.getElementById('crop-badge');
const fieldsList = document.getElementById('fields-list');
const rawTextArea = document.getElementById('raw-text-area');
const toggleRawBtn = document.getElementById('toggle-raw');
const rawTextContent = document.getElementById('raw-text-content');
const rawCaret = document.getElementById('raw-caret');
const downloadBtn = document.getElementById('download-btn');

let currentExtractedData = null;

// --- Tab Switching ---
tabs.forEach(tab => {
    tab.addEventListener('click', () => {
        // Remove active class from all
        tabs.forEach(t => t.classList.remove('active'));
        tabContents.forEach(c => c.classList.remove('active'));
        
        // Add active to clicked
        tab.classList.add('active');
        document.getElementById(tab.dataset.target).classList.add('active');
        
        // If switching away from webcam, stop it
        if (tab.dataset.target !== 'webcam-tab') {
            stopCamera();
        }
    });
});

// --- File Upload Logic ---
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
        handleFile(e.dataTransfer.files[0]);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
        handleFile(e.target.files[0]);
    }
});

function handleFile(file) {
    if (!file.type.startsWith('image/')) {
        showToast('Please upload a valid image file.', 'error');
        return;
    }
    processImage(file);
}

// --- Webcam Logic ---
startCameraBtn.addEventListener('click', async () => {
    try {
        stream = await navigator.mediaDevices.getUserMedia({ 
            video: { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1080 } } 
        });
        videoElement.srcObject = stream;
        startCameraBtn.style.display = 'none';
        captureBtn.disabled = false;
        showToast('Camera started. Align ID and capture.', 'info');
    } catch (err) {
        console.error("Error accessing camera:", err);
        showToast('Could not access camera. Please allow permissions.', 'error');
    }
});

captureBtn.addEventListener('click', () => {
    if (!stream) return;
    
    // Draw current video frame to canvas
    canvasElement.width = videoElement.videoWidth;
    canvasElement.height = videoElement.videoHeight;
    canvasElement.getContext('2d').drawImage(videoElement, 0, 0);
    
    // Convert canvas to blob
    canvasElement.toBlob((blob) => {
        const file = new File([blob], "webcam-capture.jpg", { type: "image/jpeg" });
        processImage(file);
        stopCamera();
    }, 'image/jpeg', 0.95);
});

function stopCamera() {
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
        videoElement.srcObject = null;
        stream = null;
        startCameraBtn.style.display = 'flex';
        captureBtn.disabled = true;
    }
}

// --- API Communication ---
async function processImage(file) {
    // UI Update -> Loading
    initialState.classList.add('hidden');
    dataState.classList.add('hidden');
    loadingState.classList.remove('hidden');
    resultsContainer.scrollIntoView({ behavior: 'smooth' });

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_URL}/scan`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || 'Failed to process image');
        }

        const data = await response.json();
        currentExtractedData = data;
        displayResults(data);
        showToast('Extraction successful!', 'success');
        
    } catch (error) {
        console.error('API Error:', error);
        showToast(error.message, 'error');
        // Reset view
        loadingState.classList.add('hidden');
        if (!currentExtractedData) initialState.classList.remove('hidden');
        else dataState.classList.remove('hidden');
    }
}

// --- Display Logic ---
function displayResults(data) {
    // Hide loading, show data
    loadingState.classList.add('hidden');
    dataState.classList.remove('hidden');
    
    // Image Preview
    scannedImagePreview.src = data.preview_image_base64;
    cropBadge.style.display = data.was_cropped ? 'block' : 'none';
    
    // Raw Text
    rawTextArea.value = data.raw_text || "No text detected.";
    
    // Build Fields List
    fieldsList.innerHTML = '';
    
    const fieldConfigs = [
        { key: 'name', label: 'Full Name' },
        { key: 'roll_number', label: 'ID / Roll Number' },
        { key: 'date_of_birth', label: 'Date of Birth' },
        { key: 'department', label: 'Department / Course' },
        { key: 'institution', label: 'Institution' }
    ];

    fieldConfigs.forEach(config => {
        const val = data[config.key];
        const conf = data.confidence_scores[config.key] || 0;
        
        if (val) {
            let confClass = 'conf-low';
            let confText = 'Low Confidence';
            if (conf >= 0.85) { confClass = 'conf-high'; confText = 'High Confidence'; }
            else if (conf >= 0.70) { confClass = 'conf-med'; confText = 'Medium Confidence'; }

            const html = `
                <div class="list-item">
                    <div class="item-header">
                        <span>${config.label}</span>
                        <span class="conf-badge ${confClass}" title="Score: ${(conf*100).toFixed(0)}%">
                            <i class="ph-fill ph-check-circle"></i> ${confText}
                        </span>
                    </div>
                    <div class="item-value">${val}</div>
                </div>
            `;
            fieldsList.insertAdjacentHTML('beforeend', html);
        }
    });

    if (fieldsList.innerHTML === '') {
        fieldsList.innerHTML = '<div class="text-muted text-center py-4">Could not confidently extract structured fields from this image. Check the raw text instead.</div>';
    }
}

// --- Accordion ---
toggleRawBtn.addEventListener('click', () => {
    rawTextContent.classList.toggle('expanded');
    if (rawTextContent.classList.contains('expanded')) {
        rawCaret.classList.replace('ph-caret-down', 'ph-caret-up');
    } else {
        rawCaret.classList.replace('ph-caret-up', 'ph-caret-down');
    }
});

// --- Download ---
downloadBtn.addEventListener('click', () => {
    if (!currentExtractedData) return;
    
    // Clean up base64 from download
    const toDownload = { ...currentExtractedData };
    delete toDownload.preview_image_base64;
    
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(toDownload, null, 2));
    const dt = new Date().toISOString().replace(/:/g, '-').split('.')[0];
    const el = document.createElement('a');
    el.setAttribute("href", dataStr);
    el.setAttribute("download", `id_scan_${dt}.json`);
    document.body.appendChild(el);
    el.click();
    el.remove();
});

// --- Toast System ---
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = 'ph-info';
    if (type === 'success') icon = 'ph-check-circle';
    if (type === 'error') icon = 'ph-warning-circle';

    toast.innerHTML = `<i class="ph-fill ${icon}"></i> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-in forwards';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
