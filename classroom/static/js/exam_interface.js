console.log('exam_interface.js starting to execute...');

// Verify examData is available globally
if (typeof window.examData === 'undefined') {
    console.error('examData not found - check script loading order');
    throw new Error('examData not found - check script loading order');
}

// Log the data we're working with
console.log('Working with exam data:', window.examData);

let currentQuestion = 1;
let answeredQuestions = new Set();

// Timer functionality
function startTimer(duration) {
    let timeLeft = duration * 60; // convert minutes to seconds
    const timerDisplay = document.getElementById('examTimer');
    
    const countdown = setInterval(() => {
        let minutes = Math.floor(timeLeft / 60);
        let seconds = timeLeft % 60;
        timerDisplay.textContent = `⏰ ${minutes}:${seconds < 10 ? '0' + seconds : seconds}`;
        if (timeLeft <= 0) {
            clearInterval(countdown);
            submitExam();
        }
        timeLeft--;
    }, 1000);
}

function showQuestion(num) {
    console.log("Showing question:", num);
    const questions = document.querySelectorAll('.question-box');
    
    questions.forEach(q => {
        const questionNum = parseInt(q.dataset.questionNumber);
        if (questionNum === num) {
            q.classList.add('active');
            console.log("Activating question:", questionNum);
        } else {
            q.classList.remove('active');
        }
    });
    
    document.getElementById('currentQuestionNum').textContent = num;
    currentQuestion = num;
}

function previousQuestion(e) {
    e?.preventDefault();
    if (currentQuestion > 1) {
        showQuestion(currentQuestion - 1);
    }
    console.log('Previous button clicked');
}

function nextQuestion(e) {
    e?.preventDefault();
    const questions = document.querySelectorAll('.question-box');
    const totalQuestions = questions.length;
    console.log("Total questions:", totalQuestions, "Current question:", currentQuestion);
    if (currentQuestion < totalQuestions) {
        showQuestion(currentQuestion + 1);
    } else {
        console.log("Already at the last question.");
    }
    console.log('Next button clicked');
}

function saveAnswer(e) {
    e?.preventDefault();
    // Get currently visible question using display style
    const currentBox = Array.from(document.querySelectorAll('.question-box')).find(q => q.style.display !== 'none');
    if (!currentBox) return;
    const selected = currentBox.querySelector('input[type="radio"]:checked');
    if (selected) {
        const qNumber = parseInt(currentBox.dataset.questionNumber);
        answeredQuestions.add(qNumber);
        updateProgress();
        nextQuestion(e);
    } else {
        alert('Please select an answer before saving.');
    }
}

function updateProgress() {
    const totalQuestions = document.querySelectorAll('.question-box').length;
    const progressPercent = (answeredQuestions.size / totalQuestions) * 100;
    document.getElementById('progressBar').style.width = `${progressPercent}%`;
    document.getElementById('answeredCount').textContent = answeredQuestions.size;
}

function submitExam(e) {
    e?.preventDefault();
    
    // Require at least one answered question before submission
    if (answeredQuestions.size === 0) {
        alert('Please answer at least one question before submitting.');
        return;
    }
    if (confirm('Are you sure you want to submit the exam?')) {
        const answers = {};
        // Gather selected answers from every question box
        document.querySelectorAll('.question-box').forEach(box => {
            const questionId = box.dataset.questionId;
            const selected = box.querySelector('input[type="radio"]:checked');
            if (selected) {
                answers[questionId] = selected.value;
            }
        });
        fetch('/classroom/submit-exam/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': examData.csrfToken,
            },
            body: JSON.stringify({
                examId: examData.examId,
                answers: answers
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(`Your score: ${data.score}%`);
                window.location.href = data.redirect_url;
            } else {
                alert('Error submitting exam: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error submitting exam. Please try again.');
        });
    }
}

// Basic fullscreen implementation (if desired)
function enterFullscreen() {
    const container = document.getElementById('examContainer');
    if (container && container.requestFullscreen) {
        container.requestFullscreen().catch(err => {
            console.error("Error launching fullscreen:", err);
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    try {
        // Get and verify all required elements
        const elements = {
            prevBtn: document.querySelector('.prev-btn'),
            nextBtn: document.querySelector('.next-btn'),
            saveBtn: document.querySelector('.save-btn'),
            submitBtn: document.querySelector('.submit-btn'),
            questionsContainer: document.getElementById('questionsContainer'),
            timerDisplay: document.getElementById('examTimer')
        };

        // Verify all elements are found
        Object.entries(elements).forEach(([name, element]) => {
            if (!element) {
                throw new Error(`Required element ${name} not found`);
            }
        });

        console.log('All required elements found:', elements);
        
        // Add event listeners and initialize
        elements.prevBtn.addEventListener('click', previousQuestion);
        elements.nextBtn.addEventListener('click', nextQuestion);
        elements.saveBtn.addEventListener('click', saveAnswer);
        elements.submitBtn.addEventListener('click', submitExam);
        
        startTimer(window.examData.duration);
        showQuestion(1);
        updateProgress();
        
        console.log('Exam interface initialized successfully');
    } catch (error) {
        console.error('Error initializing exam interface:', error);
    }
});
