document.addEventListener('DOMContentLoaded', function() {
    let violationsCount = 0;
    let currentPage = 1;
    const framesPerPage = 20;
    
    // Handle thumbnail clicks for modal display
    document.querySelectorAll('.frame-thumbnail').forEach(thumb => {
        thumb.addEventListener('click', function() {
            const framePath = this.dataset.framePath;
            const frameTime = this.dataset.frameTime;
            const isAnnotated = this.dataset.isAnnotated;
            
            document.getElementById('modalImage').src = framePath;
            document.getElementById('frameTimestamp').textContent = 'Captured at: ' + frameTime;
            
            // Store reference to this frame in the modal for potential violation creation
            const modalAddBtn = document.getElementById('modal-add-violation');
            if (modalAddBtn) {
                modalAddBtn.dataset.framePath = framePath;
                modalAddBtn.dataset.frameTime = frameTime;
            }
            
            new bootstrap.Modal(document.getElementById('frameModal')).show();
        });
    });
    
    // Add violation directly from modal
    const modalAddBtn = document.getElementById('modal-add-violation');
    if (modalAddBtn) {
        modalAddBtn.addEventListener('click', function() {
            const framePath = this.dataset.framePath;
            const frameTime = this.dataset.frameTime;
            
            // Create new violation and add evidence path
            const form = addViolationForm();
            form.querySelector('.violation-evidence-path').value = framePath;
            form.querySelector('.violation-description').value = `Suspicious activity detected at ${frameTime}`;
            
            // Close modal and switch to violations tab
            bootstrap.Modal.getInstance(document.getElementById('frameModal')).hide();
            document.getElementById('violations-tab').click();
        });
    }
    
    // Frame filtering
    const filterButtons = document.querySelectorAll('[data-filter]');
    filterButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Update active state
            filterButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
            
            const filterValue = this.getAttribute('data-filter');
            const frames = document.querySelectorAll('.frame-item');
            let visibleCount = 0;
            
            frames.forEach(frame => {
                const frameType = frame.dataset.frameType;
                
                if (filterValue === 'all' || frameType === filterValue) {
                    frame.style.display = 'block';
                    visibleCount++;
                } else {
                    frame.style.display = 'none';
                }
            });
            
            // Update counter
            document.getElementById('visible-frame-count').textContent = visibleCount;
        });
    });
    
    // Load more frames button
    const loadMoreBtn = document.getElementById('load-more-frames');
    if (loadMoreBtn) {
        loadMoreBtn.addEventListener('click', function() {
            currentPage++;
            loadMoreFrames(currentPage);
        });
    }
    
    function loadMoreFrames(page) {
        const resultId = document.querySelector('[data-result-id]')?.dataset.resultId;
        if (!resultId) return;
        
        loadMoreBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Loading...';
        loadMoreBtn.disabled = true;
        
        fetch(`/results/review/${resultId}/frames/?page=${page}`)
            .then(response => response.json())
            .then(data => {
                if (data.frames && data.frames.length) {
                    const frameGallery = document.querySelector('.frame-gallery');
                    
                    data.frames.forEach(frame => {
                        const isAnnotated = frame.frame_path.toLowerCase().includes('annotated');
                        const frameItem = document.createElement('div');
                        frameItem.className = `frame-item ${isAnnotated ? 'annotated-frame' : ''}`;
                        frameItem.dataset.frameType = isAnnotated ? 'annotated' : 'regular';
                        
                        frameItem.innerHTML = `
                            <img src="/media/${frame.frame_path}" 
                                 class="frame-thumbnail ${isAnnotated ? 'annotated' : ''}" 
                                 data-frame-path="/media/${frame.frame_path}"
                                 data-frame-time="${frame.timestamp}"
                                 data-is-annotated="${isAnnotated}"
                                 alt="${isAnnotated ? 'Annotated' : 'Regular'} Monitoring Frame">
                            ${isAnnotated ? '<div class="frame-badge"><span class="badge bg-warning">Annotated</span></div>' : ''}
                            <div class="frame-time-badge">
                                <small class="text-white bg-dark px-1 rounded">${frame.timestamp}</small>
                            </div>
                        `;
                        
                        frameGallery.appendChild(frameItem);
                        
                        // Add click handler for the new frame
                        const newThumb = frameItem.querySelector('.frame-thumbnail');
                        newThumb.addEventListener('click', function() {
                            const framePath = this.dataset.framePath;
                            const frameTime = this.dataset.frameTime;
                            
                            document.getElementById('modalImage').src = framePath;
                            document.getElementById('frameTimestamp').textContent = 'Captured at: ' + frameTime;
                            
                            new bootstrap.Modal(document.getElementById('frameModal')).show();
                        });
                    });
                    
                    // Update visible frame count
                    const visibleCount = document.querySelectorAll('.frame-item[style="display: block;"], .frame-item:not([style*="display"])').length;
                    document.getElementById('visible-frame-count').textContent = visibleCount;
                    
                    // Hide load more button if all frames loaded
                    if (data.has_more === false) {
                        loadMoreBtn.style.display = 'none';
                    }
                } else {
                    loadMoreBtn.style.display = 'none';
                }
            })
            .catch(error => {
                console.error('Error loading more frames:', error);
            })
            .finally(() => {
                loadMoreBtn.innerHTML = 'Load More Frames <i class="fas fa-arrow-down"></i>';
                loadMoreBtn.disabled = false;
                
                // Apply current filter
                const activeFilter = document.querySelector('[data-filter].active');
                if (activeFilter) {
                    activeFilter.click();
                }
            });
    }
    
    // Question filtering and search
    const questionFilterBtns = document.querySelectorAll('[data-question-filter]');
    questionFilterBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            questionFilterBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            const filterValue = this.getAttribute('data-question-filter');
            const questions = document.querySelectorAll('.question-item');
            
            questions.forEach(q => {
                const status = q.dataset.questionStatus;
                
                if (filterValue === 'all' || status === filterValue) {
                    q.style.display = '';
                } else {
                    q.style.display = 'none';
                }
            });
        });
    });
    
    // Question search
    const questionSearch = document.getElementById('question-search');
    if (questionSearch) {
        questionSearch.addEventListener('input', function() {
            const searchValue = this.value.toLowerCase();
            const questions = document.querySelectorAll('.question-item');
            
            questions.forEach(q => {
                const questionText = q.querySelector('.accordion-button').textContent.toLowerCase();
                
                if (questionText.includes(searchValue)) {
                    q.style.display = '';
                } else {
                    q.style.display = 'none';
                }
            });
        });
    }
    
    // Expand/Collapse all questions
    const expandAllBtn = document.getElementById('expand-all-questions');
    if (expandAllBtn) {
        expandAllBtn.addEventListener('click', function() {
            document.querySelectorAll('.question-item:not([style*="display: none"]) .accordion-button.collapsed').forEach(btn => {
                btn.click();
            });
        });
    }
    
    const collapseAllBtn = document.getElementById('collapse-all-questions');
    if (collapseAllBtn) {
        collapseAllBtn.addEventListener('click', function() {
            document.querySelectorAll('.question-item:not([style*="display: none"]) .accordion-button:not(.collapsed)').forEach(btn => {
                btn.click();
            });
        });
    }
    
    // Violation form management
    const violationsContainer = document.getElementById('violations-container');
    const violationTemplate = document.getElementById('violation-form-template').innerHTML;
    
    function addViolationForm(alertId = '', alertType = '', alertDesc = '', evidencePath = '') {
        violationsCount++;
        
        // Create violation form from template
        let formHtml = violationTemplate.replace(/{index}/g, violationsCount);
        
        // Create a temporary div to hold the form HTML
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = formHtml;
        
        // Add the form to the container
        violationsContainer.appendChild(tempDiv.firstElementChild);
        
        // Get the newly added form
        const formElement = violationsContainer.lastElementChild;
        
        // Set values if provided
        if (alertId) {
            formElement.querySelector('.violation-alert-id').value = alertId;
        }
        
        if (alertType) {
            formElement.querySelector('.violation-type').value = alertType;
        }
        
        if (alertDesc) {
            formElement.querySelector('.violation-description').value = alertDesc;
        }
        
        if (evidencePath) {
            formElement.querySelector('.violation-evidence-path').value = evidencePath;
        }
        
        // Enable the confirm violations button
        document.getElementById('confirm-violations-btn').disabled = false;
        
        // Add event listener for removal button
        formElement.querySelector('.remove-violation-btn').addEventListener('click', function() {
            formElement.remove();
            
            // Disable the confirm button if no violations
            if (violationsContainer.children.length === 0) {
                document.getElementById('confirm-violations-btn').disabled = true;
            }
        });
        
        return formElement;
    }
    
    // Add violation from alert
    document.querySelectorAll('.confirm-violation-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const alertId = this.dataset.alertId;
            const alertType = this.dataset.alertType;
            const alertDesc = this.dataset.alertDesc;
            
            const form = addViolationForm(alertId, alertType, alertDesc);
            
            // Switch to the violations tab
            document.getElementById('violations-tab').click();
        });
    });
    
    // Manual add violation button
    const addViolationBtn = document.getElementById('add-violation-btn');
    if (addViolationBtn) {
        addViolationBtn.addEventListener('click', function() {
            addViolationForm();
        });
    }
    
    // Clear flag button
    const clearBtn = document.getElementById('clear-btn');
    if (clearBtn) {
        clearBtn.addEventListener('click', function() {
            const notes = document.getElementById('reviewNotes').value;
            
            if (confirm("Are you sure you want to clear this flag? This will mark the exam as reviewed with no violations.")) {
                submitReview('clear', notes);
            }
        });
    }
    
    // Confirm violations button
    const confirmViolationsBtn = document.getElementById('confirm-violations-btn');
    if (confirmViolationsBtn) {
        confirmViolationsBtn.addEventListener('click', function() {
            const notes = document.getElementById('reviewNotes').value;
            const violations = [];
            
            // Collect all violation data
            document.querySelectorAll('.violation-form').forEach(form => {
                violations.push({
                    type: form.querySelector('.violation-type').value,
                    severity: form.querySelector('.violation-severity').value,
                    penalty: form.querySelector('.violation-penalty').value,
                    description: form.querySelector('.violation-description').value,
                    alert_id: form.querySelector('.violation-alert-id').value || null,
                    evidence_path: form.querySelector('.violation-evidence-path').value || null,
                });
            });
            
            if (violations.length === 0) {
                alert("Please add at least one violation or use the 'Clear Flag' button.");
                return;
            }
            
            // Validate form entries
            let isValid = true;
            violations.forEach((violation, index) => {
                if (!violation.type || !violation.description) {
                    alert(`Violation #${index + 1} has missing required fields. Please fill all required fields.`);
                    isValid = false;
                    return;
                }
            });
            
            if (!isValid) return;
            
            if (confirm("Are you sure you want to confirm these violations? This will apply penalties to the student's score.")) {
                submitReview('confirm_violations', notes, violations);
            }
        });
    }
    
    // Get the result ID from the page
    const resultId = document.querySelector('[data-result-id]')?.dataset.resultId;
    
    // Submit review function
    function submitReview(action, notes, violations = []) {
        // Get CSRF token from meta tag
        const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        
        const data = {
            action: action,
            notes: notes,
            violations: violations
        };
        
        // Show loading state
        const submitBtn = action === 'clear' ? clearBtn : confirmViolationsBtn;
        const originalBtnText = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
        
        fetch(`/results/review/${resultId}/process/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify(data)
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Server responded with status: ' + response.status);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                alert(data.message);
                // Get the exam ID from the response or data attribute
                const examId = data.exam_id || document.querySelector('[data-exam-id]')?.dataset.examId;
                window.location.href = `/results/exam/${examId}/results/`;
            } else {
                alert("Error: " + data.error);
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalBtnText;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert("An error occurred while processing your request: " + error.message);
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtnText;
        });
    }
});