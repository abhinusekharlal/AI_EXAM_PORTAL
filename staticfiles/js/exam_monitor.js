/**
 * Exam Monitor Dashboard
 * Responsible for managing student video feeds and alerts in the exam monitoring system
 */
class ExamMonitorDashboard {
    constructor(examId) {
        this.examId = examId;
        this.activeStudents = new Map();
        this.inactiveCheckInterval = null;
        this.autoRefreshInterval = null;
        this.examTimerInterval = null;
        this.lastRefreshTime = new Date();
        this.isRefreshing = false;
        this.currentView = localStorage.getItem('examMonitorView') || 'grid';
        this.currentFilter = 'all';
        this.currentStudentFilter = 'all';
        this.searchQuery = '';
        this.examEndTime = null;
        
        // DOM elements
        this.videoGrid = document.getElementById('videoGrid');
        this.emptyState = document.getElementById('emptyState');
        this.alertsList = document.querySelector('.alerts-list');
        this.emptyAlerts = document.getElementById('emptyAlerts');
        this.alertCounter = document.getElementById('alertCounter');
        this.connectionStatus = document.getElementById('connectionStatus');
        this.activeStudentsCount = document.getElementById('activeStudentsCount');
        this.totalAlerts = document.getElementById('totalAlerts');
        this.flaggedStudents = document.getElementById('flaggedStudents');
        this.disconnectedStudents = document.getElementById('disconnectedStudents');
        this.studentSearch = document.getElementById('studentSearch');
        this.alertFilter = document.getElementById('alertFilter');
        this.studentFilter = document.getElementById('studentFilter');
        this.clearSearchBtn = document.getElementById('clearSearchBtn');
        this.examTimeRemaining = document.getElementById('examTimeRemaining');
        this.connectionErrorOverlay = document.getElementById('connectionErrorOverlay');
        
        // Modals
        this.warningModal = document.getElementById('warningModal');
        this.flagModal = document.getElementById('flagModal');
        this.activityModal = document.getElementById('activityModal');
        this.focusModal = document.getElementById('focusModal');
        this.shortcutsModal = document.getElementById('shortcutsModal');
        
        // Get CSRF token for AJAX requests
        this.csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        
        // Bind methods to maintain 'this' context
        this.refreshStreams = this.refreshStreams.bind(this);
        this.searchStudents = this.searchStudents.bind(this);
        this.filterAlerts = this.filterAlerts.bind(this);
        this.filterStudents = this.filterStudents.bind(this);
        this.clearSearch = this.clearSearch.bind(this);
        this.handleModalClose = this.handleModalClose.bind(this);
        this.sendWarning = this.sendWarning.bind(this);
        this.flagStudent = this.flagStudent.bind(this);
        this.showStudentActivity = this.showStudentActivity.bind(this);
        this.showFocusView = this.showFocusView.bind(this);
        this.updateExamTimer = this.updateExamTimer.bind(this);
        this.showKeyboardShortcuts = this.showKeyboardShortcuts.bind(this);
        this.handleRetryConnection = this.handleRetryConnection.bind(this);
        
        // Error tracking
        this.consecutiveErrors = 0;
    }
    
    /**
     * Initialize the monitoring dashboard
     */
    async initialize() {
        try {
            // Setup toast notifications
            this.toastContainer = document.getElementById('toastNotifications');
            
            // Update connection status
            this.updateConnectionStatus('connecting');
            
            // Setup event listeners
            this.setupEventListeners();
            
            // Load initial data
            await this.loadActiveStudents();
            await this.loadExamDetails();
            
            // Update connection status
            this.updateConnectionStatus('connected');
            this.consecutiveErrors = 0;
            
            // Start timers
            this.startExamTimer();
            
            // Start auto-refresh if enabled
            const autoRefreshToggle = document.getElementById('autoRefreshToggle');
            if (autoRefreshToggle && autoRefreshToggle.checked) {
                this.startAutoRefresh();
            }
            
            // Apply initial view
            this.applyViewMode(this.currentView);
            
            // Setup checkAgainBtn for empty state
            const checkAgainBtn = document.getElementById('checkAgainBtn');
            if (checkAgainBtn) {
                checkAgainBtn.addEventListener('click', this.refreshStreams);
            }
            
        } catch (error) {
            console.error('Error initializing dashboard:', error);
            this.updateConnectionStatus('error');
            this.showToast('Failed to initialize monitoring dashboard. Please check your connection.', 'error');
            this.consecutiveErrors++;
            
            if (this.consecutiveErrors > 2) {
                this.showConnectionError();
            }
        }
    }
    
