from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta
from .models import Event, EventRegistration, EventAssessment, AssessmentSubmission, EventFeedback

@login_required
def get_coordinator_dashboard_data(request):
    """API endpoint to get real-time data for coordinator dashboard"""
    if request.user.role != 'EVENT_COORDINATOR':
        return JsonResponse({'success': False, 'message': 'Access denied'})
    
    # Get events created by this coordinator
    events = Event.objects.filter(coordinator=request.user)
    
    # Calculate dashboard metrics
    my_events_count = events.count()
    approved_events_count = events.filter(status='PRINCIPAL_APPROVED').count()
    pending_events_count = events.filter(status__in=['PENDING', 'HOD_APPROVED']).count()
    
    # Get event participation data
    event_participation = {}
    for event in events.filter(status='PRINCIPAL_APPROVED')[:5]:  # Get top 5 events
        event_participation[event.event_name] = EventRegistration.objects.filter(event=event).count()
    
    # Get assessment completion data
    assessment_completion = {}
    for event in events.filter(status='PRINCIPAL_APPROVED')[:5]:  # Get top 5 events
        assessments = EventAssessment.objects.filter(event=event)
        if assessments.exists():
            total_possible_submissions = assessments.count() * EventRegistration.objects.filter(event=event).count()
            if total_possible_submissions > 0:
                actual_submissions = AssessmentSubmission.objects.filter(assessment__event=event).count()
                completion_rate = (actual_submissions / total_possible_submissions) * 100
                assessment_completion[event.event_name] = round(completion_rate, 1)
    
    # Get event timeline data (events per month)
    current_year = timezone.now().year
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    event_timeline = []
    
    for i, month in enumerate(months, 1):
        count = events.filter(
            date__year=current_year,
            date__month=i
        ).count()
        event_timeline.append({'month': month, 'count': count})
    
    # Get event feedback data
    feedback_data = {
        'Excellent': 0,
        'Good': 0,
        'Average': 0,
        'Poor': 0
    }
    
    for event in events:
        excellent = EventFeedback.objects.filter(event=event, rating__gte=4).count()
        good = EventFeedback.objects.filter(event=event, rating=3).count()
        average = EventFeedback.objects.filter(event=event, rating=2).count()
        poor = EventFeedback.objects.filter(event=event, rating=1).count()
        
        feedback_data['Excellent'] += excellent
        feedback_data['Good'] += good
        feedback_data['Average'] += average
        feedback_data['Poor'] += poor
    
    return JsonResponse({
        'success': True,
        'myEvents': my_events_count,
        'approvedEvents': approved_events_count,
        'pendingEvents': pending_events_count,
        'eventParticipation': event_participation,
        'assessmentCompletion': assessment_completion,
        'eventTimeline': event_timeline,
        'eventFeedback': feedback_data
    })

@login_required
def get_hod_dashboard_data(request):
    """API endpoint to get real-time data for HOD dashboard"""
    if request.user.role != 'HOD':
        return JsonResponse({'success': False, 'message': 'Access denied'})
    
    # Get events from this department
    events = Event.objects.filter(department=request.user.department)
    
    # Calculate dashboard metrics
    department_events_count = events.count()
    pending_approvals_count = events.filter(status='PENDING').count()
    
    # Get student participation count
    student_participation_count = EventRegistration.objects.filter(
        event__in=events
    ).values('student').distinct().count()
    
    # Get event status distribution
    event_status = {
        'Pending': events.filter(status='PENDING').count(),
        'HOD Approved': events.filter(status='HOD_APPROVED').count(),
        'Principal Approved': events.filter(status='PRINCIPAL_APPROVED').count()
    }
    
    # Get monthly events data
    current_year = timezone.now().year
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    monthly_events = []
    
    for i, month in enumerate(months, 1):
        count = events.filter(
            date__year=current_year,
            date__month=i
        ).count()
        monthly_events.append({'month': month, 'count': count})
    
    # Get assessment performance data
    assessment_performance = {}
    for event in events.filter(status='PRINCIPAL_APPROVED')[:5]:  # Get top 5 events
        submissions = AssessmentSubmission.objects.filter(assessment__event=event)
        if submissions.exists():
            avg_score = submissions.aggregate(Avg('score'))['score__avg'] or 0
            assessment_performance[event.event_name] = round(avg_score, 1)
    
    # Get event mode distribution
    event_modes = {
        'Online': events.filter(mode='ONLINE').count(),
        'Offline': events.filter(mode='OFFLINE').count()
    }
    
    return JsonResponse({
        'success': True,
        'departmentEvents': department_events_count,
        'pendingApprovals': pending_approvals_count,
        'studentParticipation': student_participation_count,
        'eventStatus': event_status,
        'monthlyEvents': monthly_events,
        'assessmentPerformance': assessment_performance,
        'eventModes': event_modes
    })

