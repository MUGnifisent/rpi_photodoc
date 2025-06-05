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
            contrast_enabled: document.getElementById('contrast-enabled').checked,
            sharpen_enabled: document.getElementById('sharpen-enabled').checked,
            color_correction_enabled: document.getElementById('color-correction-enabled').checked,
            camera_optimal_settings: document.getElementById('camera-optimal-settings').checked
        };
    } else if (category === 'ocr') {
        settings = {
            preferred_mode: document.getElementById('ocr-preferred-mode').value
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

// Show advanced settings (placeholder for future implementation)
function showAdvancedSettings() {
    showNotification('Advanced settings will be available in a future update', 'info');
}
