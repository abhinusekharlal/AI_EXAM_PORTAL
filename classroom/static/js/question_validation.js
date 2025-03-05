document.addEventListener('htmx:afterSettle', function() {
    attachOptionValidation();
    attachCorrectOptionHandler();
});

function attachOptionValidation() {
    const optionInputs = document.querySelectorAll('.options-container input[type="text"]');
    optionInputs.forEach(input => {
        input.addEventListener('change', function() {
            validateOptions(this.closest('.question-card'));
        });
    });
}

function attachCorrectOptionHandler() {
    const correctSelects = document.querySelectorAll('select[name*="correct_option"]');
    correctSelects.forEach(select => {
        select.addEventListener('change', function() {
            validateCorrectOption(this.closest('.question-card'));
        });
    });
}

function validateOptions(questionCard) {
    const options = Array.from(questionCard.querySelectorAll('.options-container input[type="text"]'));
    const correctSelect = questionCard.querySelector('select[name*="correct_option"]');
    const errorDiv = getOrCreateErrorDiv(questionCard);
    
    // Check if all options have text
    const emptyOptions = options.filter(opt => !opt.value.trim());
    if (emptyOptions.length > 0) {
        errorDiv.textContent = 'All options must be filled out';
        errorDiv.style.display = 'block';
        correctSelect.disabled = true;
        return false;
    }
    
    // Check for duplicate options
    const optionValues = options.map(opt => opt.value.trim().toLowerCase());
    const hasDuplicates = optionValues.some((value, index) => 
        optionValues.indexOf(value) !== index
    );
    
    if (hasDuplicates) {
        errorDiv.textContent = 'Options must be unique';
        errorDiv.style.display = 'block';
        correctSelect.disabled = true;
        return false;
    }
    
    errorDiv.style.display = 'none';
    correctSelect.disabled = false;
    return true;
}

function validateCorrectOption(questionCard) {
    const correctSelect = questionCard.querySelector('select[name*="correct_option"]');
    const selectedOption = correctSelect.value;
    const optionInput = questionCard.querySelector(`input[name*="option${selectedOption}"]`);
    const errorDiv = getOrCreateErrorDiv(questionCard);
    
    if (!optionInput || !optionInput.value.trim()) {
        errorDiv.textContent = 'The selected correct option must have text';
        errorDiv.style.display = 'block';
        return false;
    }
    
    errorDiv.style.display = 'none';
    return true;
}

function getOrCreateErrorDiv(questionCard) {
    let errorDiv = questionCard.querySelector('.question-errors');
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.className = 'question-errors alert alert-danger';
        errorDiv.style.display = 'none';
        questionCard.querySelector('.question-content').appendChild(errorDiv);
    }
    return errorDiv;
}

// Form submission validation
document.addEventListener('submit', function(event) {
    if (event.target.matches('form')) {
        const questions = event.target.querySelectorAll('.question-card');
        if (questions.length === 0) {
            event.preventDefault();
            alert('Please add at least one question to the exam');
            return;
        }
        
        let hasErrors = false;
        questions.forEach(question => {
            if (!validateOptions(question) || !validateCorrectOption(question)) {
                hasErrors = true;
            }
            
            // Validate question text
            const questionText = question.querySelector('textarea[name*="question_text"]');
            if (!questionText.value.trim()) {
                const errorDiv = getOrCreateErrorDiv(question);
                errorDiv.textContent = 'Question text is required';
                errorDiv.style.display = 'block';
                hasErrors = true;
            }
        });
        
        if (hasErrors) {
            event.preventDefault();
            alert('Please fix all errors before submitting');
        }
    }
});