/**
 * Exam Monitoring Dashboard
 * Handles real-time monitoring of exams, student sessions, and alerts
 */
class ExamMonitoringDashboard {
    constructor() {
        // DOM elements
        this.examFilter = document.getElementById('examFilter');
        this.examCards = document.querySelectorAll('.exam-card');
        this.sessionRows = document.querySelectorAll('.session-row');
        this.alertRows = document.querySelectorAll('.alert-row');
        this.alertModal = document.getElementById('alertModal');
        this.closeModalBtn = this.alertModal?.querySelector('.close-modal');
        this.alertDetails = this.alertModal?.querySelector('.alert-details');
        this.alertScreenshot = this.alertModal?.querySelector('.alert-screenshot');
        this.markReviewedBtn = this.alertModal?.querySelector('.mark-reviewed-btn');
        
        // Get CSRF token for AJAX requests
        this.csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        
        // State management
        this.currentAlertId = null;
        this.refreshInterval = null;
        
        // Initialize
        this.setupEventListeners();
        this.updateInitialAlertCounts();
    }
    
    /**
     * Set up event listeners for dashboard interactions
     */
    setupEventListeners() {
        // Exam filter change
        if (this.examFilter) {
            this.examFilter.addEventListener('change', () => this.handleExamFilter());
        }
        
        // Alert view buttons
        document.querySelectorAll('.view-alert-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const alertId = e.target.dataset.alertId;
                this.openAlertModal(alertId);
            });
        });
        
        // Modal close button
        if (this.closeModalBtn) {
            this.closeModalBtn.addEventListener('click', () => this.closeAlertModal());
        }
        
        // Mark as reviewed button
        if (this.markReviewedBtn) {
            this.markReviewedBtn.addEventListener('click', () => {
                if (this.currentAlertId) {
                    this.markAlertAsReviewed(this.currentAlertId);
                }
            });
        }
        
        // Close modal when clicking outside
        window.addEventListener('click', (e) => {
            if (e.target === this.alertModal) {
                this.closeAlertModal();
            }
        });

        // Refresh button (manual refresh option)
        const refreshButton = document.createElement('button');
        refreshButton.className = 'refresh-button';
        refreshButton.innerHTML = '<i class="fas fa-sync-alt"></i> Refresh Data';
        refreshButton.addEventListener('click', () => {
            window.location.reload();
        });

        // Add refresh button to controls
        const controls = document.querySelector('.controls');
        if (controls) {
            controls.appendChild(refreshButton);
        }
    }
    
    /**
     * Calculate initial alert counts for each exam
     */
    updateInitialAlertCounts() {
        // Create exam to alert count mapping
        const examAlertCounts = new Map();
        
        // Count alerts for each exam
        document.querySelectorAll('.alert-row').forEach(row => {
            const examCell = row.querySelector('td:nth-child(2)')?.textContent.trim();
            const examId = this.getExamIdFromName(examCell);
            
            if (examId) {
                const currentCount = examAlertCounts.get(examId) || 0;
                examAlertCounts.set(examId, currentCount + 1);
            }
        });
        
        // Update the alert counts in the UI
        this.examCards.forEach(card => {
            const examId = card.dataset.examId;
            const alertCountElement = card.querySelector('.alert-count');
            if (alertCountElement) {
                alertCountElement.textContent = examAlertCounts.get(examId) || 0;
            }
        });
    }
    
    /**
     * Filter dashboard content based on selected exam
     */
    handleExamFilter() {
        const selectedExamId = this.examFilter.value;
        
        // Filter exam cards
        this.examCards.forEach(card => {
            if (selectedExamId === 'all' || card.dataset.examId === selectedExamId) {
                card.style.display = 'block';
            } else {
                card.style.display = 'none';
            }
        });
        
        // Filter session rows
        this.sessionRows.forEach(row => {
            if (selectedExamId === 'all' || row.dataset.examId === selectedExamId) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
        
        // Filter alert rows
        this.alertRows.forEach(row => {
            const examCell = row.querySelector('td:nth-child(2)')?.textContent;
            const rowExamId = this.getExamIdFromName(examCell);
            
            if (selectedExamId === 'all' || rowExamId === selectedExamId) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    }
    
    /**
     * Get exam ID from the exam name (helper method)
     */
    getExamIdFromName(examName) {
        if (!examName) return null;
        
        for (const card of this.examCards) {
            if (card.querySelector('h3')?.textContent.trim() === examName.trim()) {
                return card.dataset.examId;
            }
        }
        return null;
    }
    
    /**
     * Open alert details modal and load data
     */
    async openAlertModal(alertId) {
        if (!this.alertModal) return;
        
        this.currentAlertId = alertId;
        
        try {
            // Get the alert row to extract data
            const alertRow = document.querySelector(`.alert-row[data-alert-id="${alertId}"]`);
            if (!alertRow) {
                throw new Error('Alert not found');
            }
            
            // Extract data from the row instead of making an API call
            const studentName = alertRow.cells[0].textContent.trim();
            const examName = alertRow.cells[1].textContent.trim();
            const alertType = alertRow.cells[2].textContent.trim();
            const severity = alertRow.cells[3].textContent.trim();
            const time = alertRow.cells[4].textContent.trim();
            
            // Show modal with extracted data
            this.alertDetails.innerHTML = `
                <div class="detail-item">
                    <span class="detail-label">Student:</span>
                    <span class="detail-value">${studentName}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Exam:</span>
                    <span class="detail-value">${examName}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Alert Type:</span>
                    <span class="detail-value">${alertType}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Severity:</span>
                    <span class="detail-value severity-${alertRow.className.includes('high') ? 'high' : alertRow.className.includes('medium') ? 'medium' : 'low'}">${severity}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Time:</span>
                    <span class="detail-value">${time}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Description:</span>
                    <span class="detail-value">Alert detected during exam monitoring.</span>
                </div>
            `;
            
            // Display screenshot link if available
            const screenshotBtn = alertRow.querySelector('.view-screenshot-btn');
            if (screenshotBtn) {
                const screenshotUrl = screenshotBtn.getAttribute('href');
                this.alertScreenshot.innerHTML = `
                    <h4>Alert Screenshot</h4>
                    <img src="${screenshotUrl}" alt="Alert Screenshot" class="alert-image">
                `;
            } else {
                this.alertScreenshot.innerHTML = '<p>No screenshot available for this alert.</p>';
            }
            
            this.alertModal.style.display = 'block';
            
        } catch (error) {
            console.error('Error displaying alert details:', error);
            if (this.alertDetails) {
                this.alertDetails.innerHTML = '<p class="error">Failed to load alert details. Please try again.</p>';
            }
            this.alertModal.style.display = 'block';
        }
    }
    
    /**
     * Close the alert modal
     */
    closeAlertModal() {
        if (this.alertModal) {
            this.alertModal.style.display = 'none';
            this.currentAlertId = null;
        }
    }
    
    /**
     * Mark an alert as reviewed
     */
    async markAlertAsReviewed(alertId) {
        try {
            const response = await fetch(`/monitoring/alert/${alertId}/mark-reviewed/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken,
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                throw new Error('Failed to mark alert as reviewed');
            }
            
            // Remove the alert row from the table
            const alertRow = document.querySelector(`.alert-row[data-alert-id="${alertId}"]`);
            if (alertRow) {
                alertRow.remove();
                
                // Update alert counts
                this.updateAlertCounts();
            }
            
            // Close the modal
            this.closeAlertModal();
            
        } catch (error) {
            console.error('Error marking alert as reviewed:', error);
            alert('Failed to mark alert as reviewed. Please try again.');
        }
    }
    
    /**
     * Update alert counts across the dashboard
     */
    updateAlertCounts() {
        // Create exam to alert count mapping
        const examAlertCounts = new Map();
        
        // Count remaining alerts for each exam
        document.querySelectorAll('.alert-row').forEach(row => {
            if (row.style.display !== 'none') {
                const examCell = row.querySelector('td:nth-child(2)')?.textContent.trim();
                const examId = this.getExamIdFromName(examCell);
                
                if (examId) {
                    const currentCount = examAlertCounts.get(examId) || 0;
                    examAlertCounts.set(examId, currentCount + 1);
                }
            }
        });
        
        // Update the alert counts in the UI
        this.examCards.forEach(card => {
            const examId = card.dataset.examId;
            const alertCountElement = card.querySelector('.alert-count');
            if (alertCountElement) {
                alertCountElement.textContent = examAlertCounts.get(examId) || 0;
            }
        });
    }
}

// Initialize the dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new ExamMonitoringDashboard();
});
