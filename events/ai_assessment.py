import random
import numpy as np
from .models import EventAssessment, Question, QuestionOption, NumericalAnswer

def generate_ai_assessment(event, title, description, due_date):
    """
    Generate an AI-powered assessment with 10 questions (mix of MCQ, MSQ, and NAT)
    for a given event.
    
    Args:
        event: The Event object
        title: Title of the assessment
        description: Description of the assessment
        due_date: Due date for the assessment
        
    Returns:
        EventAssessment: The created assessment object
    """
    # Create the assessment
    assessment = EventAssessment.objects.create(
        event=event,
        title=title,
        description=description,
        due_date=due_date,
        total_marks=10,  # 10 questions, 1 mark each
        is_ai_generated=True,
        passing_score=3  # Minimum score needed for certificate
    )
    
    # Generate questions based on event details
    event_keywords = extract_keywords(event)
    
    # Create a mix of question types (6 MCQs, 2 MSQs, 2 NATs)
    create_mcq_questions(assessment, event_keywords, count=6)
    create_msq_questions(assessment, event_keywords, count=2)
    create_nat_questions(assessment, event_keywords, count=2)
    
    return assessment

def extract_keywords(event):
    """
    Extract keywords from event details to generate relevant questions
    
    Args:
        event: The Event object
        
    Returns:
        list: List of keywords extracted from event details
    """
    # Combine event name, title, and about fields
    event_text = f"{event.event_name} {event.title} {event.about}"
    
    # Simple keyword extraction (in a real implementation, use NLP techniques)
    # Remove common words and punctuation
    common_words = ['and', 'the', 'is', 'in', 'to', 'of', 'for', 'a', 'an', 'on', 'with']
    words = event_text.lower().split()
    keywords = [word for word in words if word not in common_words and len(word) > 3]
    
    # Return unique keywords
    return list(set(keywords))

def create_mcq_questions(assessment, keywords, count=6):
    """
    Create Multiple Choice Questions for the assessment
    
    Args:
        assessment: The EventAssessment object
        keywords: List of keywords to use for question generation
        count: Number of MCQ questions to create
    """
    # Sample question templates
    question_templates = [
        "What is the main focus of {keyword}?",
        "Which of the following best describes {keyword}?",
        "What is the primary purpose of {keyword}?",
        "Which concept is most closely related to {keyword}?",
        "In the context of this event, what does {keyword} refer to?",
        "What is the significance of {keyword} in this event?",
        "Which of these is a characteristic of {keyword}?",
        "How does {keyword} contribute to the event's objectives?"
    ]
    
    for i in range(count):
        # Select a random keyword and question template
        keyword = random.choice(keywords) if keywords else f"Topic {i+1}"
        template = random.choice(question_templates)
        
        # Create the question
        question_text = template.format(keyword=keyword)
        question = Question.objects.create(
            assessment=assessment,
            question_text=question_text,
            question_type='MCQ',
            marks=1
        )
        
        # Create 4 options (1 correct, 3 incorrect)
        correct_option = f"The correct definition of {keyword}"
        QuestionOption.objects.create(
            question=question,
            option_text=correct_option,
            is_correct=True
        )
        
        # Create incorrect options
        for j in range(3):
            incorrect_option = f"Incorrect definition {j+1} of {keyword}"
            QuestionOption.objects.create(
                question=question,
                option_text=incorrect_option,
                is_correct=False
            )

