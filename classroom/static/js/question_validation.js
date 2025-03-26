// Question validation script
document.addEventListener('DOMContentLoaded', function() {
    function validateQuestionForm() {
        // Get all question cards
        const questionCards = document.querySelectorAll('.question-card');
        let isValid = true;

        questionCards.forEach((card, index) => {
            // Validate question text
            const questionText = card.querySelector('textarea');
            if (!questionText.value.trim()) {
                questionText.classList.add('is-invalid');
                isValid = false;
            } else {
                questionText.classList.remove('is-invalid');
            }

            // Validate options
            const options = card.querySelectorAll('input[type="text"]');
            options.forEach((option) => {
                if (!option.value.trim()) {
                    option.classList.add('is-invalid');
                    isValid = false;
                } else {
                    option.classList.remove('is-invalid');
                }
            });

            // Validate correct option selection
            const radioGroup = card.querySelectorAll('input[type="radio"]');
            let isAnyRadioChecked = Array.from(radioGroup).some(radio => radio.checked);
            
            if (!isAnyRadioChecked) {
                radioGroup.forEach(radio => {
                    radio.parentElement.classList.add('is-invalid');
                });
                isValid = false;
            }
        });

        return isValid;
    }

    // Add form submit validation
    const examForm = document.querySelector('form');
    if (examForm) {
        examForm.addEventListener('submit', function(e) {
            if (!validateQuestionForm()) {
                e.preventDefault();
                alert('Please fill in all required fields and select a correct answer for each question.');
                return false;
            }
        });
    }
});