    /**
     * Load exam details including end time
     */
    async loadExamDetails() {
        try {
            const response = await fetch(`/monitoring/api/exam/${this.examId}/details/`, {
                headers: {
                    'X-CSRFToken': this.csrfToken,
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'same-origin'
            });
            
            if (!response.ok) {
                throw new Error(`Failed to load exam details: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Look for end_time in the response, with fallback to ensure backwards compatibility
            if (data.end_time) {
                this.examEndTime = new Date(data.end_time);
                this.updateExamTimer();
            } else {
                // If we don't have an end_time directly, try to calculate it from other fields
                console.log("No direct end_time found, attempting to calculate from other fields");
                
                // Try to use start_time and duration if available
                if (data.start_time && data.duration) {
                    const startTime = new Date(data.start_time);
                    
                    // Parse duration (format: "HH:MM:SS" or similar)
                    let durationMs = 0;
                    if (typeof data.duration === 'string') {
                        const durationParts = data.duration.split(':');
                        if (durationParts.length === 3) {
                            // Format is likely "HH:MM:SS"
                            const hours = parseInt(durationParts[0], 10);
                            const minutes = parseInt(durationParts[1], 10);
                            const seconds = parseInt(durationParts[2], 10);
                            durationMs = (hours * 60 * 60 + minutes * 60 + seconds) * 1000;
                        } else {
                            // Try to parse as minutes
                            durationMs = parseInt(data.duration, 10) * 60 * 1000;
                        }
                    } else if (typeof data.duration === 'number') {
                        // Assume duration is in minutes
                        durationMs = data.duration * 60 * 1000;
                    }
                    
                    if (durationMs > 0) {
                        this.examEndTime = new Date(startTime.getTime() + durationMs);
                        this.updateExamTimer();
                    }
                }
                
                // If we still don't have an end time, set a default (2 hours from now)
                if (!this.examEndTime) {
                    console.warn("Could not determine exam end time from API response, using fallback");
                    this.examEndTime = new Date(Date.now() + 2 * 60 * 60 * 1000); // 2 hours from now
                    this.updateExamTimer();
                }
            }
            
            // Update exam name and other details if available
            if (data.name && this.examName) {
                this.examName.textContent = data.name;
            }
            
            // Update exam metadata in the header
            const examDate = document.querySelector('.meta-item .exam-date');
            const examTime = document.querySelector('.meta-item .exam-time');
            const examDuration = document.querySelector('.meta-item .exam-duration');
            
            if (examDate && data.date) {
                examDate.textContent = new Date(data.date).toLocaleDateString();
            }
            
            if (examTime && data.time) {
                examTime.textContent = data.time;
            }
            
            if (examDuration && data.duration) {
                examDuration.textContent = data.duration;
            }
            
        } catch (error) {
            console.error('Error loading exam details:', error);
            this.showToast('Failed to load exam details. Using default exam timer.', 'warning');
            
            // Set a default end time (2 hours from now) so the UI doesn't break
            this.examEndTime = new Date(Date.now() + 2 * 60 * 60 * 1000);
            this.updateExamTimer();
        }
    }
    
    /**
     * Start exam countdown timer
     */
    startExamTimer() {
        if (this.examTimerInterval) {
            clearInterval(this.examTimerInterval);
        }
        
        this.examTimerInterval = setInterval(this.updateExamTimer, 1000);
    }
    
    /**
     * Update exam countdown timer
     */
    updateExamTimer() {
        if (!this.examEndTime || !this.examTimeRemaining) return;
        
        const now = new Date();
        const timeRemaining = this.examEndTime - now;
        
        if (timeRemaining <= 0) {
            this.examTimeRemaining.textContent = "Exam Ended";
            this.examTimeRemaining.classList.add('critical');
            clearInterval(this.examTimerInterval);
            return;
        }
        
        // Format time remaining
        const hours = Math.floor(timeRemaining / (1000 * 60 * 60));
        const minutes = Math.floor((timeRemaining % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((timeRemaining % (1000 * 60)) / 1000);
        
        const formattedTime = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        this.examTimeRemaining.textContent = formattedTime;
        
        // Add warning classes for low time
        this.examTimeRemaining.classList.remove('warning', 'critical');
        if (timeRemaining < 5 * 60 * 1000) { // Less than 5 minutes
            this.examTimeRemaining.classList.add('critical');
        } else if (timeRemaining < 15 * 60 * 1000) { // Less than 15 minutes
            this.examTimeRemaining.classList.add('warning');
        }
    }
    
    /**
     * Show connection error overlay
     */
    showConnectionError() {
        if (this.connectionErrorOverlay) {
            this.connectionErrorOverlay.classList.remove('hidden');
        }
    }
    
    /**
     * Hide connection error overlay
     */
    hideConnectionError() {
        if (this.connectionErrorOverlay) {
            this.connectionErrorOverlay.classList.add('hidden');
        }
    }
    
    /**
     * Handle retry connection button click
     */
    async handleRetryConnection() {
        this.hideConnectionError();
        this.updateConnectionStatus('connecting');
        this.showToast('Retrying connection...', 'info');
        
        try {
            await this.refreshStreams();
            this.consecutiveErrors = 0;
        } catch (error) {
            console.error('Error retrying connection:', error);
            this.showToast('Still having trouble connecting. Please check your network.', 'error');
            this.showConnectionError();
        }
    }
    
    /**
     * Show keyboard shortcuts modal
     */
    showKeyboardShortcuts() {
        if (this.shortcutsModal) {
            this.shortcutsModal.style.display = 'block';
        }
    }
    
    /**
     * Set up all event listeners
     */
    setupEventListeners() {
        // Search functionality
        if (this.studentSearch) {
            this.studentSearch.addEventListener('input', this.searchStudents);
        }
        
        if (this.clearSearchBtn) {
            this.clearSearchBtn.addEventListener('click', this.clearSearch);
        }
        
        // Alert filtering
        if (this.alertFilter) {
            this.alertFilter.addEventListener('change', this.filterAlerts);
        }
        
        // Clear all alerts button
        const clearAllAlertsBtn = document.getElementById('clearAllAlertsBtn');
        if (clearAllAlertsBtn) {
            clearAllAlertsBtn.addEventListener('click', () => this.markAllAlertsReviewed());
        }
        
        // Export report button
        const exportReportBtn = document.getElementById('exportReportBtn');
        if (exportReportBtn) {
            exportReportBtn.addEventListener('click', () => this.exportReport());
        }
        
        // Modal close buttons
        document.querySelectorAll('.close-modal').forEach(btn => {
            btn.addEventListener('click', this.handleModalClose);
        });
        
        // Warning modal buttons
        if (this.warningModal) {
            const sendWarningBtn = document.getElementById('sendWarningBtn');
            const cancelWarningBtn = document.getElementById('cancelWarningBtn');
            
            if (sendWarningBtn) sendWarningBtn.addEventListener('click', this.sendWarning);
            if (cancelWarningBtn) cancelWarningBtn.addEventListener('click', () => this.closeModal(this.warningModal));
        }
        
        // Flag modal buttons
        if (this.flagModal) {
            const submitFlagBtn = document.getElementById('submitFlagBtn');
            const cancelFlagBtn = document.getElementById('cancelFlagBtn');
            
            if (submitFlagBtn) submitFlagBtn.addEventListener('click', this.flagStudent);
            if (cancelFlagBtn) cancelFlagBtn.addEventListener('click', () => this.closeModal(this.flagModal));
        }
        
        // Activity modal buttons
        if (this.activityModal) {
            const closeActivityBtn = document.getElementById('closeActivityBtn');
            const exportActivityBtn = document.getElementById('exportActivityBtn');
            
            if (closeActivityBtn) closeActivityBtn.addEventListener('click', () => this.closeModal(this.activityModal));
            if (exportActivityBtn) exportActivityBtn.addEventListener('click', () => this.exportStudentActivity());
        }
        
        // Focus modal close
        if (this.focusModal) {
            const closeFocusBtn = this.focusModal.querySelector('.close-modal');
            if (closeFocusBtn) {
                closeFocusBtn.addEventListener('click', () => this.closeModal(this.focusModal));
            }
            
            // Focus modal action buttons
            const focusSendWarningBtn = document.getElementById('focusSendWarningBtn');
            const focusFlagBtn = document.getElementById('focusFlagBtn');
            const focusRejectAlertBtn = document.getElementById('focusRejectAlertBtn');
            
            if (focusSendWarningBtn) {
                focusSendWarningBtn.addEventListener('click', () => {
                    const studentId = this.focusModal.dataset.studentId;
                    const studentName = document.getElementById('focusStudentName').textContent;
                    this.openWarningModal(studentId, studentName);
                });
            }
            
            if (focusFlagBtn) {
                focusFlagBtn.addEventListener('click', () => {
                    const studentId = this.focusModal.dataset.studentId;
                    const studentName = document.getElementById('focusStudentName').textContent;
                    this.openFlagModal(studentId, studentName);
                });
            }
            
            if (focusRejectAlertBtn) {
                focusRejectAlertBtn.addEventListener('click', () => {
                    const studentId = this.focusModal.dataset.studentId;
                    const sessionId = this.focusModal.dataset.sessionId;
                    this.rejectCurrentAlert(studentId, sessionId);
                });
            }
        }
        
        // Use event delegation for dynamic elements
        document.addEventListener('click', event => {
            // Focus view button
            if (event.target.closest('.focus-btn')) {
                const card = event.target.closest('.video-card');
                if (card) {
                    const studentId = card.dataset.studentId;
                    const studentName = card.querySelector('.student-name').textContent;
                    this.showFocusView(studentId, studentName);
                }
            }
            
            // Warning button
            if (event.target.closest('.send-warning-btn')) {
                const card = event.target.closest('.video-card');
                if (card) {
                    const studentId = card.dataset.studentId;
                    const studentName = card.querySelector('.student-name').textContent;
                    this.openWarningModal(studentId, studentName);
                }
            }
            
            // Flag button
            if (event.target.closest('.flag-student-btn')) {
                const card = event.target.closest('.video-card');
                if (card) {
                    const studentId = card.dataset.studentId;
                    const studentName = card.querySelector('.student-name').textContent;
                    this.openFlagModal(studentId, studentName);
                }
            }
            
            // History button
            if (event.target.closest('.view-history-btn')) {
                const card = event.target.closest('.video-card');
                if (card) {
                    const sessionId = card.dataset.sessionId;
                    const studentName = card.querySelector('.student-name').textContent;
                    this.showStudentActivity(sessionId, studentName);
                }
            }
            
            // Pause exam button
            if (event.target.closest('.pause-exam-btn')) {
                const card = event.target.closest('.video-card');
                if (card) {
                    const studentId = card.dataset.studentId;
                    const studentName = card.querySelector('.student-name').textContent;
                    this.pauseStudentExam(studentId, studentName);
                }
            }
        });
        
        // Close modals when clicking outside content
        window.addEventListener('click', event => {
            if (event.target.classList.contains('modal')) {
                this.closeModal(event.target);
            }
        });
        
        // Setup keyboard shortcuts
        document.addEventListener('keydown', event => {
            if (event.key === 'Escape') {
                // Close any open modal
                document.querySelectorAll('.modal').forEach(modal => {
                    if (modal.style.display === 'block') {
                        this.closeModal(modal);
                    }
                });
            }
        });
        
        // Student filter
        if (this.studentFilter) {
            this.studentFilter.addEventListener('change', this.filterStudents);
        }
        
        // Shortcuts help button
        const shortcutsHelpBtn = document.getElementById('shortcutsHelpBtn');
        if (shortcutsHelpBtn) {
            shortcutsHelpBtn.addEventListener('click', this.showKeyboardShortcuts);
        }
        
        // Close shortcuts modal
        const closeShortcutsBtn = document.getElementById('closeShortcutsBtn');
        if (closeShortcutsBtn) {
            closeShortcutsBtn.addEventListener('click', () => this.closeModal(this.shortcutsModal));
        }
        
        // Retry connection button
        const retryConnectionBtn = document.getElementById('retryConnectionBtn');
        if (retryConnectionBtn) {
            retryConnectionBtn.addEventListener('click', this.handleRetryConnection);
        }
        
        // Enable clicking on alerts to focus on student
        document.addEventListener('click', event => {
            const alertItem = event.target.closest('.alert-item');
            if (alertItem && alertItem.dataset.sessionId) {
                const sessionId = alertItem.dataset.sessionId;
                const studentId = alertItem.dataset.studentId;
                const studentName = alertItem.querySelector('.alert-student')?.textContent;
                
                // Remove focus from any previously focused alert
                document.querySelectorAll('.alert-item.focused').forEach(el => {
                    el.classList.remove('focused');
                });
                
                // Add focus to clicked alert
                alertItem.classList.add('focused');
                
                // Find the corresponding student card
                const studentCard = this.videoGrid.querySelector(`.video-card[data-session-id="${sessionId}"]`);
                if (studentCard) {
                    // Scroll to the student card
                    studentCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    
                    // Add highlight effect to the card
                    studentCard.classList.add('highlight-pulse');
                    setTimeout(() => {
                        studentCard.classList.remove('highlight-pulse');
                    }, 2000);
                }
                
                // If student name is present, show focus view
                if (studentName && studentId) {
                    this.showFocusView(studentId, studentName);
                }
            }
        });
    }
    
    /**
     * Filter students by status
     */
    filterStudents() {
        if (!this.studentFilter || !this.videoGrid) return;
        
        const filterValue = this.studentFilter.value;
        this.currentStudentFilter = filterValue;
        
        const cards = this.videoGrid.querySelectorAll('.video-card');
        let visibleCount = 0;
        
        cards.forEach(card => {
            let show = false;
            
            switch (filterValue) {
                case 'all':
                    show = true;
                    break;
                case 'active':
                    show = !card.classList.contains('disconnected');
                    break;
                case 'disconnected':
                    show = card.classList.contains('disconnected');
                    break;
                case 'flagged':
                    show = card.classList.contains('alert-critical') || 
                           card.classList.contains('alert-warning');
                    break;
            }
            
            // Also apply search filter if there's an active search
            if (show && this.searchQuery) {
                const studentName = card.querySelector('.student-name').textContent.toLowerCase();
                show = studentName.includes(this.searchQuery.toLowerCase());
            }
            
            card.style.display = show ? '' : 'none';
            
            if (show) {
                visibleCount++;
            }
        });
        
        // Show empty state if no students match the filter
        if (visibleCount === 0) {
            if (this.emptyState) {
                this.emptyState.style.display = 'flex';
                let message = 'No students match the current filter';
                
                if (this.searchQuery) {
                    message += ` and search "${this.searchQuery}"`;
                }
                
                this.emptyState.innerHTML = `
                    <i class="fas fa-filter" aria-hidden="true"></i>
                    <p>${message}</p>
                    <button id="clearFiltersBtn" class="btn btn-secondary">Clear Filters</button>
                `;
                
                // Add event listener to clear button
                document.getElementById('clearFiltersBtn')?.addEventListener('click', () => {
                    // Reset student filter
                    if (this.studentFilter) {
                        this.studentFilter.value = 'all';
                        this.currentStudentFilter = 'all';
                    }
                    
                    // Reset search
                    this.clearSearch();
                    
                    // Apply filters
                    this.filterStudents();
                });
            }
        } else {
            this.hideEmptyState();
        }
    }
    
    /**
     * Load active student sessions for this exam
     */
    async loadActiveStudents() {
        try {
            const response = await fetch(`/monitoring/api/exam/${this.examId}/sessions/`, {
                headers: {
                    'X-CSRFToken': this.csrfToken,
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'same-origin'
            });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Reset error counter since we have a successful response
            this.consecutiveErrors = 0;
            this.hideConnectionError();
            
            // Update dashboard statistics
            if (data.stats) {
                if (this.activeStudentsCount) {
                    this.activeStudentsCount.textContent = data.stats.connected_students;
                }
                
                if (this.totalAlerts) {
                    this.totalAlerts.textContent = data.stats.alert_count;
                }
                
                if (this.flaggedStudents) {
                    this.flaggedStudents.textContent = data.stats.high_severity_count;
                }
                
                if (this.disconnectedStudents) {
                    this.disconnectedStudents.textContent = 
                        data.stats.total_students - data.stats.connected_students;
                }
            }
            
            if (data.sessions.length === 0) {
                this.showEmptyState();
                return;
            }
            
            this.hideEmptyState();
            
            // Keep track of current sessions to detect removed ones
            const currentSessionIds = new Set();
            
            // Create or update student cards
            data.sessions.forEach(session => {
                currentSessionIds.add(session.id.toString());
                this.createOrUpdateStudentCard(session);
            });
            
            // Remove cards for sessions that are no longer active
            this.activeStudents.forEach((data, sessionId) => {
                if (!currentSessionIds.has(sessionId)) {
                    const card = data.element;
                    if (card && card.parentNode) {
                        card.parentNode.removeChild(card);
                    }
                    this.activeStudents.delete(sessionId);
                }
            });
            
            // Clear existing alerts
            if (this.alertsList) {
                // Keep track of existing alerts
                const existingAlerts = new Set(
                    Array.from(this.alertsList.querySelectorAll('.alert-item'))
                        .map(el => el.dataset.alertId)
                );
                
                // Add new alerts that don't already exist
                if (data.alerts && data.alerts.length > 0) {
                    data.alerts.forEach(alert => {
                        if (!existingAlerts.has(alert.id.toString())) {
                            this.addAlert(alert);
                        }
                    });
                    
                    this.hideEmptyAlerts();
                } else if (existingAlerts.size === 0) {
                    this.showEmptyAlerts();
                }
            }
            
            // Apply current search filter
            if (this.searchQuery) {
                this.searchStudents({ target: { value: this.searchQuery } });
            }
            
            // Apply current student filter
            this.filterStudents();
            
            // Apply current alert filter
            this.filterAlerts();
            
            // Update "Mark All as Reviewed" button state
            const clearAllAlertsBtn = document.getElementById('clearAllAlertsBtn');
            if (clearAllAlertsBtn) {
                const alertsExist = this.alertsList && this.alertsList.querySelectorAll('.alert-item').length > 0;
                clearAllAlertsBtn.disabled = !alertsExist;
            }
            
            // Update last refresh time
            this.lastRefreshTime = new Date();
            
        } catch (error) {
            console.error('Error loading active students:', error);
            this.updateConnectionStatus('error');
            this.showToast('Failed to load active students. Will retry automatically.', 'error');
            this.consecutiveErrors++;
            
            if (this.consecutiveErrors > 2) {
                this.showConnectionError();
            }
            
            throw error;
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
            if (!template) {
                console.error('Video card template not found');
                return;
            }
            
            card = template.content.cloneNode(true).querySelector('.video-card');
            card.dataset.sessionId = session.id;
            card.dataset.studentId = session.student_id;
            
            const studentName = card.querySelector('.student-name');
            studentName.textContent = session.student_name || `Student #${session.student_id}`;
            
            this.videoGrid.appendChild(card);
        }
        
        // Update card with latest data
        const isConnected = session.is_connected !== false;
        card.classList.toggle('disconnected', !isConnected);
        
        // Update activity indicator
        const activityIndicator = card.querySelector('.activity-indicator');
        if (activityIndicator) {
            activityIndicator.classList.remove('active', 'inactive', 'disconnected');
            activityIndicator.classList.add(isConnected ? 'active' : 'disconnected');
            activityIndicator.title = isConnected ? 'Active' : 'Disconnected';
        }
        
        // Show/hide connection overlay
        const connectionOverlay = card.querySelector('.connection-overlay');
        if (connectionOverlay) {
            connectionOverlay.classList.toggle('hidden', isConnected);
        }
        
        // Update time active
        const timeActive = card.querySelector('.time-active');
        if (timeActive && session.started_at) {
            const startTime = new Date(session.started_at);
            const duration = this.formatDuration(new Date() - startTime);
            timeActive.textContent = duration;
            timeActive.title = `Active since ${startTime.toLocaleTimeString()}`;
        }
        
        // Update connection status text
        const statusElement = card.querySelector('.connection-status');
        if (statusElement) {
            statusElement.textContent = isConnected ? 'Connected' : 'Disconnected';
            statusElement.classList.toggle('disconnected', !isConnected);
        }
        
        // Fetch latest frame for this session
        this.fetchLatestFrame(session.id, card);
        
        // Store in active students map
        this.activeStudents.set(session.id.toString(), {
            lastUpdate: new Date(),
            element: card,
            data: session
        });
        
        return card;
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
            
            if (response.status === 404) {
                // No frames available yet, but not an error
                return;
            }
            
            if (!response.ok) {
                throw new Error(`Failed to fetch frame for session ${sessionId}`);
            }
            
            const data = await response.json();
            
            if (data.frame_url) {
                const img = card.querySelector('.student-video');
                if (img) {
                    // Add timestamp to prevent caching
                    img.src = `${data.frame_url}?t=${new Date().getTime()}`;
                    
                    // Update connection status
                    const statusElement = card.querySelector('.connection-status');
                    if (statusElement) {
                        statusElement.textContent = data.is_connected ? 'Connected' : 'Disconnected';
                        statusElement.classList.toggle('disconnected', !data.is_connected);
                    }
                    
                    // Update activity indicator
                    const activityIndicator = card.querySelector('.activity-indicator');
                    if (activityIndicator) {
                        activityIndicator.classList.remove('active', 'inactive', 'disconnected');
                        activityIndicator.classList.add(data.is_connected ? 'active' : 'disconnected');
                        activityIndicator.title = data.is_connected ? 'Active' : 'Disconnected';
                    }
                    
                    // Update alert indicator if there are active alerts
                    if (data.has_active_alerts) {
                        const alertIndicator = card.querySelector('.alert-indicator');
                        if (alertIndicator) {
                            alertIndicator.classList.remove('hidden');
                            alertIndicator.querySelector('.alert-text').textContent = 
                                data.alert_count > 1 ? `${data.alert_count} alerts` : '1 alert';
                            
                            // Add alert class to card
                            if (data.latest_alert && data.latest_alert.severity === 'critical') {
                                card.classList.add('alert-critical');
                            } else if (data.latest_alert && data.latest_alert.severity === 'warning') {
                                card.classList.add('alert-warning');
                            } else {
                                card.classList.add('alert-info');
                            }
                        }
                    } else {
                        // Hide alert indicator if no alerts
                        const alertIndicator = card.querySelector('.alert-indicator');
                        if (alertIndicator) {
                            alertIndicator.classList.add('hidden');
                            card.classList.remove('alert-critical', 'alert-warning', 'alert-info');
                        }
                    }
                    
                    // Display activity overlay with latest alert if available
                    if (data.latest_alert) {
                        const overlay = card.querySelector('.activity-overlay');
                        const content = card.querySelector('.overlay-content');
                        if (overlay && content) {
                            overlay.classList.remove('hidden');
                            content.innerHTML = `
                                <div class="alert-overlay ${data.latest_alert.severity}">
                                    <p>${data.latest_alert.description}</p>
                                    <span>${this.formatTime(data.latest_alert.timestamp)}</span>
                                </div>
                            `;
                            
                            // Auto-hide overlay after 5 seconds
                            setTimeout(() => {
                                overlay.classList.add('hidden');
                            }, 5000);
                        }
                    }
                }
            }
        } catch (error) {
            console.error(`Error fetching frame for session ${sessionId}:`, error);
            const statusElement = card.querySelector('.connection-status');
            if (statusElement) {
                statusElement.textContent = 'Error';
                statusElement.classList.add('disconnected');
            }
        }
    }
    
    /**
     * Add an alert to the alerts panel
     */
    addAlert(alert) {
        if (!this.alertsList) return;
        
        const alertElement = document.createElement('div');
        alertElement.className = `alert-item ${alert.severity}`;
        alertElement.dataset.alertId = alert.id;
        alertElement.dataset.studentId = alert.student_id;
        alertElement.dataset.sessionId = alert.session_id;
        
        alertElement.innerHTML = `
            <div class="alert-header">
                <span class="alert-student">${alert.student_name}</span>
                <span class="alert-time">${this.formatTime(alert.timestamp)}</span>
            </div>
            <div class="alert-message">${alert.description}</div>
            <div class="alert-actions">
                <button class="mark-reviewed-btn" data-alert-id="${alert.id}" title="Mark as Reviewed">
                    <i class="fas fa-check" aria-hidden="true"></i> Review
                </button>
                ${alert.has_screenshot ? 
                    `<a href="/monitoring/alert/${alert.id}/screenshot/" 
                       class="view-screenshot-btn" 
                       target="_blank" 
                       title="View Screenshot">
                        <i class="fas fa-image" aria-hidden="true"></i> View
                    </a>` : ''}
                <button class="focus-student-btn" title="Focus on this student">
                    <i class="fas fa-search" aria-hidden="true"></i> Focus
                </button>
            </div>
        `;
        
        // Add event listener for the mark as reviewed button
        alertElement.querySelector('.mark-reviewed-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            this.markAlertReviewed(alert.id, alertElement);
        });
        
        // Add event listener for focus button
        alertElement.querySelector('.focus-student-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            if (alert.student_id && alert.student_name) {
                this.showFocusView(alert.student_id, alert.student_name);
            }
        });
        
