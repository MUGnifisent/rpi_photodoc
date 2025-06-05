document.addEventListener('DOMContentLoaded', () => {
    console.log("Upload.js DOMContentLoaded event fired");
    const fileInput = document.getElementById('file-upload-input');
    const fileNameDisplay = document.getElementById('file-name-display');
    const fileSelectButton = document.getElementById('file-select-button');
    const uploadSubmitButton = document.getElementById('upload-submit-button');
    
    if (fileInput && fileNameDisplay) {
        fileInput.onchange = () => {
            if (fileInput.files.length > 0) {
                fileNameDisplay.textContent = fileInput.files[0].name;
                fileNameDisplay.classList.add('has-file');
                if (uploadSubmitButton) {
                    uploadSubmitButton.disabled = false;
                }
            } else {
                fileNameDisplay.textContent = "No file selected";
                fileNameDisplay.classList.remove('has-file');
                if (uploadSubmitButton) {
                    uploadSubmitButton.disabled = true;
                }
            }
        }
    }
    
    // Initialize submit button state
    if (uploadSubmitButton) {
        uploadSubmitButton.disabled = true;
    }

    const uploadForm = document.getElementById('upload-form');
    const uploadFormErrorPlaceholder = document.getElementById('upload-form-error-placeholder');

    if (uploadForm && uploadSubmitButton) {
        uploadForm.addEventListener('submit', (event) => {
            if (fileInput && fileInput.files.length === 0) {
                event.preventDefault();
                displayNotification('Please select a file to upload.', 'warning', uploadFormErrorPlaceholder, true);
                return;
            }
            uploadSubmitButton.classList.add('is-loading');
            uploadSubmitButton.disabled = true;
        });
    }

    function displayNotification(message, type = 'info', container, isFormError = false) {
        if (!container) {
            console.warn("Notification container not found for message:", message);
            if(!isFormError) alert(message);
            return;
        }
        let notificationDiv = container.querySelector('.notification');
        if (!notificationDiv || !isFormError) {
            if(isFormError) container.innerHTML = '';
            notificationDiv = document.createElement('div');
            notificationDiv.className = `notification is-${type} is-light is-small mb-3`;
            container.appendChild(notificationDiv);
        } else {
             notificationDiv.className = `notification is-${type} is-light is-small mb-3`;
        }
        
        notificationDiv.innerHTML = `<button class="delete is-small"></button>${message}`;
        const deleteButton = notificationDiv.querySelector('.delete');
        if (deleteButton) {
            deleteButton.addEventListener('click', () => notificationDiv.remove());
        }
    }

    const cameraSection = document.getElementById('rpi-camera-section');
    console.log("Camera section found:", !!cameraSection);
    if (cameraSection) {
        console.log("Initializing camera section...");
        console.log("API URLs available:", window.apiUrls);
        const cameraFeedImg = document.getElementById('camera-feed-img');
        const cameraFeedContainer = document.getElementById('camera-feed-container');
        const cameraLoadingOverlay = document.getElementById('camera-loading-overlay');
        const captureProcessingOverlay = document.getElementById('capture-processing-overlay');
        const cameraFrozenIndicator = document.getElementById('camera-frozen-indicator');
        const startCameraButton = document.getElementById('start-camera-btn');
        const stopCameraButton = document.getElementById('stop-camera-btn');
        const capturePhotoButton = document.getElementById('capture-photo-btn');
        const cameraStatusText = document.getElementById('camera-status-text');
        const captureMessagePlaceholder = document.getElementById('capture-message-placeholder');
        const togglePortraitBtn = document.getElementById('toggle-portrait-btn');
        const portraitBtnLabel = document.getElementById('portrait-btn-label');
        const toggleAfBtn = document.getElementById('toggle-af-btn');
        const afBtnLabel = document.getElementById('af-btn-label');
        const oneshotAfBtn = document.getElementById('oneshot-af-btn');
        const afStatus = document.getElementById('af-status');
        let portraitMode = false;
        let afEnabled = false;
        let streamActive = false;
        let captureInProgress = false;
        let frozenFrame = null;

        function updatePortraitButton() {
            const img = cameraFeedImg;
            const container = cameraFeedContainer;
            if (portraitMode) {
                portraitBtnLabel.textContent = 'Portrait Mode: On';
                img.classList.add('portrait');
            } else {
                portraitBtnLabel.textContent = 'Portrait Mode: Off';
                img.classList.remove('portrait');
            }
            setTimeout(() => {
                if (img.offsetParent === null || img.naturalWidth === 0 || img.naturalHeight === 0) {
                    container.style.width = 'auto';
                    container.style.height = 'auto';
                    return;
                }
                let imgW = img.naturalWidth;
                let imgH = img.naturalHeight;
                if (portraitMode) {
                    [imgW, imgH] = [imgH, imgW];
                }
                const parentW = container.parentElement.clientWidth;
                const maxH = window.innerHeight * 0.7;
                let scale = Math.min(parentW / imgW, maxH / imgH, 1);
                let targetW = Math.round(imgW * scale);
                let targetH = Math.round(imgH * scale);
                container.style.width = `${targetW}px`;
                container.style.height = `${targetH}px`;
            }, 100);
        }

        togglePortraitBtn.addEventListener('click', async () => {
            if (captureInProgress) return;
            portraitMode = !portraitMode;
            updatePortraitButton();
            try {
                await fetchWithTimeout(window.apiUrls.toggleCameraOrientation, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled: portraitMode })
                });
            } catch (e) {
                displayNotification('Failed to toggle portrait mode.', 'danger', captureMessagePlaceholder);
            }
            if (streamActive && !captureInProgress) {
                showLiveFeed();
            }
        });

        // Helper function for fetch with timeout
        async function fetchWithTimeout(url, options = {}, timeout = 10000) {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), timeout);
            
            try {
                const response = await fetch(url, {
                    ...options,
                    signal: controller.signal
                });
                clearTimeout(timeoutId);
                return response;
            } catch (error) {
                clearTimeout(timeoutId);
                throw error;
            }
        }

        function showCameraLoading(text = "Loading camera...") {
            cameraFeedContainer.classList.remove('visible');
            cameraFeedImg.classList.remove('visible');
            cameraFeedImg.src = '';
            cameraLoadingOverlay.textContent = text;
            cameraLoadingOverlay.style.display = 'flex';
            captureProcessingOverlay.classList.remove('active');
            cameraFrozenIndicator.classList.remove('active');
        }

        function showCameraPlaceholder() {
            cameraFeedContainer.classList.remove('visible');
            cameraFeedImg.classList.remove('visible');
            cameraFeedImg.src = '';
            cameraLoadingOverlay.style.display = 'none';
            captureProcessingOverlay.classList.remove('active');
            cameraFrozenIndicator.classList.remove('active');
        }

        function freezeFrame() {
            // Create a canvas to capture the current frame
            const canvas = document.createElement('canvas');
            canvas.width = cameraFeedImg.naturalWidth;
            canvas.height = cameraFeedImg.naturalHeight;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(cameraFeedImg, 0, 0);
            frozenFrame = canvas.toDataURL('image/jpeg');
            
            // Set the frozen frame as the image source
            cameraFeedImg.src = frozenFrame;
            cameraFrozenIndicator.classList.add('active');
        }

        function unfreezeFrame() {
            if (streamActive && !captureInProgress) {
                showLiveFeed();
            }
            cameraFrozenIndicator.classList.remove('active');
            frozenFrame = null;
        }

        function showLiveFeed() {
            console.log("showLiveFeed called");
            if (!cameraFeedImg || !cameraFeedContainer || !cameraLoadingOverlay) {
                console.error("Missing feed elements:", {
                    img: !!cameraFeedImg,
                    container: !!cameraFeedContainer,
                    overlay: !!cameraLoadingOverlay
                });
                return;
            }
            if (captureInProgress) {
                console.log("Capture in progress, not showing live feed");
                return;
            }

            console.log("Setting up camera feed");
            cameraFeedContainer.classList.add('visible');
            cameraFeedImg.classList.remove('visible');
            cameraLoadingOverlay.style.display = 'flex';
            cameraFeedImg.src = '';

            const feedUrl = window.apiUrls.cameraFeed + "?_nocache=" + new Date().getTime();
            console.log("Camera feed URL:", feedUrl);
            cameraFeedImg.src = feedUrl;

            cameraFeedImg.onload = () => {
                console.log("camera_feed_img loaded successfully. Dimensions:", cameraFeedImg.offsetWidth, cameraFeedImg.offsetHeight);
                cameraFeedImg.classList.add('visible');
                cameraLoadingOverlay.style.display = 'none';
                updatePortraitButton();
            };

            cameraFeedImg.onerror = (event) => {
                console.error("Failed to load camera feed from URL:", feedUrl);
                console.error("Image error event:", event);
                cameraLoadingOverlay.textContent = 'Error loading feed.';
                cameraFeedImg.classList.remove('visible');
            };
        }

        async function checkCameraStatus() {
            console.log("Checking camera status...");
            showCameraLoading("Checking camera status...");
            startCameraButton.disabled = true;
            capturePhotoButton.disabled = true;
            togglePortraitBtn.disabled = true;
            toggleAfBtn.disabled = true;
            oneshotAfBtn.disabled = true;

            try {
                console.log("Fetching camera status from:", window.apiUrls.cameraStatus);
                const response = await fetchWithTimeout(window.apiUrls.cameraStatus);
                
                console.log("Camera status response:", response.status, response.statusText);
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const data = await response.json();
                console.log("Camera status data:", data);
                
                if (data.available) {
                    startCameraButton.disabled = false; 
                    if (data.streaming) {
                        console.log("Camera already streaming, activating UI");
                        activateStreamUI();
                        cameraStatusText.textContent = "Camera live."; 
                    } else {
                        console.log("Camera available but not streaming");
                        deactivateStreamUI("Camera ready. Press Start.", false);
                    }
                } else {
                    console.log("Camera not available:", data.message);
                    cameraStatusText.textContent = data.message || "RPi Camera not available.";
                    deactivateStreamUI(data.message || "RPi Camera not available.", true);
                }
            } catch (error) {
                console.error("Error checking camera status:", error);
                let errorMsg = "Camera status check failed.";
                if (error.name === 'AbortError') {
                    errorMsg = "Camera status check timed out.";
                } else if (error.message.includes('NetworkError') || error.message.includes('fetch')) {
                    errorMsg = "Network error checking camera.";
                } else if (error.message.includes('HTTP')) {
                    errorMsg = `Server error: ${error.message}`;
                }
                console.log("Final error message:", errorMsg);
                deactivateStreamUI(errorMsg, true);
            }
        }

        function activateStreamUI() {
            if (!captureInProgress) {
                showLiveFeed();
            }
            startCameraButton.style.display = 'none';
            stopCameraButton.style.display = 'block';
            stopCameraButton.disabled = captureInProgress;
            
            capturePhotoButton.style.display = 'block';
            capturePhotoButton.disabled = captureInProgress;
            togglePortraitBtn.disabled = captureInProgress;
            oneshotAfBtn.disabled = captureInProgress;
            
            cameraStatusText.textContent = "Camera live.";
            streamActive = true;
            setTimeout(updateAfStateUI, 500);
        }

        function deactivateStreamUI(statusText = "Camera stopped.", disableAll = true) {
            showCameraPlaceholder();
            startCameraButton.style.display = 'block';
            startCameraButton.disabled = disableAll || captureInProgress;

            stopCameraButton.style.display = 'none';
            capturePhotoButton.style.display = 'none';
            
            capturePhotoButton.disabled = true;
            togglePortraitBtn.disabled = true;
            toggleAfBtn.disabled = true;
            oneshotAfBtn.disabled = true;
            
            cameraStatusText.textContent = statusText;
            streamActive = false;
            captureInProgress = false;
            if (disableAll) {
                updateAfStateUI();
            }
        }

        function disableAllControls() {
            startCameraButton.disabled = true;
            stopCameraButton.disabled = true;
            capturePhotoButton.disabled = true;
            togglePortraitBtn.disabled = true;
            toggleAfBtn.disabled = true;
            oneshotAfBtn.disabled = true;
        }

        function enableControlsAfterCapture() {
            if (streamActive) {
                stopCameraButton.disabled = false;
                capturePhotoButton.disabled = false;
                togglePortraitBtn.disabled = false;
                toggleAfBtn.disabled = false;
                oneshotAfBtn.disabled = false;
            } else {
                startCameraButton.disabled = false;
            }
        }

        startCameraButton.addEventListener('click', async () => {
            startCameraButton.classList.add('is-loading');
            disableAllControls();
            showCameraLoading("Starting camera...");
            
            try {
                const response = await fetchWithTimeout(window.apiUrls.startCameraStream, { method: 'POST' });
                const result = await response.json();
                if (response.ok && result.success) {
                    activateStreamUI();
                } else {
                    const errorMsg = "Failed to start camera: " + (result.error || "Unknown error");
                    deactivateStreamUI(errorMsg);
                    displayNotification(errorMsg, 'danger', captureMessagePlaceholder);
                }
            } catch (error) {
                console.error("Error starting camera:", error);
                const errorMsg = "Error starting camera: " + error.message;
                deactivateStreamUI(errorMsg);
                displayNotification(errorMsg, 'danger', captureMessagePlaceholder);
            }
            startCameraButton.classList.remove('is-loading');
            if (!streamActive && !startCameraButton.disabled) {
                startCameraButton.disabled = false;
            }
        });

        stopCameraButton.addEventListener('click', async () => {
            if (captureInProgress) return;
            
            stopCameraButton.classList.add('is-loading');
            disableAllControls();
            showCameraLoading("Stopping camera...");
            
            try {
                const response = await fetchWithTimeout(window.apiUrls.stopCameraStream, { method: 'POST' });
                const result = await response.json();
                if (response.ok && result.success) {
                    deactivateStreamUI("Camera stopped. Press Start to resume.", false);
                } else {
                    const errorMsg = "Failed to stop camera: " + (result.error || "Unknown error");
                    cameraStatusText.textContent = errorMsg;
                    displayNotification(errorMsg, 'danger', captureMessagePlaceholder);
                    stopCameraButton.disabled = false; 
                    if(streamActive) {
                        activateStreamUI();
                    } else {
                        deactivateStreamUI(errorMsg, true);
                    }
                }
            } catch (error) {
                console.error("Error stopping camera:", error);
                const errorMsg = "Error stopping camera: " + error.message;
                cameraStatusText.textContent = errorMsg;
                displayNotification(errorMsg, 'danger', captureMessagePlaceholder);
                stopCameraButton.disabled = false; 
                if(streamActive) {
                    activateStreamUI();
                } else {
                    deactivateStreamUI(errorMsg, true);
                }
            }
            stopCameraButton.classList.remove('is-loading');
        });

        capturePhotoButton.addEventListener('click', async () => {
            captureInProgress = true;
            capturePhotoButton.classList.add('is-loading');
            disableAllControls();
            
            // Freeze the current frame
            freezeFrame();
            
            // Show processing overlay
            setTimeout(() => {
                captureProcessingOverlay.classList.add('active');
            }, 100);
            
            // Clear previous messages
            if (captureMessagePlaceholder) captureMessagePlaceholder.innerHTML = '';

            try {
                const response = await fetch(window.apiUrls.captureRpiPhoto, { method: 'POST' });
                const result = await response.json();

                if (response.ok && result.success) {
                    // Update processing text
                    captureProcessingOverlay.querySelector('.processing-text').textContent = 'Success! Redirecting...';
                    
                    if (result.redirect_url) {
                        setTimeout(() => {
                            window.location.href = result.redirect_url;
                        }, 1500);
                    } else if (result.warning) {
                        displayNotification(result.warning, 'warning', captureMessagePlaceholder);
                        captureInProgress = false;
                        captureProcessingOverlay.classList.remove('active');
                        unfreezeFrame();
                        enableControlsAfterCapture();
                    }
                } else {
                    const errorMsg = "Capture/Processing failed: " + (result.error || "Unknown error");
                    displayNotification(errorMsg, 'danger', captureMessagePlaceholder);
                    captureInProgress = false;
                    captureProcessingOverlay.classList.remove('active');
                    unfreezeFrame();
                    enableControlsAfterCapture();
                }
            } catch (error) {
                console.error("Error capturing photo:", error);
                const errorMsg = "Error during capture: " + error.message;
                displayNotification(errorMsg, 'danger', captureMessagePlaceholder);
                captureInProgress = false;
                captureProcessingOverlay.classList.remove('active');
                unfreezeFrame();
                enableControlsAfterCapture();
            }
            
            capturePhotoButton.classList.remove('is-loading');
            
            // Re-check camera status if not redirecting
            if (!result || !result.redirect_url) {
                setTimeout(() => {
                    if (!captureInProgress) {
                        checkCameraStatus();
                    }
                }, 500);
            }
        });

        function updateAfStateUI() {
            if (!toggleAfBtn) return;
            afBtnLabel.textContent = afEnabled ? 'Autofocus: On' : 'Autofocus: Off';
            toggleAfBtn.classList.toggle('autofocus-on', afEnabled);
            toggleAfBtn.classList.toggle('autofocus-off', !afEnabled);
            afStatus.textContent = '';
            toggleAfBtn.disabled = !streamActive || captureInProgress;
        }

        toggleAfBtn.addEventListener('click', async () => {
            if (!streamActive || captureInProgress) {
                displayNotification("Cannot toggle autofocus right now.", "warning", captureMessagePlaceholder);
                return;
            }
            afEnabled = !afEnabled;
            updateAfStateUI();
            afBtnLabel.textContent = afEnabled ? 'AF: Enabling...' : 'AF: Disabling...';
            toggleAfBtn.disabled = true;
            toggleAfBtn.classList.add('is-loading');
            try {
                await fetchWithTimeout(window.apiUrls.cameraSetAutofocus, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled: afEnabled })
                });
            } catch (e) {
                displayNotification('Error sending autofocus command.', 'danger', captureMessagePlaceholder);
            } finally {
                setTimeout(() => {
                    toggleAfBtn.classList.remove('is-loading');
                    updateAfStateUI();
                }, 800);
            }
        });

        oneshotAfBtn.addEventListener('click', async () => {
            if (!streamActive || captureInProgress) {
                displayNotification("Cannot trigger autofocus right now.", "warning", captureMessagePlaceholder);
                return;
            }
            oneshotAfBtn.classList.add('is-loading');
            oneshotAfBtn.disabled = true;
            toggleAfBtn.disabled = true;
            await fetchWithTimeout(window.apiUrls.cameraTriggerAutofocus, { method: 'POST' });
            setTimeout(() => {
                oneshotAfBtn.classList.remove('is-loading');
                oneshotAfBtn.disabled = false;
                toggleAfBtn.disabled = false;
                updateAfStateUI();
            }, 1200);
        });

        checkCameraStatus();
    }

    document.querySelectorAll('.notification .delete').forEach((deleteButton) => {
        if (!deleteButton.dataset.listenerAttached) {
            deleteButton.addEventListener('click', () => {
                deleteButton.parentElement.remove();
            });
            deleteButton.dataset.listenerAttached = 'true';
        }
    });
});
