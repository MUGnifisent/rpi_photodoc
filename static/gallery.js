document.addEventListener('DOMContentLoaded', () => {
    const checkboxes = document.querySelectorAll('.select-photo-checkbox');
    const createDocActions = document.getElementById('create-doc-actions');
    const createDocBtn = document.getElementById('create-doc-btn');
    const selectedPhotoCountSpan = document.getElementById('selected-photo-count');
    const newDocNameInput = document.getElementById('new_doc_name');

    // Modal elements
    const confirmationModal = document.getElementById('confirmationModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalMessage = document.getElementById('modalMessage');
    const modalClose = document.getElementById('modalClose');
    const modalCancel = document.getElementById('modalCancel');
    const modalConfirm = document.getElementById('modalConfirm');

    // Photo usage modal elements
    const photoUsageModal = document.getElementById('photoUsageModal');
    const usageModalClose = document.getElementById('usageModalClose');
    const usageModalOk = document.getElementById('usageModalOk');
    const usageModalBody = document.getElementById('usageModalBody');

    let selectedPhotoIds = [];
    let currentAction = null;

    // Update create document button state
    function updateCreateDocButtonState() {
        selectedPhotoIds = Array.from(checkboxes)
                                .filter(cb => cb.checked)
                                .map(cb => cb.dataset.photoId);
        selectedPhotoCountSpan.textContent = selectedPhotoIds.length;
        if (selectedPhotoIds.length >= 1) {
            createDocBtn.disabled = false;
            createDocActions.style.display = 'flex';
        } else {
            createDocBtn.disabled = true;
            createDocActions.style.display = 'none';
        }
    }

    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', updateCreateDocButtonState);
    });

    // Create document functionality
    createDocBtn.addEventListener('click', async () => {
        if (selectedPhotoIds.length < 1) {
            alert('Please select at least one photo to create a document.');
            return;
        }
        const newName = newDocNameInput.value.trim();
        createDocBtn.classList.add('is-loading');
        try {
            const response = await fetch(window.apiUrls.createDocumentRoute, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    photo_ids: selectedPhotoIds,
                    doc_name: newName
                })
            });
            const result = await response.json();
            if (response.ok && result.new_document_id) {
                window.location.href = window.apiUrls.documentView.replace('_PLACEHOLDER_', result.new_document_id);
            } else {
                alert(result.error || 'Failed to create document.');
            }
        } catch (error) {
            console.error('Error creating document:', error);
            alert('An error occurred while trying to create the document.');
        } finally {
            createDocBtn.classList.remove('is-loading');
        }
    });

    // Modal functions
    function showModal(title, message, confirmCallback) {
        modalTitle.textContent = title;
        modalMessage.textContent = message;
        confirmationModal.classList.add('is-active');
        currentAction = confirmCallback;
    }

    function hideModal() {
        confirmationModal.classList.remove('is-active');
        currentAction = null;
    }

    function showPhotoUsageModal(photoId) {
        usageModalBody.innerHTML = '<p>Loading...</p>';
        photoUsageModal.classList.add('is-active');
        
        // Fetch photo usage information
        fetch(`/photo/${photoId}/usage`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    usageModalBody.innerHTML = `<p class="has-text-danger">${data.error}</p>`;
                } else {
                    let html = `<p><strong>Photo:</strong> ${data.filename}</p>`;
                    if (data.usage_count === 0) {
                        html += '<p class="has-text-success">This photo is not used in any documents and can be safely deleted.</p>';
                    } else {
                        html += `<p><strong>Used in ${data.usage_count} document(s):</strong></p><ul>`;
                        data.used_in_documents.forEach(doc => {
                            html += `<li><a href="/document/${doc.id}">${doc.name}</a></li>`;
                        });
                        html += '</ul><p class="has-text-warning">Remove this photo from all documents before deleting it.</p>';
                    }
                    usageModalBody.innerHTML = html;
                }
            })
            .catch(error => {
                console.error('Error fetching photo usage:', error);
                usageModalBody.innerHTML = '<p class="has-text-danger">Error loading photo usage information.</p>';
            });
    }

    function hidePhotoUsageModal() {
        photoUsageModal.classList.remove('is-active');
    }

    // Modal event listeners
    modalClose.addEventListener('click', hideModal);
    modalCancel.addEventListener('click', hideModal);
    modalConfirm.addEventListener('click', () => {
        if (currentAction) {
            currentAction();
        }
        hideModal();
    });

    usageModalClose.addEventListener('click', hidePhotoUsageModal);
    usageModalOk.addEventListener('click', hidePhotoUsageModal);

    // Close modal when clicking outside
    window.addEventListener('click', (event) => {
        if (event.target === confirmationModal) {
            hideModal();
        }
        if (event.target === photoUsageModal) {
            hidePhotoUsageModal();
        }
    });

    // Photo deletion functionality
    document.querySelectorAll('.photo-delete-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            const photoId = btn.dataset.photoId;
            const filename = btn.dataset.filename;
            
            showModal(
                'Delete Photo',
                `Are you sure you want to permanently delete "${filename}"? This action cannot be undone.`,
                async () => {
                    btn.classList.add('is-loading');
                    try {
                        const response = await fetch(`/photo/${photoId}/delete`, {
                            method: 'DELETE'
                        });
                        const result = await response.json();
                        
                        if (response.ok) {
                            // Remove the photo card from the DOM
                            const photoCard = btn.closest('.photo-card');
                            photoCard.remove();
                            
                            // Show success message
                            showNotification('Photo deleted successfully.', 'success');
                            
                            // Update create doc button state
                            updateCreateDocButtonState();
                        } else {
                            showNotification(result.error || 'Failed to delete photo.', 'danger');
                        }
                    } catch (error) {
                        console.error('Error deleting photo:', error);
                        showNotification('An error occurred while deleting the photo.', 'danger');
                    } finally {
                        btn.classList.remove('is-loading');
                    }
                }
            );
        });
    });

    // Photo usage functionality
    document.querySelectorAll('.photo-usage-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const photoId = btn.dataset.photoId;
            showPhotoUsageModal(photoId);
        });
    });

    // Document deletion functionality
    document.querySelectorAll('.doc-delete-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            const docId = btn.dataset.docId;
            const docName = btn.dataset.docName;
            
            showModal(
                'Delete Document',
                `Are you sure you want to delete the document "${docName}"? This action cannot be undone.`,
                async () => {
                    btn.classList.add('is-loading');
                    try {
                        const response = await fetch(`/document/${docId}/delete`, {
                            method: 'DELETE'
                        });
                        const result = await response.json();
                        
                        if (response.ok) {
                            // Remove the document card from the DOM
                            const docCard = btn.closest('.doc-card');
                            docCard.remove();
                            
                            // Show success message
                            showNotification('Document deleted successfully.', 'success');
                        } else {
                            showNotification(result.error || 'Failed to delete document.', 'danger');
                        }
                    } catch (error) {
                        console.error('Error deleting document:', error);
                        showNotification('An error occurred while deleting the document.', 'danger');
                    } finally {
                        btn.classList.remove('is-loading');
                    }
                }
            );
        });
    });

    // Notification function
    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification is-${type} is-light is-small mb-4`;
        notification.innerHTML = `
            <button class="delete is-small"></button>
            ${message}
        `;
        
        // Insert at the top of the container
        const container = document.querySelector('.container');
        const firstElement = container.querySelector('.level') || container.firstElementChild;
        container.insertBefore(notification, firstElement.nextSibling);
        
        // Add delete functionality
        const deleteBtn = notification.querySelector('.delete');
        deleteBtn.addEventListener('click', () => notification.remove());
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }

    updateCreateDocButtonState();
});