def create_msq_questions(assessment, keywords, count=2):
    """
    Create Multiple Select Questions for the assessment
    
    Args:
        assessment: The EventAssessment object
        keywords: List of keywords to use for question generation
        count: Number of MSQ questions to create
    """
    # Sample question templates
    question_templates = [
        "Which of the following are related to {keyword}? (Select all that apply)",
        "Select all concepts that are associated with {keyword}.",
        "Which of these characteristics apply to {keyword}? (Select all that apply)",
        "Identify all elements that are part of {keyword}."
    ]
    
    for i in range(count):
        # Select a random keyword and question template
        keyword = random.choice(keywords) if keywords else f"Topic {i+1}"
        template = random.choice(question_templates)
        
        # Create the question
        question_text = template.format(keyword=keyword)
        question = Question.objects.create(
            assessment=assessment,
            question_text=question_text,
            question_type='MSQ',
            marks=1
        )
        
        # Create 5 options (2-3 correct, rest incorrect)
        num_correct = random.randint(2, 3)
        
        # Create correct options
        for j in range(num_correct):
            correct_option = f"Correct aspect {j+1} of {keyword}"
            QuestionOption.objects.create(
                question=question,
                option_text=correct_option,
                is_correct=True
            )
        
        # Create incorrect options
        for j in range(5 - num_correct):
            incorrect_option = f"Incorrect aspect {j+1} of {keyword}"
            QuestionOption.objects.create(
                question=question,
                option_text=incorrect_option,
                is_correct=False
            )

def create_nat_questions(assessment, keywords, count=2):
    """
    Create Numerical Answer Type Questions for the assessment
    
    Args:
        assessment: The EventAssessment object
        keywords: List of keywords to use for question generation
        count: Number of NAT questions to create
    """
    # Sample question templates
    question_templates = [
        "How many key components are there in {keyword}?",
        "What is the numerical value associated with {keyword}?",
        "If {keyword} has a value of X, what is X/2?",
        "What is the approximate percentage of {keyword} in the event?"
    ]
    
    for i in range(count):
        # Select a random keyword and question template
        keyword = random.choice(keywords) if keywords else f"Topic {i+1}"
        template = random.choice(question_templates)
        
        # Create the question
        question_text = template.format(keyword=keyword)
        question = Question.objects.create(
            assessment=assessment,
            question_text=question_text,
            question_type='NAT',
            marks=1
        )
        
        # Create numerical answer (random value between 1-10)
        correct_answer = round(random.uniform(1, 10), 1)
        tolerance = 0.1  # Allow for small differences in answers
        
        NumericalAnswer.objects.create(
            question=question,
            correct_answer=correct_answer,
            tolerance=tolerance
        )

def evaluate_student_submission(submission):
    """
    Automatically evaluate a student's assessment submission
    
    Args:
        submission: The AssessmentSubmission object
        
    Returns:
        int: The calculated score
    """
    from .models import StudentAnswer
    
    assessment = submission.assessment
    questions = assessment.questions.all()
    total_score = 0
    
    for question in questions:
        # Get the student's answer for this question
        try:
            student_answer = StudentAnswer.objects.get(submission=submission, question=question)
            is_correct = False
            
            # Evaluate based on question type
            if question.question_type == 'MCQ':
                # For MCQ, check if the selected option is correct
                selected_options = student_answer.selected_options.all()
                if selected_options.count() == 1 and selected_options.first().is_correct:
                    is_correct = True
                    total_score += question.marks
            
            elif question.question_type == 'MSQ':
                # For MSQ, all correct options must be selected and no incorrect ones
                selected_options = student_answer.selected_options.all()
                correct_options = question.options.filter(is_correct=True)
                
                # Check if all selected options are correct and all correct options are selected
                if (selected_options.count() == correct_options.count() and
                    all(option.is_correct for option in selected_options)):
                    is_correct = True
                    total_score += question.marks
            
            elif question.question_type == 'NAT':
                # For NAT, check if the numerical value is within tolerance
                if student_answer.numerical_value is not None:
                    numerical_answer = question.numerical_answer
                    if abs(student_answer.numerical_value - numerical_answer.correct_answer) <= numerical_answer.tolerance:
                        is_correct = True
                        total_score += question.marks
            
            # Update the is_correct field
            student_answer.is_correct = is_correct
            student_answer.save()
            
        except StudentAnswer.DoesNotExist:
            # No answer provided for this question
            pass
    
    # Update the submission score
    submission.score = total_score
    submission.is_ai_graded = True
    submission.save()
    
    return total_score