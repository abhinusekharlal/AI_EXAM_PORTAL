        // Mock exam data
const examData = {
    currentQuestion: 1,
    totalQuestions: 5,
    answeredQuestions: 1,
    timeRemaining: 3600, // in seconds
};

// Update progress bar
function updateProgress() {
    const progress = (examData.answeredQuestions / examData.totalQuestions) * 100;
    document.querySelector('.progress').style.width = `${progress}%`;
    document.querySelector('.fraction').textContent = 
        `${examData.answeredQuestions}/${examData.totalQuestions}`;
}

// Timer functionality
function updateTimer() {
    const hours = Math.floor(examData.timeRemaining / 3600);
    const minutes = Math.floor((examData.timeRemaining % 3600) / 60);
    const seconds = examData.timeRemaining % 60;
    
    const timerDisplay = document.querySelector('.timer');
    timerDisplay.textContent = `⏰ ${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    
    if (examData.timeRemaining > 0) {
        examData.timeRemaining--;
        setTimeout(updateTimer, 1000);
    } else {
        alert('Time is up!');
        // Handle exam submission
    }
}

// Navigation buttons
document.querySelector('.prev-btn').addEventListener('click', () => {
    if (examData.currentQuestion > 1) {
        examData.currentQuestion--;
        document.querySelector('.question-number').textContent = 
            `Question No. ${examData.currentQuestion}`;
    }
});

document.querySelector('.next-btn').addEventListener('click', () => {
    if (examData.currentQuestion < examData.totalQuestions) {
        examData.currentQuestion++;
        document.querySelector('.question-number').textContent = 
            `Question No. ${examData.currentQuestion}`;
    }
});

// Save answer button
document.querySelector('.save-btn').addEventListener('click', () => {
    const selectedOption = document.querySelector('input[name="answer"]:checked');
    if (selectedOption) {
        // Here you would typically save the answer to your backend
        alert('Answer saved successfully!');
    } else {
        alert('Please select an answer before saving.');
    }
});

// Submit exam button
document.querySelector('.submit-btn').addEventListener('click', () => {
    if (confirm('Are you sure you want to submit the exam?')) {
        // Here you would typically handle the exam submission
        alert('Exam submitted successfully!');
    }
});

// Initialize the exam interface
document.addEventListener('DOMContentLoaded', () => {
    updateProgress();
    updateTimer();
});

// Simulate active proctoring status
setInterval(() => {
    const statusDot = document.querySelector('.status-dot');
    statusDot.style.opacity = statusDot.style.opacity === '1' ? '0.5' : '1';
}, 2000);
