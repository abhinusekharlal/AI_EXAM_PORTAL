// JavaScript for the Create Exam page with HTMX
document.addEventListener('DOMContentLoaded', function() {
    // Get references to DOM elements
    const questionsContainer = document.getElementById('questions-container');
    const noQuestionsMessage = document.getElementById('no-questions-message');
    
    // Only proceed with DOM operations if the elements exist
    if (questionsContainer) {
        // Handle showing/hiding the no-questions message
        const updateNoQuestionsMessage = function() {
            const questionCards = document.querySelectorAll('.question-card');
            
            if (noQuestionsMessage) {
                if (questionCards.length > 0) {
                    noQuestionsMessage.style.display = 'none';
                } else {
                    noQuestionsMessage.style.display = 'block';
                }
            }
        };

        // Initialize the page
        updateNoQuestionsMessage();

        // Handle HTMX events for question management
        document.body.addEventListener('htmx:afterSwap', function(event) {
            // Update the no questions message visibility
            updateNoQuestionsMessage();
            
            // Update the form validation on new questions
            initializeFormValidation();
        });

        // Add event listener for form submission
        const examForm = document.querySelector('form');
        if (examForm) {
            examForm.addEventListener('submit', function(e) {
                // Form validation could be added here if needed
                console.log("Form submitted");
            });
        }
    }

    // Function to initialize form validation
    function initializeFormValidation() {
        // Add validation for required fields
        const requiredFields = document.querySelectorAll('input[required], textarea[required], select[required]');
        requiredFields.forEach(field => {
            field.addEventListener('blur', function() {
                if (!this.value) {
                    this.classList.add('is-invalid');
                } else {
                    this.classList.remove('is-invalid');
                }
            });
        });

        // Add validation for correct option selection
        const correctOptionRadios = document.querySelectorAll('.correct-option-radio');
        correctOptionRadios.forEach(radio => {
            radio.addEventListener('change', function() {
                // Find the form group this radio belongs to
                const questionCard = this.closest('.question-card');
                if (questionCard) {
                    const radioName = this.name;
                    
                    // Mark all radios in this group as valid (remove any previous error styling)
                    questionCard.querySelectorAll(`input[name="${radioName}"]`).forEach(r => {
                        if (r.parentElement) {
                            r.parentElement.classList.remove('is-invalid');
                        }
                    });
                }
            });
        });
    }

    // Initialize form validation if we're on a page with form elements
    if (document.querySelector('form')) {
        initializeFormValidation();
    }
});