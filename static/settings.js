document.addEventListener('DOMContentLoaded', function() {
    // Tab switching functionality
    const tabs = document.querySelectorAll('.tabs li');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            const targetTab = this.getAttribute('data-tab');
            
            // Remove active class from all tabs
            tabs.forEach(t => t.classList.remove('is-active'));
            // Add active class to clicked tab
            this.classList.add('is-active');
            
            // Hide all tab contents
            tabContents.forEach(content => {
                content.style.display = 'none';
            });
            
            // Show target tab content
            const targetContent = document.getElementById(targetTab);
            if (targetContent) {
                targetContent.style.display = 'block';
            }
        });
    });
    
    // Enhancement options visibility toggle
    const enhancementEnabled = document.getElementById('enhancement-enabled');
    const enhancementOptions = document.getElementById('enhancement-options');
    
    if (enhancementEnabled && enhancementOptions) {
        enhancementEnabled.addEventListener('change', function() {
            enhancementOptions.style.display = this.checked ? 'block' : 'none';
        });
    }
    
    // Advanced settings visibility toggles
    setupAdvancedToggle('denoise-enabled', 'denoise-controls');
    setupAdvancedToggle('contrast-enabled', 'contrast-controls');
    setupAdvancedToggle('sharpen-enabled', 'sharpen-controls');
    setupAdvancedToggle('color-correction-enabled', 'color-controls');
    setupAdvancedToggle('camera-optimal-settings', 'camera-controls');
    setupAdvancedToggle('experimental-hdr-enabled', 'hdr-controls');
    setupAdvancedToggle('experimental-stacking-enabled', 'stacking-controls');
    
    // Update fine-tuning section visibility
    updateFineTuningVisibility();
    
    // Experimental features mutual exclusion
    const hdrEnabled = document.getElementById('experimental-hdr-enabled');
    const stackingEnabled = document.getElementById('experimental-stacking-enabled');
    
    if (hdrEnabled && stackingEnabled) {
        hdrEnabled.addEventListener('change', function() {
            if (this.checked) {
                stackingEnabled.checked = false;
                stackingEnabled.disabled = true;
            } else {
                stackingEnabled.disabled = false;
            }
        });
        
        stackingEnabled.addEventListener('change', function() {
            if (this.checked) {
                hdrEnabled.checked = false;
                hdrEnabled.disabled = true;
            } else {
                hdrEnabled.disabled = false;
            }
        });
        
        // Set initial state
        if (hdrEnabled.checked) {
            stackingEnabled.disabled = true;
        } else if (stackingEnabled.checked) {
            hdrEnabled.disabled = true;
        }
    }
});

