/**
 * Exam Monitor Dashboard
 * Responsible for managing student video feeds and alerts in the exam monitoring system
 */
class ExamMonitorDashboard {
    constructor(examId) {
        this.examId = examId;
        this.activeStudents = new Map();
        this.alertCounter = 0;
        this.inactiveCheckInterval = null;
        
        // DOM elements
        this.videoGrid = document.getElementById('videoGrid');
        this.emptyState = document.getElementById('emptyState');
        this.alertsList = document.querySelector('.alerts-list');
        this.alertCounter = document.getElementById('alertCounter');
        this.connectionStatus = document.getElementById('connectionStatus');
        
        // Get CSRF token for AJAX requests
        this.csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    }
    
    /**
     * Initialize the monitoring dashboard
     */
    async initialize() {
        try {
            this.connectionStatus.textContent = 'Connecting...';
            await this.loadActiveStudents();
            this.connectionStatus.textContent = 'Connected';
            
            // Set up event listeners
            document.addEventListener('click', event => {
                // Event delegation for focus buttons
                if (event.target.classList.contains('focus-btn') || 
                    event.target.closest('.focus-btn')) {
                    const card = event.target.closest('.video-card');
                    if (card) {
                        const studentId = card.dataset.studentId;
                        this.focusStudent(studentId);
                    }
                }
            });
        } catch (error) {
            console.error('Error initializing dashboard:', error);
            this.connectionStatus.textContent = 'Connection Error';
        }
    }
    
    /**
     * Load active student sessions for this exam
     */
    async loadActiveStudents() {
        try {
            const response = await fetch(`/monitoring/api/exam/${this.examId}/sessions/`, {
                headers: {
                    'X-CSRFToken': this.csrfToken
                }
            });
            
            if (!response.ok) {
                throw new Error('Failed to fetch active students');
            }
            
            const data = await response.json();
            
            if (data.sessions.length === 0) {
                this.showEmptyState();
                return;
            }
            
            this.hideEmptyState();
            
            // Create or update student cards
            data.sessions.forEach(session => {
                this.createOrUpdateStudentCard(session);
            });
            
            // Load recent alerts
            if (data.alerts) {
                data.alerts.forEach(alert => {
                    this.addAlert(alert);
                });
            }
            
        } catch (error) {
            console.error('Error loading active students:', error);
            this.connectionStatus.textContent = 'Failed to load students';
        }
    }
    
    /**
     * Create or update a student video card
     */
    createOrUpdateStudentCard(session) {
        let card = this.videoGrid.querySelector(`.video-card[data-session-id="${session.id}"]`);
        
        // If card doesn't exist, create it from template
        if (!card) {
            const template = document.getElementById('videoCardTemplate');
            card = template.content.cloneNode(true).querySelector('.video-card');
            card.dataset.sessionId = session.id;
            card.dataset.studentId = session.student_id;
            
            const studentName = card.querySelector('.student-name');
            studentName.textContent = session.student_name || `Student #${session.student_id}`;
            
            this.videoGrid.appendChild(card);
        }
        
        // Update card with latest data
        card.classList.toggle('disconnected', !session.is_active);
        
        // Fetch latest frame for this session
        this.fetchLatestFrame(session.id, card);
        
        // Store in active students map
        this.activeStudents.set(session.id.toString(), {
            lastUpdate: new Date(),
            element: card
        });
    }
    
