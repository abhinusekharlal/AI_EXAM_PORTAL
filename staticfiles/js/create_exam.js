let questionCounter = 1;
        const questionsContainer = document.getElementById('questions-container');
        const addQuestionBtn = document.querySelector('.btn-add-question');

        function addQuestion() {
            const questionDiv = document.createElement('div');
            questionDiv.className = 'question-card';
            questionDiv.innerHTML = `

                <div class="question-header">
                    <span>Question ${questionCounter + 1}</span>
                    <button type="button" class="btn-delete" onclick="deleteQuestion(this)">🗑</button>
                </div>
    
                <div class="question-text">
                    {{ question_form.question_text }}
                </div>    
        
                <div class="options-container">
                    <div class="option">
                        <label for="option1">Option 1</label>
                        {{ question_form.option1 }}
                    </div>
                    <div class="option">
                        <label for="option2">Option 2</label>
                        {{ question_form.option2 }}
                    </div>
                    <div class="option">
                        <label for="option3">Option 3</label>
                        {{ question_form.option3 }}
                    </div>
                    <div class="option">
                        <label for="option4">Option 4</label>
                        {{ question_form.option4 }}
                    </div>
                </div>
    
                <div class="option">
                    <label for="correct_option">Correct Option</label>
                    {{ question_form.correct_option }}
                </div>
    
                <button type="button" class="btn-add-option" onclick="addOption(this)">+ Add Option</button>
            `;

            questionsContainer.appendChild(questionDiv);
            questionCounter++;
        }

        function deleteQuestion(button) {
            const questionCard = button.closest('.question-card');
            questionCard.remove();
        }

        function addOption(button) {
            const optionsContainer = button.previousElementSibling;
            const optionCount = optionsContainer.children.length + 1;
            const optionDiv = document.createElement('div');
            optionDiv.className = 'option';
            optionDiv.innerHTML = `
                <input type="text" name="option${optionCount}" placeholder="Option ${optionCount}">
            `;
            optionsContainer.appendChild(optionDiv);
        }

        // 初始化第一个题目
        document.addEventListener('DOMContentLoaded', () => {
            if (questionsContainer.children.length === 0) {
                addQuestion();
            }
        });