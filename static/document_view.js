document.addEventListener('DOMContentLoaded', () => {
    // Modal elements
    const confirmationModal = document.getElementById('confirmationModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalMessage = document.getElementById('modalMessage');
    const modalClose = document.getElementById('modalClose');
    const modalCancel = document.getElementById('modalCancel');
    const modalConfirm = document.getElementById('modalConfirm');
    
    let currentAction = null;

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

    // Modal event listeners
    modalClose.addEventListener('click', hideModal);
    modalCancel.addEventListener('click', hideModal);
    modalConfirm.addEventListener('click', () => {
        if (currentAction) {
            currentAction();
        }
        hideModal();
    });

    // Close modal when clicking outside
    window.addEventListener('click', (event) => {
        if (event.target === confirmationModal) {
            hideModal();
        }
    });

    // Initialize drag-and-drop sorting
    const container = document.getElementById('pages-container');
    new Sortable(container, {
        animation: 150,
        handle: '.drag-handle',
        draggable: '.page-box',
        onEnd: function(evt) {
            updatePageOrder();
        }
    });

    // Handle move up/down buttons
    container.addEventListener('click', (e) => {
        const btn = e.target.closest('button');
        if (!btn) return;
        
        if (btn.classList.contains('move-up') || btn.classList.contains('move-down')) {
            const pageBox = btn.closest('.page-box');
            const isUp = btn.classList.contains('move-up');
            const sibling = isUp ? pageBox.previousElementSibling : pageBox.nextElementSibling;
            
            if (sibling && sibling.classList.contains('page-box')) {
                if (isUp) {
                    container.insertBefore(pageBox, sibling);
                } else {
                    container.insertBefore(sibling, pageBox);
                }
                updatePageOrder();
            }
        }
    });

    // Update page numbers and button states
    function updatePageOrder() {
        const pages = container.querySelectorAll('.page-box');
        const pageIds = Array.from(pages).map(page => page.dataset.pageId);
        
        pages.forEach((page, idx) => {
            page.querySelector('.page-number').textContent = `Page ${idx + 1}`;
            page.querySelector('.move-up').disabled = idx === 0;
            page.querySelector('.move-down').disabled = idx === pages.length - 1;
        });

        // Send new order to server
        fetch(`${window.location.pathname}/reorder`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ photo_ids: pageIds })
        });
    }

    // Copy text functionality
    document.querySelectorAll('.copy-text').forEach(btn => {
        btn.addEventListener('click', () => {
            const text = btn.dataset.text;
            navigator.clipboard.writeText(text).then(() => {
                const originalText = btn.innerHTML;
                btn.innerHTML = '<span class="icon"><i class="fas fa-check"></i></span><span>Copied!</span>';
                setTimeout(() => btn.innerHTML = originalText, 2000);
            });
        });
    });

    // Use as edited functionality
    document.querySelectorAll('.use-as-edited').forEach(btn => {
        btn.addEventListener('click', () => {
            const text = btn.dataset.text;
            const targetId = btn.dataset.target;
            document.getElementById(targetId).value = text;
        });
    });

    // Combined text handling
    const combinedTextArea = document.getElementById('combined-text-area');
    const saveCombinedBtn = document.getElementById('save-combined');
    
    saveCombinedBtn.addEventListener('click', async () => {
        saveCombinedBtn.classList.add('is-loading');
        try {
            const response = await fetch(`${window.location.pathname}/update_combined_text`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ combined_text: combinedTextArea.value })
            });
            const result = await response.json();
            if (response.ok) {
                saveCombinedBtn.classList.remove('is-loading');
                saveCombinedBtn.innerHTML = '<span class="icon"><i class="fas fa-check"></i></span><span>Saved!</span>';
                setTimeout(() => {
                    saveCombinedBtn.innerHTML = '<span class="icon"><i class="fas fa-save"></i></span><span>Save Changes</span>';
                }, 2000);
            } else {
                throw new Error(result.error);
            }
        } catch (err) {
            alert('Error saving combined text: ' + err.message);
            saveCombinedBtn.classList.remove('is-loading');
        }
    });

    // Regenerate combined text
    document.getElementById('regenerate-combined').addEventListener('click', () => {
        const editedTexts = Array.from(document.querySelectorAll('.page-box')).map(
            page => page.querySelector('textarea[id^="edited-"]').value
        );
        combinedTextArea.value = editedTexts.join('\n\n---\n\n');
    });

    // Process text with AI
    document.querySelectorAll('.process-text').forEach(btn => {
        btn.addEventListener('click', () => {
            const textId = btn.dataset.textId;
            const selector = document.getElementById(`prompt-selector-${textId}`);
            selector.classList.add('active');
        });
    });

    // Handle prompt selection
    document.querySelectorAll('.prompt-select').forEach(select => {
        select.addEventListener('change', () => {
            const textId = select.dataset.textId;
            const customField = document.getElementById(`custom-prompt-${textId}`);
            if (select.value === 'custom') {
                customField.classList.add('active');
            } else {
                customField.classList.remove('active');
            }
        });
    });

    // Cancel prompt selection
    document.querySelectorAll('.cancel-prompt').forEach(btn => {
        btn.addEventListener('click', () => {
            const textId = btn.dataset.textId;
            const selector = document.getElementById(`prompt-selector-${textId}`);
            selector.classList.remove('active');
            // Reset the select
            selector.querySelector('.prompt-select').value = '';
            // Hide custom prompt field
            document.getElementById(`custom-prompt-${textId}`).classList.remove('active');
        });
    });

    // Execute prompt
    document.querySelectorAll('.execute-prompt').forEach(btn => {
        btn.addEventListener('click', async () => {
            const textId = btn.dataset.textId;
            const selector = document.getElementById(`prompt-selector-${textId}`);
            const promptSelect = selector.querySelector('.prompt-select');
            const promptKey = promptSelect.value;
            
            if (!promptKey) {
                alert('Please select an AI action');
                return;
            }

            // Get the text to process
            let textToProcess;
            if (textId === 'combined') {
                textToProcess = combinedTextArea.value;
            } else {
                textToProcess = document.getElementById(textId).value;
            }

            // Get custom prompt if selected
            let customPrompt = null;
            if (promptKey === 'custom') {
                customPrompt = document.getElementById(`custom-prompt-${textId}`).querySelector('textarea').value;
                if (!customPrompt.trim()) {
                    alert('Please enter a custom prompt');
                    return;
                }
            }

            btn.classList.add('is-loading');
            
            try {
                // Determine the endpoint based on prompt type
                const isTranslation = promptKey.includes('translate');
                const endpoint = isTranslation ? 'translate' : 'format';
                
                const response = await fetch(`${window.location.pathname}/${endpoint}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        text: textToProcess,
                        prompt_key: promptKey === 'custom' ? null : promptKey,
                        custom_prompt: customPrompt
                    })
                });
                
                const result = await response.json();
                if (response.ok) {
                    // Show result
                    const resultArea = document.getElementById(`result-${textId}`);
                    const resultText = resultArea.querySelector('.result-text');
                    
                    // Get the correct result based on endpoint
                    const processedText = result.formatted_text || result.translated_text || result.text;
                    
                    resultText.value = processedText;
                    resultArea.classList.add('active');
                    
                    // Hide prompt selector
                    selector.classList.remove('active');
                    promptSelect.value = '';
                    document.getElementById(`custom-prompt-${textId}`).classList.remove('active');
                } else {
                    throw new Error(result.error || 'Processing failed');
                }
            } catch (err) {
                alert('Error processing text: ' + err.message);
            } finally {
                btn.classList.remove('is-loading');
            }
        });
    });

    // Copy result
    document.querySelectorAll('.copy-result').forEach(btn => {
        btn.addEventListener('click', () => {
            const textId = btn.dataset.textId;
            const resultText = document.getElementById(`result-${textId}`).querySelector('.result-text').value;
            
            navigator.clipboard.writeText(resultText).then(() => {
                const originalText = btn.innerHTML;
                btn.innerHTML = '<span class="icon"><i class="fas fa-check"></i></span><span>Copied!</span>';
                setTimeout(() => btn.innerHTML = originalText, 2000);
            });
        });
    });

    // Replace original with result
    document.querySelectorAll('.replace-original').forEach(btn => {
        btn.addEventListener('click', () => {
            const textId = btn.dataset.textId;
            const resultText = document.getElementById(`result-${textId}`).querySelector('.result-text').value;
            
            if (textId === 'combined') {
                combinedTextArea.value = resultText;
            } else {
                document.getElementById(textId).value = resultText;
            }
            
            // Hide result area
            document.getElementById(`result-${textId}`).classList.remove('active');
        });
    });

    // Document deletion functionality
    document.getElementById('delete-document-btn').addEventListener('click', (e) => {
        e.preventDefault();
        const docId = e.target.closest('button').dataset.docId;
        const docName = e.target.closest('button').dataset.docName;
        
        showModal(
            'Delete Document',
            `Are you sure you want to delete the document "${docName}"? This action cannot be undone and will remove all pages from this document.`,
            async () => {
                const btn = e.target.closest('button');
                btn.classList.add('is-loading');
                try {
                    const response = await fetch(`/document/${docId}/delete`, {
                        method: 'DELETE'
                    });
                    const result = await response.json();
                    
                    if (response.ok) {
                        // Redirect to gallery after successful deletion
                        window.location.href = "{{ url_for('main.gallery_view') }}";
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

    // Page removal functionality (remove from document but keep photo)
    document.querySelectorAll('.page-remove-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const photoId = btn.dataset.photoId;
            const filename = btn.dataset.filename;
            const docId = "{{ document.id }}";
            
            showModal(
                'Remove Page',
                `Are you sure you want to remove "${filename}" from this document? The photo will remain in your gallery.`,
                async () => {
                    btn.classList.add('is-loading');
                    try {
                        const response = await fetch(`/document/${docId}/photo/${photoId}/remove`, {
                            method: 'DELETE'
                        });
                        const result = await response.json();
                        
                        if (response.ok) {
                            // Remove the page from the DOM
                            const pageBox = btn.closest('.page-box');
                            pageBox.remove();
                            
                            // Update page numbers
                            updatePageOrder();
                            
                            // Update combined text
                            document.getElementById('regenerate-combined').click();
                            
                            showNotification('Page removed from document successfully.', 'success');
                        } else {
                            showNotification(result.error || 'Failed to remove page from document.', 'danger');
                        }
                    } catch (error) {
                        console.error('Error removing page from document:', error);
                        showNotification('An error occurred while removing the page.', 'danger');
                    } finally {
                        btn.classList.remove('is-loading');
                    }
                }
            );
        });
    });

    // Page deletion functionality (delete photo entirely)
    document.querySelectorAll('.page-delete-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const photoId = btn.dataset.photoId;
            const filename = btn.dataset.filename;
            
            showModal(
                'Delete Photo',
                `Are you sure you want to permanently delete "${filename}"? This will remove it from all documents and cannot be undone.`,
                async () => {
                    btn.classList.add('is-loading');
                    try {
                        const response = await fetch(`/photo/${photoId}/delete`, {
                            method: 'DELETE'
                        });
                        const result = await response.json();
                        
                        if (response.ok) {
                            // Remove the page from the DOM
                            const pageBox = btn.closest('.page-box');
                            pageBox.remove();
                            
                            // Update page numbers
                            updatePageOrder();
                            
                            // Update combined text
                            document.getElementById('regenerate-combined').click();
                            
                            showNotification('Photo deleted successfully.', 'success');
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
        const firstElement = container.querySelector('.mb-5') || container.firstElementChild;
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
});