    /**
     * Fetch the latest frame for a student session
     */
    async fetchLatestFrame(sessionId, card) {
        try {
            const response = await fetch(`/monitoring/api/session/${sessionId}/latest-frame/`, {
                headers: {
                    'X-CSRFToken': this.csrfToken
                }
            });
            
            if (!response.ok) {
                throw new Error(`Failed to fetch frame for session ${sessionId}`);
            }
            
            const data = await response.json();
            
            if (data.frame_url) {
                const img = card.querySelector('.student-video');
                // Add timestamp to prevent caching
                img.src = `${data.frame_url}?t=${new Date().getTime()}`;
                
                // Update connection status
                const statusElement = card.querySelector('.connection-status');
                statusElement.textContent = 'Connected';
                statusElement.classList.remove('disconnected');
                
                // Update alert indicator if there are active alerts
                if (data.has_active_alerts) {
                    const alertIndicator = card.querySelector('.alert-indicator');
                    alertIndicator.classList.remove('hidden');
                    alertIndicator.querySelector('.alert-text').textContent = 
                        data.alert_count > 1 ? `${data.alert_count} alerts` : '1 alert';
                }
            }
        } catch (error) {
            console.error(`Error fetching frame for session ${sessionId}:`, error);
            const statusElement = card.querySelector('.connection-status');
            statusElement.textContent = 'Disconnected';
            statusElement.classList.add('disconnected');
        }
    }
    
    /**
     * Add an alert to the alerts panel
     */
    addAlert(alert) {
        const alertElement = document.createElement('div');
        alertElement.className = `alert-item ${alert.severity}`;
        alertElement.dataset.alertId = alert.id;
        
        alertElement.innerHTML = `
            <div class="alert-header">
                <span class="alert-student">${alert.student_name}</span>
                <span class="alert-time">${this.formatTime(alert.timestamp)}</span>
            </div>
            <div class="alert-message">${alert.description}</div>
            <div class="alert-actions">
                <button class="mark-reviewed-btn" data-alert-id="${alert.id}">Mark as Reviewed</button>
            </div>
        `;
        
        alertElement.querySelector('.mark-reviewed-btn').addEventListener('click', () => {
            this.markAlertReviewed(alert.id);
        });
        
        this.alertsList.prepend(alertElement);
        this.updateAlertCounter();
    }
    
    /**
     * Mark an alert as reviewed
     */
    async markAlertReviewed(alertId) {
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
            
            const alertElement = this.alertsList.querySelector(`.alert-item[data-alert-id="${alertId}"]`);
            if (alertElement) {
                alertElement.remove();
                this.updateAlertCounter();
            }
        } catch (error) {
            console.error('Error marking alert as reviewed:', error);
        }
    }
    
    /**
     * Update the alert counter badge
     */
    updateAlertCounter() {
        const count = this.alertsList.querySelectorAll('.alert-item').length;
        this.alertCounter.textContent = count;
    }
    
    /**
     * Show empty state when no active students
     */
    showEmptyState() {
        if (this.emptyState) {
            this.emptyState.style.display = 'flex';
        }
    }
    
    /**
     * Hide empty state when students are active
     */
    hideEmptyState() {
        if (this.emptyState) {
            this.emptyState.style.display = 'none';
        }
    }
    
    /**
     * Format timestamp for display
     */
    formatTime(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    }
    
    /**
     * Focus on a specific student (for future implementation)
     */
    focusStudent(studentId) {
        console.log(`Focusing on student ${studentId} - Feature to be implemented`);
        // This would open a modal or dedicated view for the selected student
        // Future implementation
    }
    
    /**
     * Start checking for inactive students
     */
    startInactiveCheck() {
        // Check every 30 seconds for inactive students
        this.inactiveCheckInterval = setInterval(() => this.checkInactiveStudents(), 30000);
    }
    
    /**
     * Check for inactive students and update their status
     */
    checkInactiveStudents() {
        const now = new Date();
        this.activeStudents.forEach((data, sessionId) => {
            const timeDiff = now - data.lastUpdate;
            // If no update for more than 1 minute, mark as potentially disconnected
            if (timeDiff > 60000) {
                const card = data.element;
                const statusElement = card.querySelector('.connection-status');
                statusElement.textContent = 'Disconnected';
                statusElement.classList.add('disconnected');
                card.classList.add('disconnected');
            }
        });
    }
    
    /**
     * Refresh all student streams
     */
    refreshStreams() {
        this.connectionStatus.textContent = 'Refreshing...';
        this.loadActiveStudents().then(() => {
            this.connectionStatus.textContent = 'Connected';
        }).catch(error => {
            console.error('Error refreshing streams:', error);
            this.connectionStatus.textContent = 'Refresh Failed';
        });
    }
}