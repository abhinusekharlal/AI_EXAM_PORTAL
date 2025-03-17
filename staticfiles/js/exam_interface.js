console.log('exam_interface.js starting to execute...');

// All exam interface classes and logic
class ExamState {
    constructor(examData) {
        if (!examData) throw new Error('Exam data is required');
        this.examData = examData;
        this.currentQuestion = 1;
        this.answeredQuestions = new Set();
        this.answers = new Map();
        this.isSubmitting = false;
        this.loadSavedState();
        this.setupBeforeUnload();
    }

    loadSavedState() {
        try {
            const savedState = localStorage.getItem(`exam_${this.examData.examId}_state`);
            if (savedState) {
                const state = JSON.parse(savedState);
                this.currentQuestion = state.currentQuestion;
                this.answeredQuestions = new Set(state.answeredQuestions);
                this.answers = new Map(state.answers.map(([k, v]) => [parseInt(k), v]));
            }
        } catch (error) {
            console.error('Error loading saved state:', error);
            this.clearSavedState();
        }
    }

    saveState() {
        try {
            const state = {
                currentQuestion: this.currentQuestion,
                answeredQuestions: Array.from(this.answeredQuestions),
                answers: Array.from(this.answers.entries())
            };
            localStorage.setItem(`exam_${this.examData.examId}_state`, JSON.stringify(state));
        } catch (error) {
            console.error('Error saving state:', error);
        }
    }

    setAnswer(questionId, answer) {
        this.answers.set(questionId, answer);
        this.answeredQuestions.add(this.currentQuestion);
        this.saveState();
    }

    getAnswer(questionId) {
        return this.answers.get(questionId);
    }

    clearSavedState() {
        localStorage.removeItem(`exam_${this.examData.examId}_state`);
        localStorage.removeItem(`exam_${this.examData.examId}_timer`);
    }

    setupBeforeUnload() {
        window.addEventListener('beforeunload', (e) => {
            if (this.answers.size > 0 && !this.isSubmitting) {
                e.preventDefault();
                e.returnValue = '';
            }
        });
    }
}

class ExamTimer {
    constructor(duration, onTimeUp) {
        this.duration = duration * 60;
        this.onTimeUp = onTimeUp;
        this.timerDisplay = document.getElementById('examTimer');
        this.timeLeft = this.duration;
        this.interval = null;
        this.endTime = null;
    }

    start() {
        // Use server start time instead of local storage
        if (!this.endTime) {
            const startTime = new Date(window.examData.startTime);
            this.endTime = new Date(startTime.getTime() + (this.duration * 1000));
        }

        this.interval = setInterval(() => this.tick(), 1000);
        this.tick(); // Initial tick
    }

    tick() {
        const now = new Date();
        const timeLeft = Math.max(0, Math.floor((this.endTime - now) / 1000));
        
        const minutes = Math.floor(timeLeft / 60);
        const seconds = timeLeft % 60;
        
        if (timeLeft <= 300 && timeLeft > 0) {
            this.timerDisplay.classList.add('warning');
        }
        
        this.timerDisplay.textContent = `⏰ ${minutes}:${seconds < 10 ? '0' + seconds : seconds}`;
        
        if (timeLeft <= 0) {
            clearInterval(this.interval);
            this.onTimeUp();
        }
    }

    stop() {
        if (this.interval) {
            clearInterval(this.interval);
        }
    }
}

class NotificationManager {
    constructor() {
        this.container = document.createElement('div');
        this.container.className = 'notifications-container';
        document.body.appendChild(this.container);
    }