@login_required
def get_principal_dashboard_data(request):
    """API endpoint to get real-time data for Principal dashboard"""
    if request.user.role != 'PRINCIPAL':
        return JsonResponse({'success': False, 'message': 'Access denied'})
    
    # Get all events
    events = Event.objects.all()
    
    # Calculate dashboard metrics
    total_events_count = events.count()
    pending_approvals_count = events.filter(status='HOD_APPROVED').count()
    approved_events_count = events.filter(status='PRINCIPAL_APPROVED').count()
    
    # Get department-wise event counts
    dept_event_counts = events.values('department').annotate(count=Count('id'))
    department_events = {}
    for dept in dept_event_counts:
        department_events[dict(Event.coordinator.field.related_model.DEPARTMENT_CHOICES)[dept['department']]] = dept['count']
    
    # Get budget allocation by department
    dept_budget_allocation = events.filter(status='PRINCIPAL_APPROVED').values('department').annotate(total=Sum('budget'))
    budget_by_department = {}
    for dept in dept_budget_allocation:
        budget_by_department[dict(Event.coordinator.field.related_model.DEPARTMENT_CHOICES)[dept['department']]] = float(dept['total'] or 0)
    
    # Get monthly event counts
    current_year = timezone.now().year
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    monthly_events = []
    
    for i, month in enumerate(months, 1):
        count = events.filter(
            date__year=current_year,
            date__month=i
        ).count()
        monthly_events.append({'month': month, 'count': count})
    
    # Get event mode distribution
    event_modes = {
        'Online': events.filter(mode='ONLINE').count(),
        'Offline': events.filter(mode='OFFLINE').count()
    }
    
    # Get recent events (last 30 days)
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    recent_events = events.filter(date__gte=thirty_days_ago).order_by('-date')[:5]
    recent_events_data = []
    
    for event in recent_events:
        recent_events_data.append({
            'name': event.event_name,
            'department': dict(Event.coordinator.field.related_model.DEPARTMENT_CHOICES)[event.department],
            'date': event.date.strftime('%d %b %Y'),
            'status': dict(Event.STATUS_CHOICES)[event.status]
        })
    
    return JsonResponse({
        'success': True,
        'totalEvents': total_events_count,
        'pendingApprovals': pending_approvals_count,
        'approvedEvents': approved_events_count,
        'departmentEvents': department_events,
        'budgetByDepartment': budget_by_department,
        'monthlyEvents': monthly_events,
        'eventModes': event_modes,
        'recentEvents': recent_events_data
    })

@login_required
def get_student_dashboard_data(request):
    """API endpoint to get real-time data for Student dashboard"""
    if request.user.role != 'STUDENT':
        return JsonResponse({'success': False, 'message': 'Access denied'})
    
    # Get events the student is registered for
    registered_events = EventRegistration.objects.filter(student=request.user)
    registered_events_count = registered_events.count()
    
    # Get upcoming events the student is registered for
    upcoming_events = registered_events.filter(
        event__date__gte=timezone.now().date()
    ).order_by('event__date')[:5]
    
    upcoming_events_data = []
    for reg in upcoming_events:
        upcoming_events_data.append({
            'name': reg.event.event_name,
            'date': reg.event.date.strftime('%d %b %Y'),
            'time': reg.event.time.strftime('%I:%M %p'),
            'mode': dict(Event.MODE_CHOICES)[reg.event.mode],
            'venue': reg.event.venue if reg.event.venue else 'Online'
        })
    
    # Get pending assessments
    pending_assessments = []
    for reg in registered_events:
        assessments = EventAssessment.objects.filter(
            event=reg.event,
            due_date__gte=timezone.now()
        )
        for assessment in assessments:
            # Check if student has already submitted
            submission_exists = AssessmentSubmission.objects.filter(
                assessment=assessment,
                student=request.user
            ).exists()
            
            if not submission_exists:
                pending_assessments.append({
                    'title': assessment.title,
                    'event': assessment.event.event_name,
                    'due_date': assessment.due_date.strftime('%d %b %Y, %I:%M %p'),
                    'id': assessment.id
                })
    
    # Get certificates
    certificates = registered_events.filter(certificate_generated=True).count()
    
    # Get assessment performance
    submissions = AssessmentSubmission.objects.filter(student=request.user)
    avg_score = submissions.aggregate(Avg('score'))['score__avg'] or 0
    
    # Get event participation by month
    current_year = timezone.now().year
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    monthly_participation = []
    
    for i, month in enumerate(months, 1):
        count = registered_events.filter(
            event__date__year=current_year,
            event__date__month=i
        ).count()
        monthly_participation.append({'month': month, 'count': count})
    
    # Get feedback given by student
    feedback_given = EventFeedback.objects.filter(student=request.user).count()
    
    return JsonResponse({
        'success': True,
        'registeredEvents': registered_events_count,
        'upcomingEvents': upcoming_events_data,
        'pendingAssessments': pending_assessments,
        'certificates': certificates,
        'avgScore': round(avg_score, 1),
        'monthlyParticipation': monthly_participation,
        'feedbackGiven': feedback_given
    })