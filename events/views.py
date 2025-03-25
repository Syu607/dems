from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import Event, EventAssessment, AssessmentSubmission, EventSchedule, EventRegistration, StudentAnswer, EventFeedback, EventMaterial
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Avg, Count, Sum
import uuid
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from .utils import check_and_generate_certificates
from io import BytesIO

@login_required
def create_event(request):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Only event coordinators can create events.')
        return redirect('dashboard')

    if request.method == 'POST':
        try:
            # Generate event ID in the format EVT-2025-D73FF
            import datetime
            import random
            import string
            current_year = datetime.datetime.now().year
            random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
            event_id = f'EVT-{current_year}-{random_suffix}'
            
            event = Event(
                name=request.POST['event_name'],
                coordinator=request.user,
                department=request.user.department,
                event_name=request.POST['event_name'],
                about=request.POST['about'],
                title=request.POST['title'],
                date=request.POST['date'],
                time=request.POST['time'],
                expected_attendees=request.POST['expected_attendees'],
                mode=request.POST['mode'],
                venue=request.POST.get('venue'),
                budget=request.POST['budget'],
                registration_fee=request.POST['registration_fee'],
                refreshment=request.POST['refreshment'],
                renumeration=request.POST['renumeration'],
                honorarium=request.POST['honorarium'],
                other_requirements=request.POST.get('other_requirements', ''),
                event_id=event_id
            )
            event.save()
            
            # Return JSON response for AJAX requests with event_id
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True, 
                    'message': 'Event created successfully! Waiting for approval.',
                    'event_id': event_id
                })
                
            messages.success(request, 'Event created successfully! Waiting for approval.')
            return redirect('my_events')
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': f'Error creating event: {str(e)}'})
            messages.error(request, f'Error creating event: {str(e)}')
            return render(request, 'events/create_event.html')
    return render(request, 'events/create_event.html')

@login_required
def my_events(request):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    events = Event.objects.filter(coordinator=request.user).order_by('-created_at')
    context = {
        'events': events,
        'pending_count': events.filter(status='PENDING').count(),
        'approved_count': events.filter(status__in=['HOD_APPROVED', 'PRINCIPAL_APPROVED']).count(),
        'rejected_count': events.filter(status__in=['HOD_REJECTED', 'PRINCIPAL_REJECTED']).count(),
    }
    return render(request, 'events/my_events.html', context)

@login_required
def event_detail(request, event_id):
    # Try to get event by ID first, then by event_id if that fails
    try:
        # First try to convert to integer and look up by id
        event_id_int = int(event_id)
        event = get_object_or_404(Event, id=event_id_int)
    except (ValueError, TypeError):
        # If conversion fails, look up by event_id string
        event = get_object_or_404(Event, event_id=event_id)
        
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'events/event_detail_modal.html', {'event': event})
    return render(request, 'events/event_detail.html', {'event': event})

@login_required
def event_detail_api(request, event_id):
    event = get_object_or_404(Event, event_id=event_id)
    # Return JSON response for API requests
    return JsonResponse({
        'event_id': event.event_id,
        'event_name': event.event_name,
        'title': event.title,
        'department': event.get_department_display(),
        'coordinator': event.coordinator.username,
        'date': str(event.date),
        'time': str(event.time),
        'mode': event.get_mode_display(),
        'venue': event.venue,
        'expected_attendees': event.expected_attendees,
        'status': event.status
    })

@login_required
def event_approval_list(request):
    if request.user.role not in ['HOD', 'PRINCIPAL']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    # Redirect to the appropriate pending events page based on user role
    if request.user.role == 'HOD':
        return redirect('hod_pending_events')
    else:  # PRINCIPAL
        return redirect('principal_pending_events')

    if request.user.role == 'HOD':
        pending_events = Event.objects.filter(
            department=request.user.department,
            status='PENDING'
        ).order_by('-created_at')
        approved_events = Event.objects.filter(
            department=request.user.department,
            status='HOD_APPROVED'
        ).order_by('-created_at')
        rejected_events = Event.objects.filter(
            department=request.user.department,
            status='HOD_REJECTED'
        ).order_by('-created_at')
        template_name = 'events/hod_event_approval.html'
    else:  # PRINCIPAL
        pending_events = Event.objects.filter(
            status='HOD_APPROVED'
        ).order_by('-created_at')
        approved_events = Event.objects.filter(
            status='PRINCIPAL_APPROVED'
        ).order_by('-created_at')
        rejected_events = Event.objects.filter(
            status='PRINCIPAL_REJECTED'
        ).order_by('-created_at')
        template_name = 'events/principal_event_approval.html'

    context = {
        'pending_events': pending_events,
        'approved_events': approved_events,
        'rejected_events': rejected_events
    }
    return render(request, template_name, context)



@login_required
@require_http_methods(['POST'])
def approve_event(request, event_id):
    if request.user.role not in ['HOD', 'PRINCIPAL']:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Access denied.'})
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    # Try to get event by ID first, then by event_id if that fails
    try:
        # First try to convert to integer and look up by id
        event_id_int = int(event_id)
        event = get_object_or_404(Event, id=event_id_int)
    except (ValueError, TypeError):
        # If conversion fails, look up by event_id string
        event = get_object_or_404(Event, event_id=event_id)
        
    remarks = request.POST.get('remarks', '')
    success = False
    message = ''

    if request.user.role == 'HOD':
        if event.status != 'PENDING':
            message = 'This event cannot be approved.'
            messages.error(request, message)
        else:
            event.status = 'HOD_APPROVED'
            event.hod_approval_date = timezone.now()
            event.save()
            success = True
            message = 'Event has been approved and sent to Principal.'
            messages.success(request, message)
    
    elif request.user.role == 'PRINCIPAL':
        if event.status != 'HOD_APPROVED':
            message = 'This event cannot be approved.'
            messages.error(request, message)
        else:
            event.status = 'PRINCIPAL_APPROVED'
            event.principal_approval_date = timezone.now()
            event.save()
            success = True
            message = 'Event has been approved successfully.'
            messages.success(request, message)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': success, 'message': message})
    
    # Redirect to the appropriate page based on user role
    if request.user.role == 'HOD':
        return redirect('hod_pending_events')
    else:  # PRINCIPAL
        return redirect('principal_pending_events')

@login_required
@require_http_methods(['POST'])
def reject_event(request, event_id):
    if request.user.role not in ['HOD', 'PRINCIPAL']:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Access denied.'})
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    # Try to get event by ID first, then by event_id if that fails
    try:
        # First try to convert to integer and look up by id
        event_id_int = int(event_id)
        event = get_object_or_404(Event, id=event_id_int)
    except (ValueError, TypeError):
        # If conversion fails, look up by event_id string
        event = get_object_or_404(Event, event_id=event_id)
        
    remarks = request.POST.get('remarks', '')
    success = False
    message = ''

    if request.user.role == 'HOD':
        if event.status != 'PENDING':
            message = 'This event cannot be rejected.'
            messages.error(request, message)
        else:
            event.status = 'HOD_REJECTED'
            event.save()
            success = True
            message = 'Event has been rejected.'
            messages.success(request, message)
    
    elif request.user.role == 'PRINCIPAL':
        if event.status != 'HOD_APPROVED':
            message = 'This event cannot be rejected.'
            messages.error(request, message)
        else:
            event.status = 'PRINCIPAL_REJECTED'
            event.save()
            success = True
            message = 'Event has been rejected.'
            messages.success(request, message)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': success, 'message': message})
    
    # Redirect to the appropriate page based on user role
    if request.user.role == 'HOD':
        return redirect('hod_pending_events')
    else:  # PRINCIPAL
        return redirect('principal_pending_events')

@login_required
@require_http_methods(['POST'])
def reject_event(request, event_id):
    if request.user.role not in ['HOD', 'PRINCIPAL']:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Access denied.'})
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    # Try to get event by ID first, then by event_id if that fails
    try:
        # First try to convert to integer and look up by id
        event_id_int = int(event_id)
        event = get_object_or_404(Event, id=event_id_int)
    except (ValueError, TypeError):
        # If conversion fails, look up by event_id string
        event = get_object_or_404(Event, event_id=event_id)
        
    remarks = request.POST.get('remarks', '')
    success = False
    message = ''

    if request.user.role == 'HOD':
        if event.status != 'PENDING':
            message = 'This event cannot be rejected.'
            messages.error(request, message)
        else:
            event.status = 'HOD_REJECTED'
            event.save()
            success = True
            message = 'Event has been rejected.'
            messages.success(request, message)
    
    elif request.user.role == 'PRINCIPAL':
        if event.status != 'HOD_APPROVED':
            message = 'This event cannot be rejected.'
            messages.error(request, message)
        else:
            event.status = 'PRINCIPAL_REJECTED'
            event.save()
            success = True
            message = 'Event has been rejected.'
            messages.success(request, message)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': success, 'message': message})
    
    return redirect('event_approval_list')