        this.alertsList.prepend(alertElement);
        
        // Apply current filter
        this.filterAlertElement(alertElement);
        
        this.updateAlertCounter();
        
        // Show notification for high severity alerts
        if (alert.severity === 'critical') {
            this.showToast(`Critical alert: ${alert.student_name} - ${alert.description}`, 'error');
            
            // Flash the corresponding student card
            const studentCard = this.videoGrid.querySelector(`.video-card[data-student-id="${alert.student_id}"]`);
            if (studentCard) {
                studentCard.classList.add('alert-flash');
                setTimeout(() => {
                    studentCard.classList.remove('alert-flash');
                }, 2000);
            }
        }
    }
    
    /**
     * Mark an alert as reviewed
     */
    async markAlertReviewed(alertId, alertElement) {
        if (!alertElement) {
            alertElement = this.alertsList.querySelector(`.alert-item[data-alert-id="${alertId}"]`);
        }
        
        if (!alertElement) return;
        
        // Add loading state
        alertElement.classList.add('loading');
        const reviewBtn = alertElement.querySelector('.mark-reviewed-btn');
        if (reviewBtn) {
            const originalText = reviewBtn.innerHTML;
            reviewBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
            reviewBtn.disabled = true;
        }
        
        try {
            const response = await fetch(`/monitoring/alert/${alertId}/mark-reviewed/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken,
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            if (!response.ok) {
                throw new Error('Failed to mark alert as reviewed');
            }
            
            // Remove the alert with animation
            alertElement.classList.add('removing');
            setTimeout(() => {
                if (alertElement.parentNode) {
                    alertElement.parentNode.removeChild(alertElement);
                    this.updateAlertCounter();
                    
                    // Show empty alerts message if no alerts left
                    if (this.alertsList.children.length === 0) {
                        this.showEmptyAlerts();
                    }
                }
            }, 300);
        } catch (error) {
            console.error('Error marking alert as reviewed:', error);
            alertElement.classList.remove('loading');
            
            // Restore button
            if (reviewBtn) {
                reviewBtn.innerHTML = '<i class="fas fa-check" aria-hidden="true"></i> Review';
                reviewBtn.disabled = false;
            }
            
            this.showToast('Failed to mark alert as reviewed', 'error');
        }
    }
    
    /**
     * Mark all alerts as reviewed
     */
    async markAllAlertsReviewed() {
        const clearAllBtn = document.getElementById('clearAllAlertsBtn');
        const originalText = clearAllBtn ? clearAllBtn.textContent : 'Clear All Alerts';
        
        if (clearAllBtn) {
            clearAllBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
            clearAllBtn.disabled = true;
        }
        
        try {
            const response = await fetch(`/monitoring/exam/${this.examId}/mark-all-alerts-reviewed/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken,
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            if (!response.ok) {
                throw new Error('Failed to mark all alerts as reviewed');
            }
            
            const data = await response.json();
            
            // Remove all alerts with animation
            const alerts = this.alertsList.querySelectorAll('.alert-item');
            alerts.forEach(alert => {
                alert.classList.add('removing');
            });
            
            // Clear alerts after animation
            setTimeout(() => {
                this.alertsList.innerHTML = '';
                this.updateAlertCounter();
                this.showEmptyAlerts();
                
                // Update button
                if (clearAllBtn) {
                    clearAllBtn.innerHTML = '<i class="fas fa-check"></i> Marked All as Reviewed';
                    setTimeout(() => {
                        clearAllBtn.textContent = originalText;
                        clearAllBtn.disabled = true;
                    }, 2000);
                }
                
                this.showToast(`${data.count} alerts marked as reviewed`, 'success');
            }, 300);
            
        } catch (error) {
            console.error('Error marking all alerts as reviewed:', error);
            
            // Restore button
            if (clearAllBtn) {
                clearAllBtn.textContent = originalText;
                clearAllBtn.disabled = false;
            }
            
            this.showToast('Failed to mark all alerts as reviewed', 'error');
        }
    }
    
    /**
     * Update the alert counter badge
     */
    updateAlertCounter() {
        if (!this.alertCounter) return;
        
        const visibleAlerts = this.getVisibleAlertCount();
        this.alertCounter.textContent = visibleAlerts;
        
        // Update button state
        const clearAllAlertsBtn = document.getElementById('clearAllAlertsBtn');
        if (clearAllAlertsBtn) {
            clearAllAlertsBtn.disabled = visibleAlerts === 0;
        }
    }
    
    /**
     * Get count of visible alerts based on current filter
     */
    getVisibleAlertCount() {
        if (!this.alertsList) return 0;
        
        const alerts = this.alertsList.querySelectorAll('.alert-item');
        let count = 0;
        
        alerts.forEach(alert => {
            if (alert.style.display !== 'none') {
                count++;
            }
        });
        
        return count;
    }
    
    /**
     * Filter alerts based on selected severity
     */
    filterAlerts() {
        if (!this.alertFilter || !this.alertsList) return;
        
        const severity = this.alertFilter.value;
        this.currentFilter = severity;
        
        const alerts = this.alertsList.querySelectorAll('.alert-item');
        let visibleCount = 0;
        
        alerts.forEach(alert => {
            this.filterAlertElement(alert);
            
            if (alert.style.display !== 'none') {
                visibleCount++;
            }
        });
        
        // Show/hide empty alerts message
        if (visibleCount === 0) {
            this.showEmptyAlerts();
        } else {
            this.hideEmptyAlerts();
        }
        
        this.updateAlertCounter();
    }
    
    /**
     * Filter a single alert element based on current filter
     */
    filterAlertElement(alertElement) {
        if (!alertElement) return;
        
        const alertSeverity = Array.from(alertElement.classList)
            .find(cls => ['high', 'medium', 'low', 'critical', 'warning', 'info'].includes(cls));
        
        // Map alert severities
        const severityMap = {
            'critical': 'high',
            'warning': 'medium',
            'info': 'low'
        };
        
        const mappedSeverity = severityMap[alertSeverity] || alertSeverity;
        
        if (this.currentFilter === 'all' || this.currentFilter === mappedSeverity) {
            alertElement.style.display = '';
        } else {
            alertElement.style.display = 'none';
        }
    }
    
    /**
     * Search students by name
     */
    searchStudents(event) {
        if (!event || !event.target) return;
        
        const query = event.target.value.toLowerCase().trim();
        this.searchQuery = query;
        
        if (!this.videoGrid) return;
        
        // Apply both search query and current filter
        this.filterStudents();
        
        // Toggle clear search button
        if (this.clearSearchBtn) {
            this.clearSearchBtn.style.display = query ? 'block' : 'none';
        }
    }
    
    /**
     * Clear the search input
     */
    clearSearch() {
        if (this.studentSearch) {
            this.studentSearch.value = '';
            this.searchQuery = '';
            this.searchStudents({ target: this.studentSearch });
        }
    }
    
    /**
     * Show empty state when no active students
     */
    showEmptyState() {
        if (this.emptyState) {
            this.emptyState.style.display = 'flex';
            this.emptyState.innerHTML = `
                <i class="fas fa-video-slash" aria-hidden="true"></i>
                <p>No active student streams</p>
                <button id="checkAgainBtn" class="btn btn-primary">Check Again</button>
                <p class="empty-note">Students will appear here when they connect to the exam</p>
            `;
            
            // Add event listener to the new button
            document.getElementById('checkAgainBtn')?.addEventListener('click', this.refreshStreams);
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
     * Show empty alerts message
     */
    showEmptyAlerts() {
        if (this.emptyAlerts) {
            this.emptyAlerts.style.display = 'block';
        }
    }
    
    /**
     * Hide empty alerts message
     */
    hideEmptyAlerts() {
        if (this.emptyAlerts) {
            this.emptyAlerts.style.display = 'none';
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
     * Format duration for display
     */
    formatDuration(milliseconds) {
        const seconds = Math.floor(milliseconds / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        
        if (hours > 0) {
            return `${hours}h ${minutes % 60}m`;
        } else if (minutes > 0) {
            return `${minutes}m ${seconds % 60}s`;
        } else {
            return `${seconds}s`;
        }
    }
    
    /**
     * Update connection status indicator
     */
    updateConnectionStatus(status) {
        if (!this.connectionStatus) return;
        
        this.connectionStatus.classList.remove('connected', 'connecting', 'disconnected');
        
        if (status === 'connected') {
            this.connectionStatus.textContent = 'Connected';
            this.connectionStatus.classList.add('connected');
        } else if (status === 'connecting') {
            this.connectionStatus.textContent = 'Connecting...';
            this.connectionStatus.classList.add('connecting');
        } else if (status === 'refreshing') {
            this.connectionStatus.textContent = 'Refreshing...';
            this.connectionStatus.classList.add('connecting');
        } else {
            this.connectionStatus.textContent = 'Connection Error';
            this.connectionStatus.classList.add('disconnected');
        }
    }
    
    /**
     * Show a toast notification
     */
    showToast(message, type = 'info') {
        if (!this.toastContainer) return;
        
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        // Add icon based on type
        let icon = 'info-circle';
        if (type === 'success') icon = 'check-circle';
        if (type === 'error') icon = 'exclamation-triangle';
        if (type === 'warning') icon = 'exclamation-circle';
        
        toast.innerHTML = `
            <div class="toast-icon">
                <i class="fas fa-${icon}" aria-hidden="true"></i>
            </div>
            <div class="toast-content">${message}</div>
            <button class="toast-close" aria-label="Close notification">
                <i class="fas fa-times" aria-hidden="true"></i>
            </button>
        `;
        
        // Add close button functionality
        toast.querySelector('.toast-close').addEventListener('click', () => {
            this.removeToast(toast);
        });
        
        // Add to container
        this.toastContainer.appendChild(toast);
        
        // Animate in
        setTimeout(() => {
            toast.classList.add('show');
        }, 10);
        
        // Auto-remove after 5 seconds for non-error toasts
        if (type !== 'error') {
            setTimeout(() => {
                this.removeToast(toast);
            }, 5000);
        }
    }
    
    /**
     * Remove a toast notification with animation
     */
    removeToast(toast) {
        toast.classList.remove('show');
        toast.classList.add('hide');
        
        // Remove from DOM after animation
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }
    
    /**
     * Open the warning modal for a student
     */
    openWarningModal(studentId, studentName) {
        if (!this.warningModal) return;
        
        // Set student info in modal
        this.warningModal.dataset.studentId = studentId;
        document.getElementById('warningStudentName').textContent = studentName;
        
        // Reset form
        const warningSelect = document.getElementById('warningMessageSelect');
        const customWarningContainer = document.getElementById('customWarningContainer');
        const customWarningMessage = document.getElementById('customWarningMessage');
        
        if (warningSelect) {
            warningSelect.value = warningSelect.options[0].value;
        }
        
        if (customWarningContainer) {
            customWarningContainer.style.display = 'none';
        }
        
        if (customWarningMessage) {
            customWarningMessage.value = '';
        }
        
        // Show modal
        this.warningModal.style.display = 'block';
    }
    
    /**
     * Open the flag modal for a student
     */
    openFlagModal(studentId, studentName) {
        if (!this.flagModal) return;
        
        // Set student info in modal
        this.flagModal.dataset.studentId = studentId;
        document.getElementById('flagStudentName').textContent = studentName;
        
        // Reset form
        const flagSelect = document.getElementById('flagReasonSelect');
        const customFlagContainer = document.getElementById('customFlagContainer');
        const customFlagReason = document.getElementById('customFlagReason');
        
        if (flagSelect) {
            flagSelect.value = flagSelect.options[0].value;
        }
        
        if (customFlagContainer) {
            customFlagContainer.style.display = 'none';
        }
        
        if (customFlagReason) {
            customFlagReason.value = '';
        }
        
        // Reset severity
        const severityRadios = document.querySelectorAll('input[name="flagSeverity"]');
        if (severityRadios.length > 0) {
            severityRadios[0].checked = true;
        }
        
        // Show modal
        this.flagModal.style.display = 'block';
    }
    
    /**
     * Show student activity history in modal
     */
    async showStudentActivity(sessionId, studentName) {
        if (!this.activityModal) return;
        
        // Set student info in modal
        document.getElementById('activityStudentName').textContent = studentName;
        this.activityModal.dataset.sessionId = sessionId;
        
        // Show loading state
        const timelineContainer = this.activityModal.querySelector('.timeline-container');
        if (timelineContainer) {
            timelineContainer.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading activity data...</div>';
        }
        
        // Show modal while loading
        this.activityModal.style.display = 'block';
        
        try {
            // Get activity time range
            const timeRange = document.getElementById('activityTimeRange').value || 10;
            
            // Fetch activity data
            const response = await fetch(`/monitoring/api/session/${sessionId}/activity/?minutes=${timeRange}`, {
                headers: {
                    'X-CSRFToken': this.csrfToken
                }
            });
            
            if (!response.ok) {
                throw new Error('Failed to fetch activity data');
            }
            
            const data = await response.json();
            
            // Build timeline HTML
            let timelineHTML = '';
            
            // Add alerts to timeline
            if (data.alerts && data.alerts.length > 0) {
                const alertTemplate = alertData => `
                    <div class="timeline-item alert-item ${alertData.severity}">
                        <div class="timeline-time">${this.formatTime(alertData.timestamp)}</div>
                        <div class="timeline-content">
                            <div class="timeline-title">
                                <span class="alert-type">${alertData.type}</span>
                                <span class="alert-status ${alertData.is_reviewed ? 'reviewed' : ''}">
                                    ${alertData.is_reviewed ? 'Reviewed' : 'Unreviewed'}
                                </span>
                            </div>
                            <div class="timeline-description">${alertData.description}</div>
                        </div>
                    </div>
                `;
                
                timelineHTML += data.alerts.map(alertTemplate).join('');
            }
            
            // Add selected frames to timeline
            if (data.frames && data.frames.length > 0) {
                // Select a subset of frames (every 5th) to avoid cluttering the timeline
                const selectedFrames = data.frames.filter((_, index) => index % 5 === 0);
                
                const frameTemplate = frameData => `
                    <div class="timeline-item frame-item">
                        <div class="timeline-time">${this.formatTime(frameData.timestamp)}</div>
                        <div class="timeline-content">
                            <div class="timeline-image">
                                <img src="${frameData.url}" alt="Webcam frame at ${this.formatTime(frameData.timestamp)}" />
                            </div>
                        </div>
                    </div>
                `;
                
                timelineHTML += selectedFrames.map(frameTemplate).join('');
            }
            
            if (timelineHTML === '') {
                timelineHTML = '<div class="empty-timeline-message">No activity recorded in the selected time range</div>';
            }
            
            // Update timeline
            if (timelineContainer) {
                timelineContainer.innerHTML = timelineHTML;
            }
            
        } catch (error) {
            console.error('Error fetching activity data:', error);
            
            if (timelineContainer) {
                timelineContainer.innerHTML = `
                    <div class="error-message">
                        <i class="fas fa-exclamation-circle"></i>
                        <p>Failed to load activity data. Please try again.</p>
                    </div>
                `;
            }
            
            this.showToast('Failed to load student activity data', 'error');
        }
    }
    
    /**
     * Show focus view of a student
     */
    showFocusView(studentId, studentName) {
        if (!this.focusModal) return;
        
        // Find the student session card
        const card = this.videoGrid.querySelector(`.video-card[data-student-id="${studentId}"]`);
        if (!card) return;
        
        // Get session data
        const sessionId = card.dataset.sessionId;
        const sessionData = this.activeStudents.get(sessionId)?.data;
        if (!sessionData) return;
        
        // Set student info in modal
        this.focusModal.dataset.studentId = studentId;
        this.focusModal.dataset.sessionId = sessionId;
        document.getElementById('focusStudentName').textContent = studentName;
        
        // Get the latest image and set it in focus view
        const img = card.querySelector('.student-video');
        const focusVideo = document.getElementById('focusVideo');
        
        if (img && focusVideo && img.src) {
            focusVideo.src = img.src;
        }
        
        // Set status info
        const focusStatus = document.getElementById('focusStatus');
        const focusTimeActive = document.getElementById('focusTimeActive');
        const focusAlerts = document.getElementById('focusAlerts');
        
        if (focusStatus) {
            const isConnected = !card.classList.contains('disconnected');
            focusStatus.textContent = isConnected ? 'Connected' : 'Disconnected';
            focusStatus.className = `data-value ${isConnected ? 'connected' : 'disconnected'}`;
        }
        
        if (focusTimeActive && sessionData.started_at) {
            const startTime = new Date(sessionData.started_at);
            const duration = this.formatDuration(new Date() - startTime);
            focusTimeActive.textContent = duration;
        }
        
        // Count alerts for this student
        const alertCount = document.querySelectorAll(`.alert-item[data-student-id="${studentId}"]`).length;
        if (focusAlerts) {
            focusAlerts.textContent = alertCount;
        }
        
        // Show modal
        this.focusModal.style.display = 'block';
        
        // Fetch additional data for the focus view
        this.fetchFocusData(sessionId);
    }
    
    /**
     * Fetch additional data for focus view
     */
    async fetchFocusData(sessionId) {
        try {
            // Get mini timeline container
            const miniTimeline = document.getElementById('focusMiniTimeline');
            if (!miniTimeline) return;
            
            miniTimeline.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading...</div>';
            
            // Fetch recent activity
            const response = await fetch(`/monitoring/api/session/${sessionId}/activity/?minutes=10`, {
                headers: {
                    'X-CSRFToken': this.csrfToken
                }
            });
            
            if (!response.ok) {
                throw new Error('Failed to fetch activity data');
            }
            
            const data = await response.json();
            
            // Build mini timeline
            let timelineHTML = '<h4>Recent Activity</h4>';
            
            // Add recent alerts
            if (data.alerts && data.alerts.length > 0) {
                timelineHTML += '<ul class="mini-timeline">';
                
                data.alerts.slice(0, 5).forEach(alert => {
                    timelineHTML += `
                        <li class="mini-timeline-item ${alert.severity}">
                            <span class="mini-time">${this.formatTime(alert.timestamp)}</span>
                            <span class="mini-content">${alert.description}</span>
                        </li>
                    `;
                });
                
                timelineHTML += '</ul>';
            } else {
                timelineHTML += '<p class="no-activity">No recent alerts</p>';
            }
            
            miniTimeline.innerHTML = timelineHTML;
            
        } catch (error) {
            console.error('Error fetching focus data:', error);
            
            const miniTimeline = document.getElementById('focusMiniTimeline');
            if (miniTimeline) {
                miniTimeline.innerHTML = '<p class="error">Failed to load recent activity</p>';
            }
        }
    }
    
    /**
     * Send a warning message to a student
     */
    async sendWarning() {
        if (!this.warningModal) return;
        
        const studentId = this.warningModal.dataset.studentId;
        
        // Get the session ID correctly from the card's dataset
        const card = this.videoGrid.querySelector(`.video-card[data-student-id="${studentId}"]`);
        if (!card) {
            this.showToast('Could not identify student card', 'error');
            return;
        }
        
        const sessionId = card.dataset.sessionId;
        
        if (!sessionId) {
            this.showToast('Could not identify student session', 'error');
            return;
        }
        
        const warningSelect = document.getElementById('warningMessageSelect');
        const customWarningMessage = document.getElementById('customWarningMessage');
        const priorityRadios = document.querySelectorAll('input[name="warningPriority"]');
        
        let message = '';
        if (warningSelect.value === 'custom') {
            message = customWarningMessage.value.trim();
            if (!message) {
                this.showToast('Please enter a custom warning message', 'error');
                return;
            }
        } else {
            message = warningSelect.value;
        }
        
        // Get selected priority
        let priority = 'normal';
        priorityRadios.forEach(radio => {
            if (radio.checked) {
                priority = radio.value;
            }
        });
        
        // Disable form elements
        const sendWarningBtn = document.getElementById('sendWarningBtn');
        const cancelWarningBtn = document.getElementById('cancelWarningBtn');
        
        if (sendWarningBtn) sendWarningBtn.disabled = true;
        if (cancelWarningBtn) cancelWarningBtn.disabled = true;
        if (sendWarningBtn) sendWarningBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Sending...';
        
        try {
            const response = await fetch(`/monitoring/api/session/${sessionId}/send-warning/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message,
                    priority
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to send warning');
            }
            
            const data = await response.json();
            
            // Show success message
            this.showToast(`Warning sent to student`, 'success');
            
            // Close modal
            this.closeModal(this.warningModal);
            
        } catch (error) {
            console.error('Error sending warning:', error);
            
            // Re-enable form elements
            if (sendWarningBtn) {
                sendWarningBtn.disabled = false;
                sendWarningBtn.innerHTML = 'Send Warning';
            }
            
            if (cancelWarningBtn) {
                cancelWarningBtn.disabled = false;
            }
            
            this.showToast('Failed to send warning', 'error');
        }
    }
    
    /**
     * Flag a student for review
     */
    async flagStudent() {
        if (!this.flagModal) return;
        
        const studentId = this.flagModal.dataset.studentId;
        
        // Get the session ID correctly - use the card's dataset instead
        const card = this.videoGrid.querySelector(`.video-card[data-student-id="${studentId}"]`);
        if (!card) {
            this.showToast('Could not identify student card', 'error');
            return;
        }
        
        const sessionId = card.dataset.sessionId;
        
        if (!sessionId) {
            this.showToast('Could not identify student session', 'error');
            return;
        }
        
        const flagSelect = document.getElementById('flagReasonSelect');
        const customFlagReason = document.getElementById('customFlagReason');
        const severityRadios = document.querySelectorAll('input[name="flagSeverity"]');
        const includeScreenshot = document.getElementById('includeScreenshot');
        
        let reason = '';
        if (flagSelect.value === 'custom') {
            reason = customFlagReason.value.trim();
            if (!reason) {
                this.showToast('Please enter a custom flag reason', 'error');
                return;
            }
        } else {
            reason = flagSelect.value;
        }
        
        // Get selected severity
        let severity = 'medium';
        severityRadios.forEach(radio => {
            if (radio.checked) {
                severity = radio.value;
            }
        });
        
        // Disable form elements
        const submitFlagBtn = document.getElementById('submitFlagBtn');
        const cancelFlagBtn = document.getElementById('cancelFlagBtn');
        
        if (submitFlagBtn) submitFlagBtn.disabled = true;
        if (cancelFlagBtn) cancelFlagBtn.disabled = true;
        if (submitFlagBtn) submitFlagBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting...';
        
        try {
            const response = await fetch(`/monitoring/api/session/${sessionId}/flag-student/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    reason,
                    severity,
                    include_screenshot: includeScreenshot ? includeScreenshot.checked : true
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to flag student');
            }
            
            const data = await response.json();
            
            // Update flagged students count
            if (this.flaggedStudents) {
                const currentCount = parseInt(this.flaggedStudents.textContent) || 0;
                this.flaggedStudents.textContent = currentCount + 1;
            }
            
            // Show success message
            this.showToast(`Student has been flagged for review`, 'success');
            
            // Close modal
            this.closeModal(this.flagModal);
            
            // Refresh to show the new alert
            this.refreshStreams();
            
        } catch (error) {
            console.error('Error flagging student:', error);
            
            // Re-enable form elements
            if (submitFlagBtn) {
                submitFlagBtn.disabled = false;
                submitFlagBtn.innerHTML = 'Submit Flag';
            }
            
            if (cancelFlagBtn) {
                cancelFlagBtn.disabled = false;
            }
            
            this.showToast('Failed to flag student', 'error');
        }
    }
    
    /**
     * Pause a student's exam (sends them a pause notification)
     */
    async pauseStudentExam(studentId, studentName) {
        const sessionId = this.activeStudents.get(studentId)?.element?.dataset.sessionId;
        
        if (!sessionId) {
            this.showToast('Could not identify student session', 'error');
            return;
        }
        
        if (!confirm(`Are you sure you want to pause the exam for ${studentName}? The student will be notified and their exam session will be temporarily frozen.`)) {
            return;
        }
        
        // Find and update the pause button
        const card = this.videoGrid.querySelector(`.video-card[data-student-id="${studentId}"]`);
        const pauseBtn = card?.querySelector('.pause-exam-btn');
        
        if (pauseBtn) {
            const originalHTML = pauseBtn.innerHTML;
            pauseBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            pauseBtn.disabled = true;
        }
        
        try {
            const response = await fetch(`/monitoring/api/session/${sessionId}/pause-exam/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken,
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                throw new Error('Failed to pause exam');
            }
            
            // Update button to resume
            if (pauseBtn) {
                pauseBtn.innerHTML = '<i class="fas fa-play"></i>';
                pauseBtn.title = 'Resume Exam';
                pauseBtn.disabled = false;
                pauseBtn.classList.remove('pause-exam-btn');
                pauseBtn.classList.add('resume-exam-btn');
            }
            
            if (card) {
                card.classList.add('paused');
            }
            
            this.showToast(`Exam paused for ${studentName}`, 'success');
            
        } catch (error) {
            console.error('Error pausing exam:', error);
            
            // Reset button
            if (pauseBtn) {
                pauseBtn.innerHTML = '<i class="fas fa-pause"></i>';
                pauseBtn.disabled = false;
            }
            
            this.showToast(`Failed to pause exam for ${studentName}`, 'error');
        }
    }
    
    /**
     * Export monitoring report
     */
    exportReport() {
        const url = `/monitoring/exam/${this.examId}/export-data/`;
        window.open(url, '_blank');
    }
    
    /**
     * Export student activity data
     */
    exportStudentActivity() {
        const sessionId = this.activityModal?.dataset.sessionId;
        if (!sessionId) return;
        
        const url = `/monitoring/session/${sessionId}/export-activity/`;
        window.open(url, '_blank');
    }
    
    /**
     * Show full screen view of student video
     */
    applyViewMode(viewMode) {
        if (!this.videoGrid) return;
        
        // Save preference
        this.currentView = viewMode;
        localStorage.setItem('examMonitorView', viewMode);
        
        // Apply class to video grid
        this.videoGrid.classList.remove('grid-view', 'list-view');
        this.videoGrid.classList.add(`${viewMode}-view`);
        
        // Update buttons
        const gridViewBtn = document.getElementById('gridViewBtn');
        const listViewBtn = document.getElementById('listViewBtn');
        
        if (gridViewBtn) {
            gridViewBtn.classList.toggle('active', viewMode === 'grid');
        }
        
        if (listViewBtn) {
            listViewBtn.classList.toggle('active', viewMode === 'list');
        }
    }
    
    /**
     * Generic modal close handler
     */
    handleModalClose(event) {
        const modal = event.target.closest('.modal');
        if (modal) {
            this.closeModal(modal);
        }
    }
    
    /**
     * Close a specific modal
     */
    closeModal(modal) {
        if (!modal) return;
        modal.style.display = 'none';
        
        // Reset any loading state in buttons
        const buttons = modal.querySelectorAll('button');
        buttons.forEach(btn => {
            btn.disabled = false;
            if (btn.classList.contains('btn-warning')) {
                btn.innerHTML = '<i class="fas fa-exclamation-circle" aria-hidden="true"></i> Send Warning';
            } else if (btn.classList.contains('btn-danger')) {
                btn.innerHTML = '<i class="fas fa-flag" aria-hidden="true"></i> Submit Flag';
            }
        });
    }
    
    /**
     * Focus on a specific student
     */
    focusStudent(studentId) {
        const studentData = this.activeStudents.get(studentId);
        if (!studentData) return;
        
        const card = studentData.element;
        if (card) {
            const studentName = card.querySelector('.student-name').textContent;
            this.showFocusView(studentId, studentName);
        }
    }
    
    /**
     * Start checking for inactive students
     */
    startInactiveCheck() {
        // Check every 30 seconds for inactive students
        this.inactiveCheckInterval = setInterval(() => this.checkInactiveStudents(), 30000);
    }
    
    /**
     * Start auto-refresh interval
     */
    startAutoRefresh() {
        // Auto refresh every 2 minutes
        this.autoRefreshInterval = setInterval(() => {
            const autoRefreshToggle = document.getElementById('autoRefreshToggle');
            if (autoRefreshToggle && autoRefreshToggle.checked) {
                this.refreshStreams();
            }
        }, 120000);
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
                
                // Update activity indicator
                const activityIndicator = card.querySelector('.activity-indicator');
                if (activityIndicator) {
                    activityIndicator.classList.remove('active', 'inactive');
                    activityIndicator.classList.add('disconnected');
                    activityIndicator.title = 'Disconnected';
                }
            }
        });
    }
    
    /**
     * Refresh all student streams
     */
    async refreshStreams() {
        if (this.isRefreshing) return;
        
        this.isRefreshing = true;
        this.updateConnectionStatus('refreshing');
        
        const refreshBtn = document.getElementById('refreshStreamsBtn');
        if (refreshBtn) {
            const originalHTML = refreshBtn.innerHTML;
            refreshBtn.innerHTML = '<i class="fas fa-sync fa-spin" aria-hidden="true"></i> Refreshing...';
            refreshBtn.disabled = true;
        }
        
        try {
            await this.loadActiveStudents();
            this.updateConnectionStatus('connected');
            
            if (refreshBtn) {
                refreshBtn.innerHTML = '<i class="fas fa-check" aria-hidden="true"></i> Refreshed';
                setTimeout(() => {
                    refreshBtn.innerHTML = '<i class="fas fa-sync" aria-hidden="true"></i> Refresh Streams';
                    refreshBtn.disabled = false;
                }, 1000);
            }
        } catch (error) {
            console.error('Error refreshing streams:', error);
            this.updateConnectionStatus('error');
            
            if (refreshBtn) {
                refreshBtn.innerHTML = '<i class="fas fa-exclamation-triangle" aria-hidden="true"></i> Failed';
                setTimeout(() => {
                    refreshBtn.innerHTML = '<i class="fas fa-sync" aria-hidden="true"></i> Refresh Streams';
                    refreshBtn.disabled = false;
                }, 1000);
            }
        } finally {
            this.isRefreshing = false;
        }
    }
    
    /**
     * Add CSS for pulse animation on alert flash
     */
    // addStyles() {
    //     // Add styles for alert flash animation if not already added
    //     if (!document.getElementById('monitorDashboardStyles')) {
    //         const style = document.createElement('style');
    //         style.id = 'monitorDashboardStyles';
    //         style.textContent = `
    //             @keyframes alert-flash {
    //                 0% { box-shadow: 0 0 0 0 rgba(231, 76, 60, 0.7); }
    //                 70% { box-shadow: 0 0 0 10px rgba(231, 76, 60, 0); }
    //                 100% { box-shadow: 0 0 0 0 rgba(231, 76, 60, 0); }
    //             }
                
    //             .alert-flash {
    //                 animation: alert-flash 1s ease-in-out 3;
    //             }
                
    //             .highlight-pulse {
    //                 transition: transform 0.3s ease, box-shadow 0.3s ease;
    //                 transform: translateY(-2px);
    //                 box-shadow: 0 5px 15px rgba(52, 152, 219, 0.5);
    //             }
    //         `;
    //         document.head.appendChild(style);
    //     }
    // }
    
    /**
     * Reject current alert for a student (mark as false positive)
     */
    async rejectCurrentAlert(studentId, sessionId) {
        if (!sessionId) {
            const card = this.videoGrid.querySelector(`.video-card[data-student-id="${studentId}"]`);
            sessionId = card?.dataset.sessionId;
        }
        
        if (!sessionId) {
            this.showToast('Could not identify student session', 'error');
            return;
        }
        
        // Find the latest alert for this student
        const alerts = this.alertsList?.querySelectorAll(`.alert-item[data-student-id="${studentId}"]`);
        if (!alerts || alerts.length === 0) {
            this.showToast('No active alerts to reject', 'warning');
            return;
        }
        
        // The most recent alert will be the first one (alerts are sorted newest to oldest)
        const latestAlert = alerts[0];
        const alertId = latestAlert.dataset.alertId;
        
        if (!alertId) {
            this.showToast('Could not identify alert', 'error');
            return;
        }
        
        // Update button state
        const rejectBtn = document.getElementById('focusRejectAlertBtn');
        if (rejectBtn) {
            rejectBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Rejecting...';
            rejectBtn.disabled = true;
        }
        
        try {
            const response = await fetch(`/monitoring/alert/${alertId}/reject/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    reason: 'Manually rejected by proctor'
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to reject alert');
            }
            
            // Remove the alert from UI with animation
            latestAlert.classList.add('removing');
            setTimeout(() => {
                if (latestAlert.parentNode) {
                    latestAlert.parentNode.removeChild(latestAlert);
                    this.updateAlertCounter();
                    
                    // Show empty alerts message if no alerts left
                    if (this.alertsList.children.length === 0) {
                        this.showEmptyAlerts();
                    }
                }
            }, 300);
            
            // Update display in focus view
            const focusAlerts = document.getElementById('focusAlerts');
            if (focusAlerts) {
                const currentCount = parseInt(focusAlerts.textContent) || 0;
                if (currentCount > 0) {
                    focusAlerts.textContent = currentCount - 1;
                }
            }
            
            // Reset button
            if (rejectBtn) {
                rejectBtn.innerHTML = '<i class="fas fa-check-circle"></i> Reject Alert';
                rejectBtn.disabled = false;
            }
            
            this.showToast('Alert rejected successfully', 'success');
            
            // Refresh the mini timeline in focus view
            this.fetchFocusData(sessionId);
            
        } catch (error) {
            console.error('Error rejecting alert:', error);
            
            // Reset button
            if (rejectBtn) {
                rejectBtn.innerHTML = '<i class="fas fa-check-circle"></i> Reject Alert';
                rejectBtn.disabled = false;
            }
            
            this.showToast('Failed to reject alert', 'error');
        }
    }
}