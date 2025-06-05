document.addEventListener('DOMContentLoaded', () => {
    // Handle OCR mode switching
    const ocrModeLocal = document.getElementById('ocr_mode_local');
    const ocrModeRemote = document.getElementById('ocr_mode_remote');
    const ocrServerSettings = document.getElementById('ocr-server-settings');
    
    function updateOcrSettings() {
        if (ocrModeRemote.checked) {
            ocrServerSettings.classList.add('visible');
            document.getElementById('ocr_server_url').required = true;
        } else {
            ocrServerSettings.classList.remove('visible');
            document.getElementById('ocr_server_url').required = false;
        }
    }
    
    // Set initial state
    updateOcrSettings();
    
    // Add event listeners
    ocrModeLocal.addEventListener('change', updateOcrSettings);
    ocrModeRemote.addEventListener('change', updateOcrSettings);
    
    // Handle image enhancement settings toggle
    const enhancementEnabled = document.querySelector('input[name="enhancement_enabled"]');
    const enhancementSettings = document.getElementById('enhancement-settings');
    
    function updateEnhancementSettings() {
        if (enhancementEnabled.checked) {
            enhancementSettings.style.display = 'block';
        } else {
            enhancementSettings.style.display = 'none';
        }
    }
    
    // Set initial state for enhancement settings
    updateEnhancementSettings();
    
    // Add event listener for enhancement toggle
    enhancementEnabled.addEventListener('change', updateEnhancementSettings);
    
    // Handle experimental features mutual exclusion
    const hdrEnabled = document.querySelector('input[name="experimental_hdr_enabled"]');
    const stackingEnabled = document.querySelector('input[name="experimental_stacking_enabled"]');
    
    function updateExperimentalFeatures() {
        // If HDR is enabled, disable stacking
        if (hdrEnabled && hdrEnabled.checked) {
            if (stackingEnabled) {
                stackingEnabled.checked = false;
                stackingEnabled.disabled = true;
            }
        } else if (hdrEnabled) {
            if (stackingEnabled) {
                stackingEnabled.disabled = false;
            }
        }
        
        // If stacking is enabled, disable HDR
        if (stackingEnabled && stackingEnabled.checked) {
            if (hdrEnabled) {
                hdrEnabled.checked = false;
                hdrEnabled.disabled = true;
            }
        } else if (stackingEnabled) {
            if (hdrEnabled) {
                hdrEnabled.disabled = false;
            }
        }
    }
    
    // Set initial state for experimental features
    if (hdrEnabled && stackingEnabled) {
        updateExperimentalFeatures();
        
        // Add event listeners for mutual exclusion
        hdrEnabled.addEventListener('change', updateExperimentalFeatures);
        stackingEnabled.addEventListener('change', updateExperimentalFeatures);
    }
    
    // Note: Radio and checkbox styling is now handled by CSS
    // No need for JavaScript styling functions anymore
});
