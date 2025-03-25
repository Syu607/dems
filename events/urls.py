from django.urls import path
from . import views, dashboard_api

urlpatterns = [
    path('create/', views.create_event, name='create_event'),
    path('my-events/', views.my_events, name='my_events'),
    path('available/', views.available_events, name='available_events'),
    path('register/<str:event_id>/', views.register_event, name='register_event'),
    path('assessments/', views.assessment_list, name='assessment_list'),
    path('student-assessments/', views.student_assessment_list, name='student_assessment_list'),
    path('create-assessment/', views.create_assessment, name='create_assessment'),
    path('submit-assessment/<int:assessment_id>/', views.submit_assessment, name='submit_assessment'),
    path('assessment-result/<int:submission_id>/', views.assessment_result, name='assessment_result'),
    path('grade-assessment/<int:submission_id>/', views.grade_assessment, name='grade_assessment'),
    path('certificates/', views.certificates, name='certificates'),
    path('approvals/', views.event_approval_list, name='event_approval_list'),
    path('analytics/', views.analytics, name='analytics'),
    path('event/<str:event_id>/', views.event_detail, name='event_detail'),
    path('scheduler/', views.event_scheduler, name='event_scheduler'),
    path('delete-schedule/<int:schedule_id>/', views.delete_schedule, name='delete_schedule'),
    
    # New assessment routes
    path('assessment/<int:assessment_id>/', views.assessment_detail, name='assessment_detail'),
    path('assessment/<int:assessment_id>/submissions/', views.assessment_submissions, name='assessment_submissions'),
    path('assessment/<int:assessment_id>/edit/', views.edit_assessment, name='edit_assessment'),
    path('assessment/<int:assessment_id>/delete/', views.delete_assessment, name='delete_assessment'),
    
    # HOD Event Pages
    path('hod/pending-events/', views.hod_pending_events, name='hod_pending_events'),
    path('hod/approved-events/', views.hod_approved_events, name='hod_approved_events'),
    path('hod/rejected-events/', views.hod_rejected_events, name='hod_rejected_events'),
    
    # Principal Event Pages
    path('principal/pending-events/', views.principal_pending_events, name='principal_pending_events'),
    path('principal/approved-events/', views.principal_approved_events, name='principal_approved_events'),
    path('principal/rejected-events/', views.principal_rejected_events, name='principal_rejected_events'),
    
    # API endpoints
    path('api/event/<str:event_id>/', views.event_detail_api, name='event_detail_api'),
    path('api/event/<str:event_id>/approve/', views.approve_event, name='approve_event'),
    path('api/event/<str:event_id>/reject/', views.reject_event, name='reject_event'),
    path('api/event/<str:event_id>/analytics/', views.get_event_analytics, name='event_analytics'),
    path('api/event/<int:event_id>/participants/', views.event_participants, name='event_participants'),
    path('api/event/<int:event_id>/generate-certificates/', views.generate_certificates, name='generate_certificates'),
    
    # Dashboard API endpoints
    path('api/dashboard/coordinator/', dashboard_api.get_coordinator_dashboard_data, name='coordinator_dashboard_api'),
    path('api/dashboard/hod/', dashboard_api.get_hod_dashboard_data, name='hod_dashboard_api'),
    path('api/dashboard/principal/', dashboard_api.get_principal_dashboard_data, name='principal_dashboard_api'),
    path('api/dashboard/student/', dashboard_api.get_student_dashboard_data, name='student_dashboard_api'),
    
    # Feedback
    path('feedback/<int:event_id>/', views.submit_feedback, name='submit_feedback'),
    path('feedback/report/<int:event_id>/', views.event_feedback_report, name='event_feedback_report'),
    
    # Study Materials
    path('upload-material/', views.upload_material, name='upload_material'),
    path('view-materials/', views.view_materials, name='view_materials'),
]