    show(message, type = 'info', duration = 3000) {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <div class="notification-content">${message}</div>
            <button class="notification-close" onclick="this.parentElement.remove()">×</button>
        `;
        this.container.appendChild(notification);

        if (duration > 0) {
            setTimeout(() => {
                notification.classList.add('fade-out');
                setTimeout(() => notification.remove(), 300);
            }, duration);
        }
    }
}

class WebcamMonitor {
    constructor(examId, csrfToken) {
        this.examId = examId;
        this.csrfToken = csrfToken;
        this.localVideo = document.getElementById('localVideo');
        this.videoStatus = document.querySelector('.video-status');
        this.stream = null;
        this.captureInterval = null;
        this.isActive = false;
        
        // Configuration options
        this.captureFrequency = 2000; // Capture every 2 seconds
        this.imageQuality = 0.6;      // JPEG quality (0-1)
    }

    async initialize() {
        try {
            // Request camera permission and start stream
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: 640,
                    height: 480,
                    facingMode: 'user'
                },
                audio: false
            });
            
            // Display stream in video element
            this.localVideo.srcObject = this.stream;
            
            // Update status
            this.updateStatus('success', 'Webcam active');
            this.isActive = true;
            
            // Start periodic captures
            this.startCapturing();
            
            return true;
        } catch (error) {
            console.error('Error initializing webcam:', error);
            this.updateStatus('error', 'Failed to access webcam');
            return false;
        }
    }

    updateStatus(statusType, message) {
        if (this.videoStatus) {
            this.videoStatus.className = `video-status ${statusType}`;
            this.videoStatus.textContent = message;
        }
    }

    startCapturing() {
        // Create hidden canvas for capturing frames
        this.canvas = document.createElement('canvas');
        this.canvas.width = 640;
        this.canvas.height = 480;
        this.ctx = this.canvas.getContext('2d');
        
        // Start periodic captures
        this.captureInterval = setInterval(() => this.captureAndSend(), this.captureFrequency);
    }

    async captureAndSend() {
        if (!this.isActive || !this.stream.active) return;
        
        try {
            // Draw current frame to canvas
            this.ctx.drawImage(this.localVideo, 0, 0, this.canvas.width, this.canvas.height);
            
            // Convert to compressed JPEG data URL
            const imageData = this.canvas.toDataURL('image/jpeg', this.imageQuality);
            
            // Send to server
            await this.sendFrame(imageData);
        } catch (error) {
            console.error('Error capturing webcam frame:', error);
        }
    }

    async sendFrame(imageData) {
        try {
            const response = await fetch('/monitoring/frame-upload/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({
                    exam_id: this.examId,
                    image_data: imageData
                })
            });
            
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.message || 'Error uploading frame');
            }

            // Handle any alerts from frame processing
            if (data.alerts && data.alerts.length > 0) {
                this.handleAlerts(data.alerts);
            }
        } catch (error) {
            console.error('Error sending frame to server:', error);
            
            // If we're getting persistent errors, slow down the capture frequency
            if (this.captureFrequency < 10000) {
                this.captureFrequency += 1000;
                clearInterval(this.captureInterval);
                this.captureInterval = setInterval(() => this.captureAndSend(), this.captureFrequency);
                console.log(`Adjusted capture frequency to ${this.captureFrequency}ms due to errors`);
            }
        }
    }

    handleAlerts(alerts) {
        alerts.forEach(alert => {
            // Show alert to student
            const message = `Warning: ${alert.description}`;
            const duration = alert.severity === 'critical' ? 0 : 5000; // Keep critical alerts visible
            window.examInterface.showNotification(message, alert.severity, duration);
            
            // Update video status for critical alerts
            if (alert.severity === 'critical') {
                this.updateStatus('error', alert.description);
            }
        });
    }

    stop() {
        // Clear capture interval
        if (this.captureInterval) {
            clearInterval(this.captureInterval);
            this.captureInterval = null;
        }
        
        // Stop all tracks on the stream
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
        }
        
        // Update status
        this.updateStatus('pending', 'Webcam disconnected');
        this.isActive = false;
    }
}

class ExamInterface {
    constructor(examData) {
        if (!examData) throw new Error('Exam data not initialized');
        if (!examData.examId) throw new Error('Exam ID is required');
        if (!examData.totalQuestions) throw new Error('Total questions count is required');
        if (!examData.duration) throw new Error('Exam duration is required');
        if (!examData.startTime) throw new Error('Start time is required');
        
        this.state = new ExamState(examData);
        this.timer = new ExamTimer(examData.duration, () => this.handleTimeUp());
        this.notifications = new NotificationManager();
        
        // Add webcam monitoring
        this.webcamMonitor = new WebcamMonitor(examData.examId, examData.csrfToken);
        
        // Validate required DOM elements exist
        if (!document.querySelector('.question-box')) {
            throw new Error('Question container not found');
        }
        if (!document.getElementById('examTimer')) {
            throw new Error('Timer element not found');
        }
        
        this.initializeInterface();
    }

    async initializeInterface() {
        this.attachEventListeners();
        this.loadSavedAnswers();
        this.showQuestion(this.state.currentQuestion);
        this.timer.start();
        this.updateProgress();
        
        // Initialize webcam monitoring
        try {
            const webcamInitialized = await this.webcamMonitor.initialize();
            if (!webcamInitialized) {
                this.showNotification(
                    'Warning: Webcam access is required for this exam. Please enable your camera.',
                    'warning',
                    0
                );
            }
        } catch (error) {
            console.error('Error initializing webcam monitoring:', error);
            this.showNotification(
                'Error initializing webcam monitoring. Please refresh the page.',
                'danger',
                0
            );
        }
    }

    attachEventListeners() {
        // Navigation buttons
        document.querySelector('.prev-btn')?.addEventListener('click', () => this.navigateQuestion(-1));
        document.querySelector('.next-btn')?.addEventListener('click', () => this.navigateQuestion(1));
        document.querySelector('.submit-btn')?.addEventListener('click', () => this.submitExam());

        // Auto-save on radio button change
        document.querySelectorAll('.question-box').forEach(box => {
            const radios = box.querySelectorAll('input[type="radio"]');
            radios.forEach(radio => {
                radio.addEventListener('change', (e) => this.handleAnswerChange(e));
            });

            // Add save button handler
            const saveBtn = box.querySelector('.save-btn');
            if (saveBtn) {
                saveBtn.addEventListener('click', () => {
                    const selectedRadio = box.querySelector('input[type="radio"]:checked');
                    if (selectedRadio) {
                        this.handleAnswerSave(selectedRadio);
                    } else {
                        this.showNotification('Please select an answer before saving', 'warning');
                    }
                });
            }
        });

        // Add keyboard navigation
        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowLeft') {
                this.navigateQuestion(-1);
            } else if (e.key === 'ArrowRight') {
                this.navigateQuestion(1);
            }
        });
    }

    loadSavedAnswers() {
        try {
            document.querySelectorAll('.question-box').forEach(box => {
                const questionId = parseInt(box.dataset.questionId);
                const savedAnswer = this.state.getAnswer(questionId);
                if (savedAnswer) {
                    const radio = box.querySelector(`input[value="${savedAnswer}"]`);
                    if (radio) {
                        radio.checked = true;
                        box.classList.add('answered');
                    }
                }
            });
        } catch (error) {
            console.error('Error loading saved answers:', error);
        }
    }

    handleAnswerChange(event) {
        this.handleAnswerSave(event.target);
    }

    handleAnswerSave(radio) {
        const questionBox = radio.closest('.question-box');
        if (!questionBox) return;

        const questionId = parseInt(questionBox.dataset.questionId);
        const questionNum = parseInt(questionBox.dataset.questionNumber);

        this.state.setAnswer(questionId, radio.value);
        questionBox.classList.add('answered');
        this.showNotification('Answer saved!', 'success');
        this.updateProgress();

        // Auto-navigate to next question after saving if not on last question
        if (questionNum < window.examData.totalQuestions) {
            setTimeout(() => this.navigateQuestion(1), 500);
        }
    }

    showQuestion(num) {
        try {
            if (!num || num < 1 || num > window.examData.totalQuestions) {
                throw new Error('Invalid question number');
            }

            const questions = document.querySelectorAll('.question-box');
            questions.forEach(q => {
                const questionNum = parseInt(q.dataset.questionNumber);
                q.classList.toggle('active', questionNum === num);
            });

            document.getElementById('currentQuestionNum').textContent = num;
            this.state.currentQuestion = num;
            this.state.saveState();
            this.updateProgress();
            
            const prevBtn = document.querySelector('.prev-btn');
            const nextBtn = document.querySelector('.next-btn');
            if (prevBtn) prevBtn.disabled = num <= 1;
            if (nextBtn) nextBtn.disabled = num >= window.examData.totalQuestions;
            
            const currentQuestionBox = document.querySelector(`.question-box[data-question-number="${num}"]`);
            if (currentQuestionBox) {
                const questionId = parseInt(currentQuestionBox.dataset.questionId);
                const savedAnswer = this.state.getAnswer(questionId);
                if (savedAnswer) {
                    const radio = currentQuestionBox.querySelector(`input[value="${savedAnswer}"]`);
                    if (radio) radio.checked = true;
                }
            }
        } catch (error) {
            console.error('Error showing question:', error);
            this.showNotification('Error displaying question. Please refresh the page.', 'danger');
            // Keep current question if error occurs
            this.showQuestion(this.state.currentQuestion);
        }
    }

    navigateQuestion(direction) {
        const newQuestion = this.state.currentQuestion + direction;
        if (newQuestion >= 1 && newQuestion <= window.examData.totalQuestions) {
            this.showQuestion(newQuestion);
        }
    }

    updateProgress() {
        const progress = document.querySelector('.progress-indicator');
        if (!progress) return;
        
        progress.innerHTML = '';
        for (let i = 1; i <= window.examData.totalQuestions; i++) {
            const indicator = document.createElement('div');
            indicator.className = 'question-indicator';
            if (this.state.answeredQuestions.has(i)) indicator.classList.add('answered');
            if (i === this.state.currentQuestion) indicator.classList.add('current');
            indicator.textContent = i;
            indicator.onclick = () => this.showQuestion(i);
            progress.appendChild(indicator);
        }
    }

    async submitExam(isAutoSubmit = false) {
        if (this.state.isSubmitting) return;

        try {
            // Existing confirmation code
            if (!isAutoSubmit) {
                const unansweredCount = window.examData.totalQuestions - this.state.answeredQuestions.size;
                if (unansweredCount > 0) {
                    const confirmed = confirm(`You have ${unansweredCount} unanswered questions. Are you sure you want to submit?`);
                    if (!confirmed) return;
                } else {
                    const confirmed = confirm('Are you sure you want to submit the exam?');
                    if (!confirmed) return;
                }
            }

            this.state.isSubmitting = true;
            
            // Stop webcam monitoring before submitting
            this.webcamMonitor.stop();

            // Existing submission code
            const answers = Array.from(this.state.answers.entries()).map(([questionId, answer]) => ({
                question_id: questionId,
                selected_option: answer
            }));

            const response = await fetch(window.examData.submitUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.examData.csrfToken
                },
                body: JSON.stringify({
                    exam_id: window.examData.examId,
                    answers: answers
                })
            });

            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to submit exam');

            this.state.clearSavedState();
            this.timer.stop();
            window.location.href = window.examData.completedUrl;
        } catch (error) {
            console.error('Error submitting exam:', error);
            this.showNotification('Failed to submit exam. Please try again.', 'danger', 0);
            this.state.isSubmitting = false;
            
            // Restart webcam monitoring if submission failed
            if (!this.webcamMonitor.isActive) {
                await this.webcamMonitor.initialize();
            }
        }
    }

    handleTimeUp() {
        this.showNotification('Time is up! Your exam will be submitted automatically...', 'warning', 0);
        setTimeout(() => this.submitExam(true), 2000);
    }

    showNotification(message, type) {
        this.notifications.show(message, type);
    }
}

// Improved initialization with retry logic
document.addEventListener('DOMContentLoaded', () => {
    let retryCount = 0;
    const maxRetries = 3;

    function initializeExam() {
        try {
            if (!window.examData) {
                throw new Error('Exam data not initialized');
            }
            window.examInterface = new ExamInterface(window.examData);
        } catch (error) {
            console.error('Error initializing exam interface:', error);
            retryCount++;
            
            if (retryCount < maxRetries) {
                console.log(`Retrying initialization (${retryCount}/${maxRetries})...`);
                setTimeout(initializeExam, 1000);
                return;
            }
            
            const container = document.querySelector('.container');
            if (container) {
                container.innerHTML = `
                    <div class="error-message">
                        Failed to initialize exam interface. 
                        <br>Error: ${error.message}
                        <br><br>
                        <button onclick="location.reload()" class="retry-btn">Retry</button>
                    </div>
                `;
            }
        }
    }

    initializeExam();
});