@login_required
def get_event_analytics(request, event_id):
    if request.user.role not in ['HOD', 'PRINCIPAL']:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Access denied.'})
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    # Try to get event by ID first, then by event_id if that fails
    try:
        # First try to convert to integer and look up by id
        event_id_int = int(event_id)
        event = get_object_or_404(Event, id=event_id_int)
    except (ValueError, TypeError):
        # If conversion fails, look up by event_id string
        event = get_object_or_404(Event, event_id=event_id)
    
    # Get historical events data
    historical_events = Event.objects.filter(
        status='PRINCIPAL_APPROVED',
        department=event.department
    ).exclude(event_id=event.event_id)

    if not historical_events:
        return JsonResponse({
            'success': True,
            'prediction': 'Not enough historical data',
            'message': 'Unable to make prediction due to insufficient historical data.'
        })
    
    try:
        # Import the event analysis function from utils
        from .utils import analyze_event_budget_name
        
        # Use the new analytics model that focuses on event name and budget
        analysis_result = analyze_event_budget_name(
            event_name=event.event_name,
            event_budget=float(event.budget),
            historical_events=historical_events
        )
        
        # Extract data from analysis result
        recommendation = analysis_result['recommendation']
        confidence_score = analysis_result['confidence']
        name_similarity = analysis_result['name_similarity']
        budget_analysis = analysis_result['budget_analysis']
        
        # Get similar events with similar names
        similar_events = name_similarity.get('most_similar_events', [])
        
        # Prepare response data
        response_data = {
            'success': True,
            'prediction': recommendation,
            'confidence': confidence_score,
            'name_similarity': {
                'avg_similarity': name_similarity.get('avg_similarity', 0),
                'max_similarity': name_similarity.get('max_similarity', 0),
                'similar_events': similar_events
            },
            'budget_analysis': {
                'avg_budget': budget_analysis.get('avg_budget', 0),
                'current_budget': budget_analysis.get('current_budget', 0),
                'budget_difference': budget_analysis.get('budget_difference', 0),
                'budget_percent_diff': budget_analysis.get('budget_percent_diff', 0),
                'similar_budget_events': budget_analysis.get('similar_budget_events', 0)
            },
            'message': 'Analysis based on event name and budget similarity.'
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        # Log the error for debugging
        print(f"Error in primary analytics model: {str(e)}")
        
        try:
            # Fallback to the original analytics model if there's an error
            # Prepare data for analysis with a limit on the number of events to process
            # This prevents processing too many events which could cause performance issues
            limited_events = historical_events[:50]  # Limit to 50 events for performance
            
            data = [{
                'budget': float(e.budget),
                'expected_attendees': e.expected_attendees,
                'registration_fee': float(e.registration_fee),
                'success': True  # Since these are approved events
            } for e in limited_events]

            # Create training dataset
            df = pd.DataFrame(data)
            X = df[['budget', 'expected_attendees', 'registration_fee']]
            y = df['success']

            # Train model with reduced complexity for faster processing
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            model = RandomForestClassifier(n_estimators=50)  # Reduced from 100 to 50 for speed
            model.fit(X_scaled, y)

            # Prepare current event data
            current_event_data = np.array([
                [float(event.budget), 
                event.expected_attendees, 
                float(event.registration_fee)]
            ])
            current_event_scaled = scaler.transform(current_event_data)

            # Make prediction
            prediction = model.predict_proba(current_event_scaled)[0]
            # Check if prediction has at least 2 elements before accessing index 1
            if len(prediction) > 1:
                success_probability = prediction[1] * 100
            else:
                # If prediction only has one element, use that value or default to 0
                success_probability = prediction[0] * 100 if prediction.size > 0 else 0

            # Get feature importance
            feature_importance = dict(zip(
                ['Budget', 'Expected Attendees', 'Registration Fee'],
                model.feature_importances_
            ))
            
            # Calculate budget comparison
            avg_budget = limited_events.aggregate(Avg('budget'))['budget__avg'] or 0
            budget_difference = float(event.budget) - float(avg_budget)
            budget_percent_diff = (budget_difference / float(avg_budget) * 100) if avg_budget > 0 else 0
            
            # Calculate attendees comparison
            avg_attendees = limited_events.aggregate(Avg('expected_attendees'))['expected_attendees__avg'] or 0
            attendees_difference = event.expected_attendees - avg_attendees
            attendees_percent_diff = (attendees_difference / avg_attendees * 100) if avg_attendees > 0 else 0
            
            # Get similar events with similar budget (within 20% range)
            budget_range_min = float(event.budget) * 0.8
            budget_range_max = float(event.budget) * 1.2
            similar_budget_events = limited_events.filter(budget__gte=budget_range_min, budget__lte=budget_range_max).count()
            
            # Determine recommendation strength based on confidence
            recommendation = 'Strongly Recommended for Approval' if success_probability > 85 else \
                            'Recommended for Approval' if success_probability > 70 else \
                            'Needs Review' if success_probability > 50 else \
                            'Not Recommended'

            # Include error message in response
            return JsonResponse({
                'success': True,
                'prediction': recommendation,
                'confidence': success_probability,
                'feature_importance': feature_importance,
                'similar_events': len(limited_events),
                'similar_budget_events': similar_budget_events,
                'avg_budget': float(avg_budget),
                'budget_difference': budget_difference,
                'budget_percent_diff': budget_percent_diff,
                'current_budget': float(event.budget),
                'avg_attendees': avg_attendees,
                'attendees_difference': attendees_difference,
                'attendees_percent_diff': attendees_percent_diff,
                'current_attendees': event.expected_attendees,
                'message': f'Using optimized fallback model due to error in primary model.'
            })
        except Exception as fallback_error:
            # If both models fail, return a simple response
            print(f"Error in fallback analytics model: {str(fallback_error)}")
            return JsonResponse({
                'success': False,
                'message': 'Unable to analyze event data. Please try again later.',
                'error': str(fallback_error)
            })

@login_required
def create_assessment(request):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Only event coordinators can create assessments.')
        return redirect('dashboard')

    events = Event.objects.filter(coordinator=request.user, status='PRINCIPAL_APPROVED')

    if request.method == 'POST':
        try:
            event = get_object_or_404(Event, id=request.POST['event'])
            title = request.POST['title']
            description = request.POST['description']
            due_date = request.POST['due_date']
            is_ai_generated = 'is_ai_generated' in request.POST
            
            if is_ai_generated:
                # Use AI to generate assessment with 10 questions
                from .ai_assessment import generate_ai_assessment
                assessment = generate_ai_assessment(event, title, description, due_date)
                messages.success(request, 'AI Assessment with 10 questions created successfully!')
            else:
                # Create regular assessment
                passing_score = int(request.POST.get('passing_score', 3))
                assessment = EventAssessment(
                    event=event,
                    title=title,
                    description=description,
                    due_date=due_date,
                    total_marks=10,  # 10 questions, 1 mark each
                    passing_score=passing_score
                )
                assessment.save()
                
                # Process custom questions
                from .models import Question, QuestionOption, NumericalAnswer
                
                # We expect 10 questions (0-9)
                for i in range(10):
                    question_text = request.POST.get(f'question_text_{i}')
                    question_type = request.POST.get(f'question_type_{i}')
                    
                    if question_text and question_type:
                        # Create the question
                        question = Question.objects.create(
                            assessment=assessment,
                            question_text=question_text,
                            question_type=question_type,
                            marks=1
                        )
                        
                        # Process options based on question type
                        if question_type in ['MCQ', 'MSQ']:
                            # Get the correct option(s)
                            if question_type == 'MCQ':
                                correct_option = request.POST.get(f'correct_option_{i}')
                                correct_options = [correct_option] if correct_option else []
                            else:  # MSQ
                                correct_options = request.POST.getlist(f'correct_options_{i}')
                            
                            # Create options (4 options for MCQ/MSQ)
                            for j in range(4):
                                option_text = request.POST.get(f'option_text_{i}_{j}')
                                if option_text:
                                    is_correct = str(j) in correct_options
                                    QuestionOption.objects.create(
                                        question=question,
                                        option_text=option_text,
                                        is_correct=is_correct
                                    )
                        
                        elif question_type == 'NAT':
                            # Process numerical answer
                            correct_answer = request.POST.get(f'correct_answer_{i}')
                            tolerance = request.POST.get(f'tolerance_{i}', 0.1)
                            
                            if correct_answer:
                                NumericalAnswer.objects.create(
                                    question=question,
                                    correct_answer=float(correct_answer),
                                    tolerance=float(tolerance)
                                )
                
                messages.success(request, 'Assessment with custom questions created successfully!')
                
            return redirect('assessment_list')
        except Exception as e:
            messages.error(request, f'Error creating assessment: {str(e)}')

    return render(request, 'events/create_assessment.html', {'events': events})

@login_required
def assessment_list(request):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    assessments = EventAssessment.objects.filter(event__coordinator=request.user)
    return render(request, 'events/assessment_list.html', {'assessments': assessments})

@login_required
def student_assessment_list(request):
    if not request.user.role == 'STUDENT':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    assessments = EventAssessment.objects.filter(event__registrations__student=request.user)
    now = timezone.now()
    return render(request, 'events/student_assessment_list.html', {
        'assessments': assessments,
        'now': now
    })

@login_required
def submit_assessment(request, assessment_id):
    if not request.user.role == 'STUDENT':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    assessment = get_object_or_404(EventAssessment, id=assessment_id)
    
    if assessment.due_date < timezone.now():
        messages.error(request, 'Assessment submission deadline has passed.')
        return redirect('student_assessment_list')

    # Check if this assessment has questions (AI-generated or custom)
    has_questions = assessment.questions.exists()
    
    if request.method == 'POST':
        try:
            # Check if a submission already exists for this student and assessment
            try:
                submission = AssessmentSubmission.objects.get(
                    assessment=assessment,
                    student=request.user
                )
                # If we're here, a submission already exists
                if not has_questions and 'submission_file' in request.FILES:
                    submission.submission_file = request.FILES['submission_file']
                    submission.save()
            except AssessmentSubmission.DoesNotExist:
                # Create a new submission if one doesn't exist
                submission = AssessmentSubmission(
                    assessment=assessment,
                    student=request.user
                )
                
                # For regular file upload assessments
                if not has_questions and 'submission_file' in request.FILES:
                    submission.submission_file = request.FILES['submission_file']
                
                submission.save()
            
            # For AI-generated assessments with questions
            if has_questions:
                from .models import StudentAnswer, Question, QuestionOption
                
                # If this is an existing submission, clear previous answers
                if AssessmentSubmission.objects.filter(assessment=assessment, student=request.user).exists():
                    StudentAnswer.objects.filter(submission=submission).delete()
                
                # Process each question
                for question in assessment.questions.all():
                    answer = StudentAnswer(submission=submission, question=question)
                    
                    if question.question_type == 'MCQ':
                        # Single choice question
                        option_id = request.POST.get(f'question_{question.id}')
                        if option_id:
                            answer.save()  # Save first to allow many-to-many relationship
                            option = QuestionOption.objects.get(id=option_id)
                            answer.selected_options.add(option)
                    
                    elif question.question_type == 'MSQ':
                        # Multiple choice question
                        option_ids = request.POST.getlist(f'question_{question.id}')
                        if option_ids:
                            answer.save()  # Save first to allow many-to-many relationship
                            for option_id in option_ids:
                                option = QuestionOption.objects.get(id=option_id)
                                answer.selected_options.add(option)
                    
                    elif question.question_type == 'NAT':
                        # Numerical answer
                        numerical_value = request.POST.get(f'question_{question.id}')
                        if numerical_value:
                            try:
                                answer.numerical_value = float(numerical_value)
                                answer.save()
                            except ValueError:
                                pass  # Invalid numerical input
                
                # Auto-grade the submission
                from .ai_assessment import evaluate_student_submission
                score = evaluate_student_submission(submission)
                
                # Check if student passed the assessment
                passed = score >= assessment.passing_score
                
                # Check if certificate is generated
                from .models import EventRegistration
                has_certificate = EventRegistration.objects.filter(
                    event=assessment.event,
                    student=request.user,
                    certificate_generated=True
                ).exists()
                
                # If passed, check and generate certificate
                if passed:
                    from .utils import check_and_generate_certificates
                    check_and_generate_certificates(assessment.event)
                
                # Redirect to assessment result page
                return redirect('assessment_result', submission_id=submission.id)
            else:
                messages.success(request, 'Assessment submitted successfully!')
                
                # For file upload assessments, redirect to assessment list
                return redirect('student_assessment_list')
        except Exception as e:
            messages.error(request, f'Error submitting assessment: {str(e)}')

    context = {
        'assessment': assessment,
        'has_questions': has_questions,
        'questions': assessment.questions.all() if has_questions else None
    }
    return render(request, 'events/submit_assessment.html', context)

@login_required
def assessment_result(request, submission_id):
    if not request.user.role == 'STUDENT':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    submission = get_object_or_404(AssessmentSubmission, id=submission_id)
    assessment = submission.assessment
    
    # Ensure the student can only view their own submissions
    if submission.student != request.user:
        messages.error(request, 'Access denied.')
        return redirect('student_assessment_list')
    
    # Check if student passed the assessment
    passed = submission.score >= assessment.passing_score
    
    # Check if certificate is generated
    has_certificate = EventRegistration.objects.filter(
        event=assessment.event,
        student=request.user,
        certificate_generated=True
    ).exists()
    
    # Get questions and answers
    questions = assessment.questions.all()
    answers = {}
    
    for question in questions:
        try:
            answer = StudentAnswer.objects.get(submission=submission, question=question)
            answers[question.id] = answer
        except StudentAnswer.DoesNotExist:
            pass
    
    # Create a template filter to get items from a dictionary
    from django.template.defaulttags import register
    
    @register.filter
    def get_item(dictionary, key):
        return dictionary.get(key)
    
    context = {
        'submission': submission,
        'assessment': assessment,
        'passed': passed,
        'has_certificate': has_certificate,
        'questions': questions,
        'answers': answers
    }
    
    return render(request, 'events/assessment_result.html', context)

@login_required
def grade_assessment(request, submission_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Only event coordinators can grade assessments.')
        return redirect('dashboard')

    submission = get_object_or_404(AssessmentSubmission, id=submission_id)
    
    if submission.assessment.event.coordinator != request.user:
        messages.error(request, 'You can only grade assessments for your events.')
        return redirect('assessment_list')

    if request.method == 'POST':
        try:
            submission.score = request.POST['score']
            submission.save()
            messages.success(request, 'Assessment graded successfully!')
            
            # Check if all assessments for this event are graded
            event = submission.assessment.event
            check_and_generate_certificates(event)
            
            # Redirect back to the assessment submissions page instead of the assessment list
            return redirect('assessment_submissions', assessment_id=submission.assessment.id)
        except Exception as e:
            messages.error(request, f'Error grading assessment: {str(e)}')

    return render(request, 'events/grade_assessment.html', {'submission': submission})



@login_required
def available_events(request):
    if not request.user.role == 'STUDENT':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    # Get all principal approved events
    events = Event.objects.filter(
        status='PRINCIPAL_APPROVED',
        date__gte=timezone.now().date()  # Only show upcoming events
    ).order_by('date', 'time')

    # Get the events that the student is already registered for
    registered_events = Event.objects.filter(registrations__student=request.user)

    return render(request, 'events/available_events.html', {
        'events': events,
        'registered_events': registered_events
    })

@login_required
def certificates(request):
    if request.user.role == 'EVENT_COORDINATOR':
        # For coordinators - show certificates for their events
        events = Event.objects.filter(
            coordinator=request.user,
            status='PRINCIPAL_APPROVED'
        ).order_by('-date')
        return render(request, 'events/certificates.html', {'events': events})
    elif request.user.role == 'STUDENT':
        # For students - show events they've participated in that have certificates
        events = Event.objects.filter(
            registrations__student=request.user,
            status='PRINCIPAL_APPROVED'
        ).order_by('-date')
        return render(request, 'events/certificates.html', {'events': events})
    
    # Default case for other roles
    messages.error(request, 'Access denied.')
    return redirect('dashboard')


@login_required
def analytics(request):
    if request.user.role not in ['HOD', 'PRINCIPAL']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    # Filter events based on user role
    if request.user.role == 'HOD':
        events = Event.objects.filter(department=request.user.department)
    else:  # PRINCIPAL
        events = Event.objects.all()

    # Calculate analytics data
    total_events = events.count()
    approved_events = events.filter(status='PRINCIPAL_APPROVED').count()
    pending_events = events.filter(status='PENDING').count()
    total_budget = events.aggregate(Sum('budget'))['budget__sum'] or 0

    # Event statistics by department
    dept_stats = events.values('department__name').annotate(
        event_count=Count('id'),
        avg_attendees=Avg('expected_attendees'),
        total_dept_budget=Sum('budget')
    )

    # Assessment statistics
    assessments = EventAssessment.objects.filter(event__in=events)
    total_assessments = assessments.count()
    submissions = AssessmentSubmission.objects.filter(assessment__in=assessments)
    submission_rate = (submissions.count() / total_assessments) * 100 if total_assessments > 0 else 0
    avg_score = submissions.aggregate(Avg('score'))['score__avg'] or 0

    context = {
        'total_events': total_events,
        'approved_events': approved_events,
        'pending_events': pending_events,
        'total_budget': total_budget,
        'dept_stats': dept_stats,
        'total_assessments': total_assessments,
        'submission_rate': round(submission_rate, 2),
        'avg_score': round(avg_score, 2),
    }

    return render(request, 'events/analytics.html', context)


@login_required
def event_scheduler(request):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Only event coordinators can schedule events.')
        return redirect('dashboard')

    # Get all approved events for this coordinator
    events = Event.objects.filter(
        coordinator=request.user,
        status='PRINCIPAL_APPROVED'
    ).order_by('-date')
    
    # Get existing schedules
    event_schedules = EventSchedule.objects.filter(event__coordinator=request.user).order_by('event__event_name', 'start_time')
    
    if request.method == 'POST':
        try:
            event_id = request.POST.get('event')
            event = get_object_or_404(Event, id=event_id, coordinator=request.user)
            
            # Get all session data from form
            session_names = request.POST.getlist('session_name[]')
            start_times = request.POST.getlist('start_time[]')
            end_times = request.POST.getlist('end_time[]')
            
            # Create schedule entries
            for i in range(len(session_names)):
                EventSchedule.objects.create(
                    event=event,
                    session_name=session_names[i],
                    start_time=start_times[i],
                    end_time=end_times[i]
                )
            
            messages.success(request, 'Event schedule created successfully!')
            return redirect('event_scheduler')
        except Exception as e:
            messages.error(request, f'Error creating schedule: {str(e)}')
    
    return render(request, 'events/event_scheduler.html', {
        'events': events,
        'event_schedules': event_schedules
    })

@login_required
@require_http_methods(['POST'])
def delete_schedule(request, schedule_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        return JsonResponse({'success': False, 'message': 'Access denied.'})
    
    schedule = get_object_or_404(EventSchedule, id=schedule_id)
    
    # Check if the user is the coordinator of the event
    if schedule.event.coordinator != request.user:
        return JsonResponse({'success': False, 'message': 'You can only delete schedules for your events.'})
    
    try:
        schedule.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


    return redirect('event_approval_list')


@login_required
def event_participants(request, event_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        return JsonResponse({'success': False, 'message': 'Access denied.'})
    
    event = get_object_or_404(Event, id=event_id, coordinator=request.user)
    registrations = event.registrations.all()
    
    participants = []
    for registration in registrations:
        participants.append({
            'student_id': registration.student.username,
            'name': registration.student.get_full_name(),
            'email': registration.student.email,
            'certificate_generated': registration.certificate_generated
        })
    
    return JsonResponse({
        'success': True,
        'participants': participants
    })

@login_required
@require_http_methods(['POST'])
def generate_certificates(request, event_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        return JsonResponse({'success': False, 'message': 'Access denied.'})
    
    event = get_object_or_404(Event, id=event_id, coordinator=request.user)
    registrations = event.registrations.all()
    
    if not registrations:
        return JsonResponse({'success': False, 'message': 'No participants found for this event.'})
    
    try:
        from .utils import generate_certificate
        
        for registration in registrations:
            if not registration.certificate_generated:
                certificate_url, verification_id = generate_certificate(event, registration.student)
                registration.certificate_url = certificate_url
                registration.certificate_generated = True
                registration.save()
        
        return JsonResponse({'success': True, 'message': f'Generated certificates for {registrations.count()} participants.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
def hod_pending_events(request):
    if request.user.role != 'HOD':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    pending_events = Event.objects.filter(
        department=request.user.department,
        status='PENDING'
    ).order_by('-created_at')
    
    context = {
        'pending_events': pending_events
    }
    return render(request, 'events/hod_pending_events.html', context)

@login_required
def hod_approved_events(request):
    if request.user.role != 'HOD':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    approved_events = Event.objects.filter(
        department=request.user.department,
        status='HOD_APPROVED'
    ).order_by('-created_at')
    
    context = {
        'approved_events': approved_events
    }
    return render(request, 'events/hod_approved_events.html', context)

@login_required
def hod_rejected_events(request):
    if request.user.role != 'HOD':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    rejected_events = Event.objects.filter(
        department=request.user.department,
        status='HOD_REJECTED'
    ).order_by('-created_at')
    
    context = {
        'rejected_events': rejected_events
    }
    return render(request, 'events/hod_rejected_events.html', context)

@login_required
def principal_pending_events(request):
    if request.user.role != 'PRINCIPAL':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    pending_events = Event.objects.filter(
        status='HOD_APPROVED'
    ).order_by('-created_at')
    
    context = {
        'pending_events': pending_events
    }
    return render(request, 'events/principal_pending_events.html', context)

@login_required
def principal_approved_events(request):
    if request.user.role != 'PRINCIPAL':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    approved_events = Event.objects.filter(
        status='PRINCIPAL_APPROVED'
    ).order_by('-created_at')
    
    context = {
        'approved_events': approved_events
    }
    return render(request, 'events/principal_approved_events.html', context)

@login_required
def principal_rejected_events(request):
    if request.user.role != 'PRINCIPAL':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    rejected_events = Event.objects.filter(
        status='PRINCIPAL_REJECTED'
    ).order_by('-created_at')
    
    context = {
        'rejected_events': rejected_events
    }
    return render(request, 'events/principal_rejected_events.html', context)


@login_required
def assessment_detail(request, assessment_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    assessment = get_object_or_404(EventAssessment, id=assessment_id)
    
    # Check if the user is the coordinator of the event
    if assessment.event.coordinator != request.user:
        messages.error(request, 'You can only view assessments for your events.')
        return redirect('assessment_list')
    
    return render(request, 'events/assessment_detail.html', {'assessment': assessment})

@login_required
def assessment_submissions(request, assessment_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    assessment = get_object_or_404(EventAssessment, id=assessment_id)
    
    # Check if the user is the coordinator of the event
    if assessment.event.coordinator != request.user:
        messages.error(request, 'You can only view submissions for your assessments.')
        return redirect('assessment_list')
    
    submissions = assessment.submissions.all().order_by('-submitted_at')
    return render(request, 'events/assessment_submissions.html', {
        'assessment': assessment,
        'submissions': submissions
    })

@login_required
def edit_assessment(request, assessment_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    assessment = get_object_or_404(EventAssessment, id=assessment_id)
    
    # Check if the user is the coordinator of the event
    if assessment.event.coordinator != request.user:
        messages.error(request, 'You can only edit assessments for your events.')
        return redirect('assessment_list')
    
    # Get all approved events for this coordinator
    events = Event.objects.filter(coordinator=request.user, status='PRINCIPAL_APPROVED')
    
    if request.method == 'POST':
        try:
            assessment.title = request.POST['title']
            assessment.description = request.POST['description']
            assessment.due_date = request.POST['due_date']
            assessment.total_marks = request.POST['total_marks']
            assessment.save()
            messages.success(request, 'Assessment updated successfully!')
            return redirect('assessment_list')
        except Exception as e:
            messages.error(request, f'Error updating assessment: {str(e)}')
    
    return render(request, 'events/edit_assessment.html', {'assessment': assessment, 'events': events})

@login_required
def delete_assessment(request, assessment_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    assessment = get_object_or_404(EventAssessment, id=assessment_id)
    
    # Check if the user is the coordinator of the event
    if assessment.event.coordinator != request.user:
        messages.error(request, 'You can only delete assessments for your events.')
        return redirect('assessment_list')
    
    if request.method == 'POST':
        try:
            assessment.delete()
            messages.success(request, 'Assessment deleted successfully!')
            return redirect('assessment_list')
        except Exception as e:
            messages.error(request, f'Error deleting assessment: {str(e)}')
    
    return render(request, 'events/delete_assessment.html', {'assessment': assessment})

@login_required
def submit_feedback(request, event_id):
    if request.user.role != 'STUDENT':
        messages.error(request, 'Only students can submit feedback.')
        return redirect('dashboard')
    
    event = get_object_or_404(Event, id=event_id)
    
    # Check if student is registered for this event
    registration = get_object_or_404(EventRegistration, event=event, student=request.user)
    
    # Check if certificate is generated
    if not registration.certificate_generated:
        messages.error(request, 'You can only provide feedback after receiving a certificate.')
        return redirect('certificates')
    
    # Check if feedback already exists
    feedback_exists = EventFeedback.objects.filter(event=event, student=request.user).exists()
    if feedback_exists:
        messages.info(request, 'You have already submitted feedback for this event.')
        return redirect('certificates')
    
    if request.method == 'POST':
        try:
            rating = int(request.POST.get('rating'))
            feedback_text = request.POST.get('feedback_text')
            
            if not rating or not feedback_text:
                messages.error(request, 'Please provide both rating and feedback.')
                return render(request, 'events/submit_feedback.html', {'event': event})
            
            # Create feedback
            EventFeedback.objects.create(
                event=event,
                student=request.user,
                rating=rating,
                feedback_text=feedback_text
            )
            
            messages.success(request, 'Thank you for your feedback!')
            return redirect('certificates')
        except Exception as e:
            messages.error(request, f'Error submitting feedback: {str(e)}')
    
    return render(request, 'events/submit_feedback.html', {'event': event})

@login_required
def event_feedback_report(request, event_id):
    if request.user.role not in ['EVENT_COORDINATOR', 'HOD']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    event = get_object_or_404(Event, id=event_id)
    
    # Check if user has permission to view this event's feedback
    if request.user.role == 'EVENT_COORDINATOR' and event.coordinator != request.user:
        messages.error(request, 'You can only view feedback for your events.')
        return redirect('my_events')
    
    if request.user.role == 'HOD' and event.department != request.user.department:
        messages.error(request, 'You can only view feedback for events in your department.')
        return redirect('dashboard')
    
    # Get all feedback for this event
    feedbacks = EventFeedback.objects.filter(event=event).order_by('-submitted_date')
    feedback_count = feedbacks.count()
    
    # Calculate average rating
    avg_rating = feedbacks.aggregate(Avg('rating'))['rating__avg'] or 0
    
    # Calculate feedback rate (percentage of participants who gave feedback)
    total_participants = EventRegistration.objects.filter(event=event).count()
    feedback_rate = (feedback_count / total_participants * 100) if total_participants > 0 else 0
    
    # Get rating distribution
    rating_5_count = feedbacks.filter(rating=5).count()
    rating_4_count = feedbacks.filter(rating=4).count()
    rating_3_count = feedbacks.filter(rating=3).count()
    rating_2_count = feedbacks.filter(rating=2).count()
    rating_1_count = feedbacks.filter(rating=1).count()
    
    # Calculate percentages for progress bars
    rating_5_percent = (rating_5_count / feedback_count * 100) if feedback_count > 0 else 0
    rating_4_percent = (rating_4_count / feedback_count * 100) if feedback_count > 0 else 0
    rating_3_percent = (rating_3_count / feedback_count * 100) if feedback_count > 0 else 0
    rating_2_percent = (rating_2_count / feedback_count * 100) if feedback_count > 0 else 0
    rating_1_percent = (rating_1_count / feedback_count * 100) if feedback_count > 0 else 0
    
    context = {
        'event': event,
        'feedbacks': feedbacks,
        'feedback_count': feedback_count,
        'avg_rating': avg_rating,
        'feedback_rate': feedback_rate,
        'rating_5_count': rating_5_count,
        'rating_4_count': rating_4_count,
        'rating_3_count': rating_3_count,
        'rating_2_count': rating_2_count,
        'rating_1_count': rating_1_count,
        'rating_5_percent': rating_5_percent,
        'rating_4_percent': rating_4_percent,
        'rating_3_percent': rating_3_percent,
        'rating_2_percent': rating_2_percent,
        'rating_1_percent': rating_1_percent
    }
    
    return render(request, 'events/feedback_report.html', context)

@login_required
def register_event(request, event_id):
    if not request.user.role == 'STUDENT':
        messages.error(request, 'Only students can register for events.')
        return redirect('dashboard')

    # Try to get event by ID first, then by event_id if that fails
    try:
        # First try to convert to integer and look up by id
        event_id_int = int(event_id)
        event = get_object_or_404(Event, id=event_id_int)
    except (ValueError, TypeError):
        # If conversion fails, look up by event_id string
        event = get_object_or_404(Event, event_id=event_id)
    
    # Check if event is approved
    if event.status != 'PRINCIPAL_APPROVED':
        messages.error(request, 'This event is not available for registration.')
        return redirect('available_events')
    
    # Check if student is already registered
    if EventRegistration.objects.filter(event=event, student=request.user).exists():
        messages.info(request, 'You are already registered for this event.')
        return redirect('available_events')
    
    # Create registration
    try:
        registration = EventRegistration(event=event, student=request.user)
        registration.save()
        messages.success(request, f'Successfully registered for {event.event_name}!')
    except Exception as e:
        messages.error(request, f'Error registering for event: {str(e)}')
    
    return redirect('available_events')

@login_required
def event_participants(request, event_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        return JsonResponse({'success': False, 'message': 'Access denied.'})
    
    event = get_object_or_404(Event, id=event_id, coordinator=request.user)
    registrations = event.registrations.all()
    
    participants = []
    for registration in registrations:
        participants.append({
            'student_id': registration.student.username,
            'name': registration.student.get_full_name(),
            'email': registration.student.email,
            'certificate_generated': registration.certificate_generated
        })
    
    return JsonResponse({
        'success': True,
        'participants': participants
    })

@login_required
@require_http_methods(['POST'])
def generate_certificates(request, event_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        return JsonResponse({'success': False, 'message': 'Access denied.'})
    
    event = get_object_or_404(Event, id=event_id, coordinator=request.user)
    registrations = event.registrations.all()
    
    if not registrations:
        return JsonResponse({'success': False, 'message': 'No participants found for this event.'})
    
    try:
        from .utils import generate_certificate
        
        for registration in registrations:
            if not registration.certificate_generated:
                certificate_url, verification_id = generate_certificate(event, registration.student)
                registration.certificate_url = certificate_url
                registration.certificate_generated = True
                registration.save()
        
        return JsonResponse({'success': True, 'message': f'Generated certificates for {registrations.count()} participants.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
def hod_pending_events(request):
    if request.user.role != 'HOD':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    pending_events = Event.objects.filter(
        department=request.user.department,
        status='PENDING'
    ).order_by('-created_at')
    
    context = {
        'pending_events': pending_events
    }
    return render(request, 'events/hod_pending_events.html', context)

@login_required
def hod_approved_events(request):
    if request.user.role != 'HOD':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    approved_events = Event.objects.filter(
        department=request.user.department,
        status='HOD_APPROVED'
    ).order_by('-created_at')
    
    context = {
        'approved_events': approved_events
    }
    return render(request, 'events/hod_approved_events.html', context)

@login_required
def hod_rejected_events(request):
    if request.user.role != 'HOD':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    rejected_events = Event.objects.filter(
        department=request.user.department,
        status='HOD_REJECTED'
    ).order_by('-created_at')
    
    context = {
        'rejected_events': rejected_events
    }
    return render(request, 'events/hod_rejected_events.html', context)

@login_required
def principal_pending_events(request):
    if request.user.role != 'PRINCIPAL':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    pending_events = Event.objects.filter(
        status='HOD_APPROVED'
    ).order_by('-created_at')
    
    context = {
        'pending_events': pending_events
    }
    return render(request, 'events/principal_pending_events.html', context)

@login_required
def principal_approved_events(request):
    if request.user.role != 'PRINCIPAL':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    approved_events = Event.objects.filter(
        status='PRINCIPAL_APPROVED'
    ).order_by('-created_at')
    
    context = {
        'approved_events': approved_events
    }
    return render(request, 'events/principal_approved_events.html', context)

@login_required
def principal_rejected_events(request):
    if request.user.role != 'PRINCIPAL':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    rejected_events = Event.objects.filter(
        status='PRINCIPAL_REJECTED'
    ).order_by('-created_at')
    
    context = {
        'rejected_events': rejected_events
    }
    return render(request, 'events/principal_rejected_events.html', context)


@login_required
def assessment_detail(request, assessment_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    assessment = get_object_or_404(EventAssessment, id=assessment_id)
    
    # Check if the user is the coordinator of the event
    if assessment.event.coordinator != request.user:
        messages.error(request, 'You can only view assessments for your events.')
        return redirect('assessment_list')
    
    return render(request, 'events/assessment_detail.html', {'assessment': assessment})

@login_required
def assessment_submissions(request, assessment_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    assessment = get_object_or_404(EventAssessment, id=assessment_id)
    
    # Check if the user is the coordinator of the event
    if assessment.event.coordinator != request.user:
        messages.error(request, 'You can only view submissions for your assessments.')
        return redirect('assessment_list')
    
    submissions = assessment.submissions.all().order_by('-submitted_at')
    return render(request, 'events/assessment_submissions.html', {
        'assessment': assessment,
        'submissions': submissions
    })

@login_required
def edit_assessment(request, assessment_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    assessment = get_object_or_404(EventAssessment, id=assessment_id)
    
    # Check if the user is the coordinator of the event
    if assessment.event.coordinator != request.user:
        messages.error(request, 'You can only edit assessments for your events.')
        return redirect('assessment_list')
    
    # Get all approved events for this coordinator
    events = Event.objects.filter(coordinator=request.user, status='PRINCIPAL_APPROVED')
    
    if request.method == 'POST':
        try:
            assessment.title = request.POST['title']
            assessment.description = request.POST['description']
            assessment.due_date = request.POST['due_date']
            assessment.total_marks = request.POST['total_marks']
            assessment.save()
            messages.success(request, 'Assessment updated successfully!')
            return redirect('assessment_list')
        except Exception as e:
            messages.error(request, f'Error updating assessment: {str(e)}')
    
    return render(request, 'events/edit_assessment.html', {'assessment': assessment, 'events': events})

@login_required
def delete_assessment(request, assessment_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    assessment = get_object_or_404(EventAssessment, id=assessment_id)
    
    # Check if the user is the coordinator of the event
    if assessment.event.coordinator != request.user:
        messages.error(request, 'You can only delete assessments for your events.')
        return redirect('assessment_list')
    
    if request.method == 'POST':
        try:
            assessment.delete()
            messages.success(request, 'Assessment deleted successfully!')
            return redirect('assessment_list')
        except Exception as e:
            messages.error(request, f'Error deleting assessment: {str(e)}')
    
    return render(request, 'events/delete_assessment.html', {'assessment': assessment})

@login_required
def submit_feedback(request, event_id):
    if request.user.role != 'STUDENT':
        messages.error(request, 'Only students can submit feedback.')
        return redirect('dashboard')
    
    event = get_object_or_404(Event, id=event_id)
    
    # Check if student is registered for this event
    registration = get_object_or_404(EventRegistration, event=event, student=request.user)
    
    # Check if certificate is generated
    if not registration.certificate_generated:
        messages.error(request, 'You can only provide feedback after receiving a certificate.')
        return redirect('certificates')
    
    # Check if feedback already exists
    feedback_exists = EventFeedback.objects.filter(event=event, student=request.user).exists()
    if feedback_exists:
        messages.info(request, 'You have already submitted feedback for this event.')
        return redirect('certificates')
    
    if request.method == 'POST':
        try:
            rating = int(request.POST.get('rating'))
            feedback_text = request.POST.get('feedback_text')
            
            if not rating or not feedback_text:
                messages.error(request, 'Please provide both rating and feedback.')
                return render(request, 'events/submit_feedback.html', {'event': event})
            
            # Create feedback
            EventFeedback.objects.create(
                event=event,
                student=request.user,
                rating=rating,
                feedback_text=feedback_text
            )
            
            messages.success(request, 'Thank you for your feedback!')
            return redirect('certificates')
        except Exception as e:
            messages.error(request, f'Error submitting feedback: {str(e)}')
    
    return render(request, 'events/submit_feedback.html', {'event': event})

@login_required
def event_feedback_report(request, event_id):
    if request.user.role not in ['EVENT_COORDINATOR', 'HOD']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    event = get_object_or_404(Event, id=event_id)
    
    # Check if user has permission to view this event's feedback
    if request.user.role == 'EVENT_COORDINATOR' and event.coordinator != request.user:
        messages.error(request, 'You can only view feedback for your events.')
        return redirect('my_events')
    
    if request.user.role == 'HOD' and event.department != request.user.department:
        messages.error(request, 'You can only view feedback for events in your department.')
        return redirect('dashboard')
    
    # Get all feedback for this event
    feedbacks = EventFeedback.objects.filter(event=event).order_by('-submitted_date')
    feedback_count = feedbacks.count()
    
    # Calculate average rating
    avg_rating = feedbacks.aggregate(Avg('rating'))['rating__avg'] or 0
    
    # Calculate feedback rate (percentage of participants who gave feedback)
    total_participants = EventRegistration.objects.filter(event=event).count()
    feedback_rate = (feedback_count / total_participants * 100) if total_participants > 0 else 0
    
    # Get rating distribution
    rating_5_count = feedbacks.filter(rating=5).count()
    rating_4_count = feedbacks.filter(rating=4).count()
    rating_3_count = feedbacks.filter(rating=3).count()
    rating_2_count = feedbacks.filter(rating=2).count()
    rating_1_count = feedbacks.filter(rating=1).count()
    
    # Calculate percentages for progress bars
    rating_5_percent = (rating_5_count / feedback_count * 100) if feedback_count > 0 else 0
    rating_4_percent = (rating_4_count / feedback_count * 100) if feedback_count > 0 else 0
    rating_3_percent = (rating_3_count / feedback_count * 100) if feedback_count > 0 else 0
    rating_2_percent = (rating_2_count / feedback_count * 100) if feedback_count > 0 else 0
    rating_1_percent = (rating_1_count / feedback_count * 100) if feedback_count > 0 else 0
    
    context = {
        'event': event,
        'feedbacks': feedbacks,
        'feedback_count': feedback_count,
        'avg_rating': avg_rating,
        'feedback_rate': feedback_rate,
        'rating_5_count': rating_5_count,
        'rating_4_count': rating_4_count,
        'rating_3_count': rating_3_count,
        'rating_2_count': rating_2_count,
        'rating_1_count': rating_1_count,
        'rating_5_percent': rating_5_percent,
        'rating_4_percent': rating_4_percent,
        'rating_3_percent': rating_3_percent,
        'rating_2_percent': rating_2_percent,
        'rating_1_percent': rating_1_percent
    }
    
    return render(request, 'events/feedback_report.html', context)

@login_required
def register_event(request, event_id):
    if not request.user.role == 'STUDENT':
        messages.error(request, 'Only students can register for events.')
        return redirect('dashboard')

    # Try to get event by ID first, then by event_id if that fails
    try:
        # First try to convert to integer and look up by id
        event_id_int = int(event_id)
        event = get_object_or_404(Event, id=event_id_int)
    except (ValueError, TypeError):
        # If conversion fails, look up by event_id string
        event = get_object_or_404(Event, event_id=event_id)
    
    # Check if event is approved
    if event.status != 'PRINCIPAL_APPROVED':
        messages.error(request, 'This event is not available for registration.')
        return redirect('available_events')
    
    # Check if student is already registered
    if EventRegistration.objects.filter(event=event, student=request.user).exists():
        messages.info(request, 'You are already registered for this event.')
        return redirect('available_events')
    
    # Create registration
    try:
        registration = EventRegistration(event=event, student=request.user)
        registration.save()
        messages.success(request, f'Successfully registered for {event.event_name}!')
    except Exception as e:
        messages.error(request, f'Error registering for event: {str(e)}')
    
    return redirect('available_events')

@login_required
def event_participants(request, event_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        return JsonResponse({'success': False, 'message': 'Access denied.'})
    
    event = get_object_or_404(Event, id=event_id, coordinator=request.user)
    registrations = event.registrations.all()
    
    participants = []
    for registration in registrations:
        participants.append({
            'student_id': registration.student.username,
            'name': registration.student.get_full_name(),
            'email': registration.student.email,
            'certificate_generated': registration.certificate_generated
        })
    
    return JsonResponse({
        'success': True,
        'participants': participants
    })

@login_required
@require_http_methods(['POST'])
def generate_certificates(request, event_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        return JsonResponse({'success': False, 'message': 'Access denied.'})
    
    event = get_object_or_404(Event, id=event_id, coordinator=request.user)
    registrations = event.registrations.all()
    
    if not registrations:
        return JsonResponse({'success': False, 'message': 'No participants found for this event.'})
    
    try:
        from .utils import generate_certificate
        
        for registration in registrations:
            if not registration.certificate_generated:
                certificate_url, verification_id = generate_certificate(event, registration.student)
                registration.certificate_url = certificate_url
                registration.certificate_generated = True
                registration.save()
        
        return JsonResponse({'success': True, 'message': f'Generated certificates for {registrations.count()} participants.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
def hod_pending_events(request):
    if request.user.role != 'HOD':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    pending_events = Event.objects.filter(
        department=request.user.department,
        status='PENDING'
    ).order_by('-created_at')
    
    context = {
        'pending_events': pending_events
    }
    return render(request, 'events/hod_pending_events.html', context)

@login_required
def hod_approved_events(request):
    if request.user.role != 'HOD':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    approved_events = Event.objects.filter(
        department=request.user.department,
        status='HOD_APPROVED'
    ).order_by('-created_at')
    
    context = {
        'approved_events': approved_events
    }
    return render(request, 'events/hod_approved_events.html', context)

@login_required
def hod_rejected_events(request):
    if request.user.role != 'HOD':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    rejected_events = Event.objects.filter(
        department=request.user.department,
        status='HOD_REJECTED'
    ).order_by('-created_at')
    
    context = {
        'rejected_events': rejected_events
    }
    return render(request, 'events/hod_rejected_events.html', context)

@login_required
def principal_pending_events(request):
    if request.user.role != 'PRINCIPAL':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    pending_events = Event.objects.filter(
        status='HOD_APPROVED'
    ).order_by('-created_at')
    
    context = {
        'pending_events': pending_events
    }
    return render(request, 'events/principal_pending_events.html', context)

@login_required
def principal_approved_events(request):
    if request.user.role != 'PRINCIPAL':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    approved_events = Event.objects.filter(
        status='PRINCIPAL_APPROVED'
    ).order_by('-created_at')
    
    context = {
        'approved_events': approved_events
    }
    return render(request, 'events/principal_approved_events.html', context)

@login_required
def principal_rejected_events(request):
    if request.user.role != 'PRINCIPAL':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    rejected_events = Event.objects.filter(
        status='PRINCIPAL_REJECTED'
    ).order_by('-created_at')
    
    context = {
        'rejected_events': rejected_events
    }
    return render(request, 'events/principal_rejected_events.html', context)


@login_required
def assessment_detail(request, assessment_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    assessment = get_object_or_404(EventAssessment, id=assessment_id)
    
    # Check if the user is the coordinator of the event
    if assessment.event.coordinator != request.user:
        messages.error(request, 'You can only view assessments for your events.')
        return redirect('assessment_list')
    
    return render(request, 'events/assessment_detail.html', {'assessment': assessment})

@login_required
def assessment_submissions(request, assessment_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    assessment = get_object_or_404(EventAssessment, id=assessment_id)
    
    # Check if the user is the coordinator of the event
    if assessment.event.coordinator != request.user:
        messages.error(request, 'You can only view submissions for your assessments.')
        return redirect('assessment_list')
    
    submissions = assessment.submissions.all().order_by('-submitted_at')
    return render(request, 'events/assessment_submissions.html', {
        'assessment': assessment,
        'submissions': submissions
    })

@login_required
def edit_assessment(request, assessment_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    assessment = get_object_or_404(EventAssessment, id=assessment_id)
    
    # Check if the user is the coordinator of the event
    if assessment.event.coordinator != request.user:
        messages.error(request, 'You can only edit assessments for your events.')
        return redirect('assessment_list')
    
    # Get all approved events for this coordinator
    events = Event.objects.filter(coordinator=request.user, status='PRINCIPAL_APPROVED')
    
    if request.method == 'POST':
        try:
            assessment.title = request.POST['title']
            assessment.description = request.POST['description']
            assessment.due_date = request.POST['due_date']
            assessment.total_marks = request.POST['total_marks']
            assessment.save()
            messages.success(request, 'Assessment updated successfully!')
            return redirect('assessment_list')
        except Exception as e:
            messages.error(request, f'Error updating assessment: {str(e)}')
    
    return render(request, 'events/edit_assessment.html', {'assessment': assessment, 'events': events})

@login_required
def delete_assessment(request, assessment_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    assessment = get_object_or_404(EventAssessment, id=assessment_id)
    
    # Check if the user is the coordinator of the event
    if assessment.event.coordinator != request.user:
        messages.error(request, 'You can only delete assessments for your events.')
        return redirect('assessment_list')
    
    if request.method == 'POST':
        try:
            assessment.delete()
            messages.success(request, 'Assessment deleted successfully!')
            return redirect('assessment_list')
        except Exception as e:
            messages.error(request, f'Error deleting assessment: {str(e)}')
    
    return render(request, 'events/delete_assessment.html', {'assessment': assessment})

@login_required
def submit_feedback(request, event_id):
    if request.user.role != 'STUDENT':
        messages.error(request, 'Only students can submit feedback.')
        return redirect('dashboard')
    
    event = get_object_or_404(Event, id=event_id)
    
    # Check if student is registered for this event
    registration = get_object_or_404(EventRegistration, event=event, student=request.user)
    
    # Check if certificate is generated
    if not registration.certificate_generated:
        messages.error(request, 'You can only provide feedback after receiving a certificate.')
        return redirect('certificates')
    
    # Check if feedback already exists
    feedback_exists = EventFeedback.objects.filter(event=event, student=request.user).exists()
    if feedback_exists:
        messages.info(request, 'You have already submitted feedback for this event.')
        return redirect('certificates')
    
    if request.method == 'POST':
        try:
            rating = int(request.POST.get('rating'))
            feedback_text = request.POST.get('feedback_text')
            
            if not rating or not feedback_text:
                messages.error(request, 'Please provide both rating and feedback.')
                return render(request, 'events/submit_feedback.html', {'event': event})
            
            # Create feedback
            EventFeedback.objects.create(
                event=event,
                student=request.user,
                rating=rating,
                feedback_text=feedback_text
            )
            
            messages.success(request, 'Thank you for your feedback!')
            return redirect('certificates')
        except Exception as e:
            messages.error(request, f'Error submitting feedback: {str(e)}')
    
    return render(request, 'events/submit_feedback.html', {'event': event})

@login_required
def event_feedback_report(request, event_id):
    if request.user.role not in ['EVENT_COORDINATOR', 'HOD']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    event = get_object_or_404(Event, id=event_id)
    
    # Check if user has permission to view this event's feedback
    if request.user.role == 'EVENT_COORDINATOR' and event.coordinator != request.user:
        messages.error(request, 'You can only view feedback for your events.')
        return redirect('my_events')
    
    if request.user.role == 'HOD' and event.department != request.user.department:
        messages.error(request, 'You can only view feedback for events in your department.')
        return redirect('dashboard')
    
    # Get all feedback for this event
    feedbacks = EventFeedback.objects.filter(event=event).order_by('-submitted_date')
    feedback_count = feedbacks.count()
    
    # Calculate average rating
    avg_rating = feedbacks.aggregate(Avg('rating'))['rating__avg'] or 0
    
    # Calculate feedback rate (percentage of participants who gave feedback)
    total_participants = EventRegistration.objects.filter(event=event).count()
    feedback_rate = (feedback_count / total_participants * 100) if total_participants > 0 else 0
    
    # Get rating distribution
    rating_5_count = feedbacks.filter(rating=5).count()
    rating_4_count = feedbacks.filter(rating=4).count()
    rating_3_count = feedbacks.filter(rating=3).count()
    rating_2_count = feedbacks.filter(rating=2).count()
    rating_1_count = feedbacks.filter(rating=1).count()
    
    # Calculate percentages for progress bars
    rating_5_percent = (rating_5_count / feedback_count * 100) if feedback_count > 0 else 0
    rating_4_percent = (rating_4_count / feedback_count * 100) if feedback_count > 0 else 0
    rating_3_percent = (rating_3_count / feedback_count * 100) if feedback_count > 0 else 0
    rating_2_percent = (rating_2_count / feedback_count * 100) if feedback_count > 0 else 0
    rating_1_percent = (rating_1_count / feedback_count * 100) if feedback_count > 0 else 0
    
    context = {
        'event': event,
        'feedbacks': feedbacks,
        'feedback_count': feedback_count,
        'avg_rating': avg_rating,
        'feedback_rate': feedback_rate,
        'rating_5_count': rating_5_count,
        'rating_4_count': rating_4_count,
        'rating_3_count': rating_3_count,
        'rating_2_count': rating_2_count,
        'rating_1_count': rating_1_count,
        'rating_5_percent': rating_5_percent,
        'rating_4_percent': rating_4_percent,
        'rating_3_percent': rating_3_percent,
        'rating_2_percent': rating_2_percent,
        'rating_1_percent': rating_1_percent
    }
    
    return render(request, 'events/feedback_report.html', context)

@login_required
def available_events(request):
    if not request.user.role == 'STUDENT':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    # Get all principal approved events
    events = Event.objects.filter(
        status='PRINCIPAL_APPROVED',
        date__gte=timezone.now().date()  # Only show upcoming events
    ).order_by('date', 'time')

    # Get the events that the student is already registered for
    registered_events = Event.objects.filter(registrations__student=request.user)

    return render(request, 'events/available_events.html', {
        'events': events,
        'registered_events': registered_events
    })

@login_required
def certificates(request):
    if request.user.role == 'EVENT_COORDINATOR':
        # For coordinators - show certificates for their events
        events = Event.objects.filter(
            coordinator=request.user,
            status='PRINCIPAL_APPROVED'
        ).order_by('-date')
        return render(request, 'events/certificates.html', {'events': events})
    elif request.user.role == 'STUDENT':
        # For students - show events they've participated in that have certificates
        events = Event.objects.filter(
            registrations__student=request.user,
            status='PRINCIPAL_APPROVED'
        ).order_by('-date')
        return render(request, 'events/certificates.html', {'events': events})
    
    # Default case for other roles
    messages.error(request, 'Access denied.')
    return redirect('dashboard')


@login_required
def analytics(request):
    if request.user.role not in ['HOD', 'PRINCIPAL']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    # Filter events based on user role
    if request.user.role == 'HOD':
        events = Event.objects.filter(department=request.user.department)
    else:  # PRINCIPAL
        events = Event.objects.all()

    # Calculate analytics data
    total_events = events.count()
    approved_events = events.filter(status='PRINCIPAL_APPROVED').count()
    pending_events = events.filter(status='PENDING').count()
    total_budget = events.aggregate(Sum('budget'))['budget__sum'] or 0

    # Event statistics by department
    dept_stats = events.values('department__name').annotate(
        event_count=Count('id'),
        avg_attendees=Avg('expected_attendees'),
        total_dept_budget=Sum('budget')
    )

    # Assessment statistics
    assessments = EventAssessment.objects.filter(event__in=events)
    total_assessments = assessments.count()
    submissions = AssessmentSubmission.objects.filter(assessment__in=assessments)
    submission_rate = (submissions.count() / total_assessments) * 100 if total_assessments > 0 else 0
    avg_score = submissions.aggregate(Avg('score'))['score__avg'] or 0

    context = {
        'total_events': total_events,
        'approved_events': approved_events,
        'pending_events': pending_events,
        'total_budget': total_budget,
        'dept_stats': dept_stats,
        'total_assessments': total_assessments,
        'submission_rate': round(submission_rate, 2),
        'avg_score': round(avg_score, 2),
    }

    return render(request, 'events/analytics.html', context)


@login_required
def event_scheduler(request):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Only event coordinators can schedule events.')
        return redirect('dashboard')

    # Get all approved events for this coordinator
    events = Event.objects.filter(
        coordinator=request.user,
        status='PRINCIPAL_APPROVED'
    ).order_by('-date')
    
    # Get existing schedules
    event_schedules = EventSchedule.objects.filter(event__coordinator=request.user).order_by('event__event_name', 'start_time')
    
    if request.method == 'POST':
        try:
            event_id = request.POST.get('event')
            event = get_object_or_404(Event, id=event_id, coordinator=request.user)
            
            # Get all session data from form
            session_names = request.POST.getlist('session_name[]')
            start_times = request.POST.getlist('start_time[]')
            end_times = request.POST.getlist('end_time[]')
            
            # Create schedule entries
            for i in range(len(session_names)):
                EventSchedule.objects.create(
                    event=event,
                    session_name=session_names[i],
                    start_time=start_times[i],
                    end_time=end_times[i]
                )
            
            messages.success(request, 'Event schedule created successfully!')
            return redirect('event_scheduler')
        except Exception as e:
            messages.error(request, f'Error creating schedule: {str(e)}')
    
    return render(request, 'events/event_scheduler.html', {
        'events': events,
        'event_schedules': event_schedules
    })

@login_required
@require_http_methods(['POST'])
def delete_schedule(request, schedule_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        return JsonResponse({'success': False, 'message': 'Access denied.'})
    
    schedule = get_object_or_404(EventSchedule, id=schedule_id)
    
    # Check if the user is the coordinator of the event
    if schedule.event.coordinator != request.user:
        return JsonResponse({'success': False, 'message': 'You can only delete schedules for your events.'})
    
    try:
        schedule.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


    return redirect('event_approval_list')


@login_required
def event_participants(request, event_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        return JsonResponse({'success': False, 'message': 'Access denied.'})
    
    event = get_object_or_404(Event, id=event_id, coordinator=request.user)
    registrations = event.registrations.all()
    
    participants = []
    for registration in registrations:
        participants.append({
            'student_id': registration.student.username,
            'name': registration.student.get_full_name(),
            'email': registration.student.email,
            'certificate_generated': registration.certificate_generated
        })
    
    return JsonResponse({
        'success': True,
        'participants': participants
    })

@login_required
@require_http_methods(['POST'])
def generate_certificates(request, event_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        return JsonResponse({'success': False, 'message': 'Access denied.'})
    
    event = get_object_or_404(Event, id=event_id, coordinator=request.user)
    registrations = event.registrations.all()
    
    if not registrations:
        return JsonResponse({'success': False, 'message': 'No participants found for this event.'})
    
    try:
        from .utils import generate_certificate
        
        for registration in registrations:
            if not registration.certificate_generated:
                certificate_url, verification_id = generate_certificate(event, registration.student)
                registration.certificate_url = certificate_url
                registration.certificate_generated = True
                registration.save()
        
        return JsonResponse({'success': True, 'message': f'Generated certificates for {registrations.count()} participants.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
def hod_pending_events(request):
    if request.user.role != 'HOD':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    pending_events = Event.objects.filter(
        department=request.user.department,
        status='PENDING'
    ).order_by('-created_at')
    
    context = {
        'pending_events': pending_events
    }
    return render(request, 'events/hod_pending_events.html', context)

@login_required
def hod_approved_events(request):
    if request.user.role != 'HOD':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    approved_events = Event.objects.filter(
        department=request.user.department,
        status='HOD_APPROVED'
    ).order_by('-created_at')
    
    context = {
        'approved_events': approved_events
    }
    return render(request, 'events/hod_approved_events.html', context)

@login_required
def hod_rejected_events(request):
    if request.user.role != 'HOD':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    rejected_events = Event.objects.filter(
        department=request.user.department,
        status='HOD_REJECTED'
    ).order_by('-created_at')
    
    context = {
        'rejected_events': rejected_events
    }
    return render(request, 'events/hod_rejected_events.html', context)

@login_required
def principal_pending_events(request):
    if request.user.role != 'PRINCIPAL':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    pending_events = Event.objects.filter(
        status='HOD_APPROVED'
    ).order_by('-created_at')
    
    context = {
        'pending_events': pending_events
    }
    return render(request, 'events/principal_pending_events.html', context)

@login_required
def principal_approved_events(request):
    if request.user.role != 'PRINCIPAL':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    approved_events = Event.objects.filter(
        status='PRINCIPAL_APPROVED'
    ).order_by('-created_at')
    
    context = {
        'approved_events': approved_events
    }
    return render(request, 'events/principal_approved_events.html', context)

@login_required
def principal_rejected_events(request):
    if request.user.role != 'PRINCIPAL':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    rejected_events = Event.objects.filter(
        status='PRINCIPAL_REJECTED'
    ).order_by('-created_at')
    
    context = {
        'rejected_events': rejected_events
    }
    return render(request, 'events/principal_rejected_events.html', context)


@login_required
def assessment_detail(request, assessment_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    assessment = get_object_or_404(EventAssessment, id=assessment_id)
    
    # Check if the user is the coordinator of the event
    if assessment.event.coordinator != request.user:
        messages.error(request, 'You can only view assessments for your events.')
        return redirect('assessment_list')
    
    return render(request, 'events/assessment_detail.html', {'assessment': assessment})

@login_required
def assessment_submissions(request, assessment_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    assessment = get_object_or_404(EventAssessment, id=assessment_id)
    
    # Check if the user is the coordinator of the event
    if assessment.event.coordinator != request.user:
        messages.error(request, 'You can only view submissions for your assessments.')
        return redirect('assessment_list')
    
    submissions = assessment.submissions.all().order_by('-submitted_at')
    return render(request, 'events/assessment_submissions.html', {
        'assessment': assessment,
        'submissions': submissions
    })

@login_required
def edit_assessment(request, assessment_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    assessment = get_object_or_404(EventAssessment, id=assessment_id)
    
    # Check if the user is the coordinator of the event
    if assessment.event.coordinator != request.user:
        messages.error(request, 'You can only edit assessments for your events.')
        return redirect('assessment_list')
    
    # Get all approved events for this coordinator
    events = Event.objects.filter(coordinator=request.user, status='PRINCIPAL_APPROVED')
    
    if request.method == 'POST':
        try:
            assessment.title = request.POST['title']
            assessment.description = request.POST['description']
            assessment.due_date = request.POST['due_date']
            assessment.total_marks = request.POST['total_marks']
            assessment.save()
            messages.success(request, 'Assessment updated successfully!')
            return redirect('assessment_list')
        except Exception as e:
            messages.error(request, f'Error updating assessment: {str(e)}')
    
    return render(request, 'events/edit_assessment.html', {'assessment': assessment, 'events': events})

@login_required
def delete_assessment(request, assessment_id):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    assessment = get_object_or_404(EventAssessment, id=assessment_id)
    
    # Check if the user is the coordinator of the event
    if assessment.event.coordinator != request.user:
        messages.error(request, 'You can only delete assessments for your events.')
        return redirect('assessment_list')
    
    if request.method == 'POST':
        try:
            assessment.delete()
            messages.success(request, 'Assessment deleted successfully!')
            return redirect('assessment_list')
        except Exception as e:
            messages.error(request, f'Error deleting assessment: {str(e)}')
    
    return render(request, 'events/delete_assessment.html', {'assessment': assessment})

@login_required
def submit_feedback(request, event_id):
    if request.user.role != 'STUDENT':
        messages.error(request, 'Only students can submit feedback.')
        return redirect('dashboard')
    
    event = get_object_or_404(Event, id=event_id)
    
    # Check if student is registered for this event
    registration = get_object_or_404(EventRegistration, event=event, student=request.user)
    
    # Check if certificate is generated
    if not registration.certificate_generated:
        messages.error(request, 'You can only provide feedback after receiving a certificate.')
        return redirect('certificates')
    
    # Check if feedback already exists
    feedback_exists = EventFeedback.objects.filter(event=event, student=request.user).exists()
    if feedback_exists:
        messages.info(request, 'You have already submitted feedback for this event.')
        return redirect('certificates')
    
    if request.method == 'POST':
        try:
            rating = int(request.POST.get('rating'))
            feedback_text = request.POST.get('feedback_text')
            
            if not rating or not feedback_text:
                messages.error(request, 'Please provide both rating and feedback.')
                return render(request, 'events/submit_feedback.html', {'event': event})
            
            # Create feedback
            EventFeedback.objects.create(
                event=event,
                student=request.user,
                rating=rating,
                feedback_text=feedback_text
            )
            
            messages.success(request, 'Thank you for your feedback!')
            return redirect('certificates')
        except Exception as e:
            messages.error(request, f'Error submitting feedback: {str(e)}')
    
    return render(request, 'events/submit_feedback.html', {'event': event})

@login_required
def event_feedback_report(request, event_id):
    if request.user.role not in ['EVENT_COORDINATOR', 'HOD']:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    event = get_object_or_404(Event, id=event_id)
    
    # Check if user has permission to view this event's feedback
    if request.user.role == 'EVENT_COORDINATOR' and event.coordinator != request.user:
        messages.error(request, 'You can only view feedback for your events.')
        return redirect('my_events')
    
    if request.user.role == 'HOD' and event.department != request.user.department:
        messages.error(request, 'You can only view feedback for events in your department.')
        return redirect('dashboard')
    
    # Get all feedback for this event
    feedbacks = EventFeedback.objects.filter(event=event).order_by('-submitted_date')
    feedback_count = feedbacks.count()
    
    # Calculate average rating
    avg_rating = feedbacks.aggregate(Avg('rating'))['rating__avg'] or 0
    
    # Calculate feedback rate (percentage of participants who gave feedback)
    total_participants = EventRegistration.objects.filter(event=event).count()
    feedback_rate = (feedback_count / total_participants * 100) if total_participants > 0 else 0
    
    # Get rating distribution
    rating_5_count = feedbacks.filter(rating=5).count()
    rating_4_count = feedbacks.filter(rating=4).count()
    rating_3_count = feedbacks.filter(rating=3).count()
    rating_2_count = feedbacks.filter(rating=2).count()
    rating_1_count = feedbacks.filter(rating=1).count()
    
    # Calculate percentages for progress bars
    rating_5_percent = (rating_5_count / feedback_count * 100) if feedback_count > 0 else 0
    rating_4_percent = (rating_4_count / feedback_count * 100) if feedback_count > 0 else 0
    rating_3_percent = (rating_3_count / feedback_count * 100) if feedback_count > 0 else 0
    rating_2_percent = (rating_2_count / feedback_count * 100) if feedback_count > 0 else 0
    rating_1_percent = (rating_1_count / feedback_count * 100) if feedback_count > 0 else 0
    
    context = {
        'event': event,
        'feedbacks': feedbacks,
        'feedback_count': feedback_count,
        'avg_rating': avg_rating,
        'feedback_rate': feedback_rate,
        'rating_5_count': rating_5_count,
        'rating_4_count': rating_4_count,
        'rating_3_count': rating_3_count,
        'rating_2_count': rating_2_count,
        'rating_1_count': rating_1_count,
        'rating_5_percent': rating_5_percent,
        'rating_4_percent': rating_4_percent,
        'rating_3_percent': rating_3_percent,
        'rating_2_percent': rating_2_percent,
        'rating_1_percent': rating_1_percent
    }
    
    return render(request, 'events/feedback_report.html', context)

@login_required
def available_events(request):
    if not request.user.role == 'STUDENT':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    # Get all principal approved events
    events = Event.objects.filter(
        status='PRINCIPAL_APPROVED',
        date__gte=timezone.now().date()  # Only show upcoming events
    ).order_by('date', 'time')

    # Get the events that the student is already registered for
    registered_events = Event.objects.filter(registrations__student=request.user)

    return render(request, 'events/available_events.html', {
        'events': events,
        'registered_events': registered_events
    })

@login_required
def upload_material(request):
    if not request.user.role == 'EVENT_COORDINATOR':
        messages.error(request, 'Only event coordinators can upload study materials.')
        return redirect('dashboard')
    
    # Get all approved events for this coordinator
    events = Event.objects.filter(
        coordinator=request.user,
        status='PRINCIPAL_APPROVED'
    ).order_by('-date')
    
    if request.method == 'POST':
        try:
            event_id = request.POST.get('event')
            title = request.POST.get('title')
            description = request.POST.get('description')
            material_file = request.FILES.get('material_file')
            
            if not all([event_id, title, material_file]):
                messages.error(request, 'Please fill all required fields.')
                return render(request, 'events/upload_material.html', {'events': events})
            
            event = get_object_or_404(Event, id=event_id, coordinator=request.user)
            
            # Create material
            EventMaterial.objects.create(
                event=event,
                title=title,
                description=description,
                file=material_file
            )
            
            messages.success(request, 'Study material uploaded successfully!')
            return redirect('upload_material')
        except Exception as e:
            messages.error(request, f'Error uploading material: {str(e)}')
    
    return render(request, 'events/upload_material.html', {'events': events})

@login_required
def view_materials(request):
    if request.user.role == 'STUDENT':
        # For students - show materials for events they're registered for
        registered_events = Event.objects.filter(
            registrations__student=request.user,
            status='PRINCIPAL_APPROVED'
        ).prefetch_related('materials').order_by('-date')
        
        return render(request, 'events/view_materials.html', {
            'registered_events': registered_events
        })
    elif request.user.role == 'EVENT_COORDINATOR':
        # For coordinators - show materials for their events
        events = Event.objects.filter(
            coordinator=request.user,
            status='PRINCIPAL_APPROVED'
        ).prefetch_related('materials').order_by('-date')
        
        return render(request, 'events/view_materials.html', {
            'registered_events': events
        })
    else:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

# This duplicate certificates function has been removed to fix the ValueError issue