// Show notification
function showNotification(message, type = 'info') {
    const placeholder = document.getElementById('notification-placeholder');
    const notification = document.createElement('div');
    notification.className = `notification is-${type} is-light`;
    notification.innerHTML = `
        <button class="delete" onclick="this.parentElement.remove();"></button>
        ${message}
    `;
    
    placeholder.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

// Save user settings for a specific category
function saveUserSettings(category) {
    const button = event.target.closest('button');
    const originalText = button.innerHTML;
    
    // Show loading state
    button.innerHTML = '<span class="icon"><i class="fas fa-spinner fa-spin"></i></span><span>Saving...</span>';
    button.disabled = true;
    
    let settings = {};
    
    if (category === 'image_enhancement') {
        settings = {
            enabled: document.getElementById('enhancement-enabled').checked,
            denoise_enabled: document.getElementById('denoise-enabled').checked,
            denoise_strength: parseInt(document.getElementById('denoise-strength').value),
            denoise_fast_mode: document.getElementById('denoise-fast-mode').checked,
            contrast_enabled: document.getElementById('contrast-enabled').checked,
            contrast_clip_limit: parseFloat(document.getElementById('contrast-clip-limit').value),
            contrast_preserve_tone: document.getElementById('contrast-preserve-tone').checked,
            sharpen_enabled: document.getElementById('sharpen-enabled').checked,
            sharpen_strength: parseFloat(document.getElementById('sharpen-strength').value),
            color_correction_enabled: document.getElementById('color-correction-enabled').checked,
            color_white_balance: document.getElementById('color-white-balance').checked,
            color_saturation_factor: parseFloat(document.getElementById('color-saturation-factor').value),
            color_temperature_adjustment: parseFloat(document.getElementById('color-temperature-adjustment').value),
            camera_optimal_settings: document.getElementById('camera-optimal-settings').checked,
            camera_exposure_time: parseInt(document.getElementById('camera-exposure-time').value),
            camera_analog_gain: parseFloat(document.getElementById('camera-analog-gain').value),
            camera_awb_mode: document.getElementById('camera-awb-mode').value,
            camera_sharpness: parseFloat(document.getElementById('camera-sharpness').value),
            experimental_hdr_enabled: document.getElementById('experimental-hdr-enabled').checked,
            experimental_hdr_exposure_times: [
                parseInt(document.getElementById('hdr-exposure-low').value),
                parseInt(document.getElementById('hdr-exposure-med').value),
                parseInt(document.getElementById('hdr-exposure-high').value)
            ],
            experimental_hdr_gamma: parseFloat(document.getElementById('hdr-gamma').value),
            experimental_stacking_enabled: document.getElementById('experimental-stacking-enabled').checked,
            experimental_stacking_num_images: parseInt(document.getElementById('stacking-num-images').value),
            experimental_stacking_alignment_threshold: parseFloat(document.getElementById('stacking-alignment-threshold').value)
        };
    } else if (category === 'ocr') {
        const languageSelect = document.getElementById('ocr-languages');
        const selectedLanguages = Array.from(languageSelect.selectedOptions).map(option => option.value);
        
        settings = {
            preferred_mode: document.getElementById('ocr-preferred-mode').value,
            languages: selectedLanguages,
            detail_level: parseInt(document.getElementById('ocr-detail-level').value),
            paragraph_mode: document.getElementById('ocr-paragraph-mode').checked
        };
    } else if (category === 'ui') {
        settings = {
            gallery_sort_order: document.getElementById('gallery-sort-order').value,
            items_per_page: parseInt(document.getElementById('items-per-page').value)
        };
    }
    
    fetch(`/settings/user/${category}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(`${category.replace('_', ' ')} settings saved successfully!`, 'success');
        } else {
            showNotification(data.message || 'Failed to save settings', 'danger');
        }
    })
    .catch(error => {
        console.error('Error saving settings:', error);
        showNotification('Error saving settings', 'danger');
    })
    .finally(() => {
        // Restore button state
        button.innerHTML = originalText;
        button.disabled = false;
    });
}

// Reset user settings to defaults
function resetUserSettings(category) {
    if (!confirm(`Are you sure you want to reset ${category.replace('_', ' ')} settings to defaults?`)) {
        return;
    }
    
    const button = event.target.closest('button');
    const originalText = button.innerHTML;
    
    // Show loading state
    button.innerHTML = '<span class="icon"><i class="fas fa-spinner fa-spin"></i></span><span>Resetting...</span>';
    button.disabled = true;
    
    fetch(`/settings/user/${category}/reset`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(`${category.replace('_', ' ')} settings reset to defaults!`, 'success');
            // Reload page to show updated values
            setTimeout(() => location.reload(), 1000);
        } else {
            showNotification(data.message || 'Failed to reset settings', 'danger');
        }
    })
    .catch(error => {
        console.error('Error resetting settings:', error);
        showNotification('Error resetting settings', 'danger');
    })
    .finally(() => {
        // Restore button state
        button.innerHTML = originalText;
        button.disabled = false;
    });
}

// Save system settings
function saveSystemSettings() {
    const button = event.target.closest('button');
    const originalText = button.innerHTML;
    
    // Show loading state
    button.innerHTML = '<span class="icon"><i class="fas fa-spinner fa-spin"></i></span><span>Saving...</span>';
    button.disabled = true;
    
    const settings = {
        llm_server_url: document.getElementById('llm_server_url').value,
        llm_model_name: document.getElementById('llm_model_name').value,
        ocr_mode: document.getElementById('system_ocr_mode').value,
        ocr_server_url: document.getElementById('ocr_server_url').value
    };
    
    fetch('/settings/system', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('System settings saved successfully!', 'success');
        } else {
            showNotification(data.message || 'Failed to save system settings', 'danger');
        }
    })
    .catch(error => {
        console.error('Error saving system settings:', error);
        showNotification('Error saving system settings', 'danger');
    })
    .finally(() => {
        // Restore button state
        button.innerHTML = originalText;
        button.disabled = false;
    });
}

// Helper function to setup advanced settings toggles
function setupAdvancedToggle(checkboxId, controlsId) {
    const checkbox = document.getElementById(checkboxId);
    const controls = document.getElementById(controlsId);
    
    if (checkbox && controls) {
        checkbox.addEventListener('change', function() {
            controls.style.display = this.checked ? 'block' : 'none';
            updateFineTuningVisibility();
        });
    }
}

// Update fine-tuning section visibility based on enabled features
function updateFineTuningVisibility() {
    const fineTuningSection = document.getElementById('fine-tuning-section');
    if (!fineTuningSection) return;
    
    const advancedCheckboxes = [
        'denoise-enabled',
        'contrast-enabled', 
        'sharpen-enabled',
        'color-correction-enabled',
        'camera-optimal-settings',
        'experimental-hdr-enabled',
        'experimental-stacking-enabled'
    ];
    
    const anyEnabled = advancedCheckboxes.some(id => {
        const checkbox = document.getElementById(id);
        return checkbox && checkbox.checked;
    });
    
    fineTuningSection.style.display = anyEnabled ? 'block' : 'none';
}

// Update range input value display
function updateRangeValue(rangeId, displayId) {
    const range = document.getElementById(rangeId);
    const display = document.getElementById(displayId);
    
    if (range && display) {
        display.textContent = range.value;
    }
}
