from django.db import models
from django.core.validators import MinValueValidator
from users.models import CustomUser

class Event(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('HOD_APPROVED', 'HOD Approved'),
        ('HOD_REJECTED', 'HOD Rejected'),
        ('PRINCIPAL_APPROVED', 'Principal Approved'),
        ('PRINCIPAL_REJECTED', 'Principal Rejected'),
    ]

    MODE_CHOICES = [
        ('ONLINE', 'Online'),
        ('OFFLINE', 'Offline'),
    ]

    # Basic Event Information
    name = models.CharField(max_length=200)
    coordinator = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='coordinated_events')
    department = models.CharField(max_length=10, choices=CustomUser.DEPARTMENT_CHOICES)
    event_name = models.CharField(max_length=200)
    about = models.TextField()
    title = models.CharField(max_length=200)
    date = models.DateField()
    time = models.TimeField()
    expected_attendees = models.PositiveIntegerField()
    mode = models.CharField(max_length=10, choices=MODE_CHOICES)
    venue = models.CharField(max_length=200, blank=True, null=True)

    # Budget Information
    budget = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    registration_fee = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    refreshment = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    renumeration = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    honorarium = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    other_requirements = models.TextField(blank=True)

    # Approval Information
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    hod_approval_date = models.DateTimeField(null=True, blank=True)
    principal_approval_date = models.DateTimeField(null=True, blank=True)
    event_id = models.CharField(max_length=50, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_name} - {self.department}"

class EventSchedule(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='schedules')
    session_name = models.CharField(max_length=200)
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"{self.event.event_name} - {self.session_name}"

class EventRegistration(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='registrations')
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='event_registrations')
    registration_date = models.DateTimeField(auto_now_add=True)
    certificate_generated = models.BooleanField(default=False)
    certificate_generated_date = models.DateTimeField(null=True, blank=True)
    certificate_url = models.URLField(blank=True, null=True)

    class Meta:
        unique_together = ['event', 'student']

    def __str__(self):
        return f"{self.student.username} - {self.event.event_name}"

class EventFeedback(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='feedbacks')
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='given_feedbacks')
    feedback_text = models.TextField()
    rating = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    submitted_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['event', 'student']

    def __str__(self):
        return f"{self.student.username}'s feedback for {self.event.event_name}"

class EventMaterial(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='materials')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='event_materials/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.event.event_name}"

class EventAssessment(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='assessments')
    title = models.CharField(max_length=200)
    description = models.TextField()
    due_date = models.DateTimeField()
    total_marks = models.PositiveIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    is_ai_generated = models.BooleanField(default=False)
    passing_score = models.PositiveIntegerField(default=3)  # Minimum score needed for certificate

    def __str__(self):
        return f"{self.title} - {self.event.event_name}"

class Question(models.Model):
    QUESTION_TYPE_CHOICES = [
        ('MCQ', 'Multiple Choice Question'),
        ('MSQ', 'Multiple Select Question'),
        ('NAT', 'Numerical Answer Type'),
    ]
    
    assessment = models.ForeignKey(EventAssessment, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    question_type = models.CharField(max_length=3, choices=QUESTION_TYPE_CHOICES)
    marks = models.PositiveIntegerField(default=1)
    
    def __str__(self):
        return f"{self.question_text[:30]}..."

class QuestionOption(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    option_text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    
    def __str__(self):
        return self.option_text

class NumericalAnswer(models.Model):
    question = models.OneToOneField(Question, on_delete=models.CASCADE, related_name='numerical_answer')
    correct_answer = models.FloatField()
    tolerance = models.FloatField(default=0.0)  # For approximate answers
    
    def __str__(self):
        return f"{self.correct_answer} (±{self.tolerance})"

class AssessmentSubmission(models.Model):
    assessment = models.ForeignKey(EventAssessment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='assessment_submissions')
    submission_file = models.FileField(upload_to='events/assessment_submissions/', null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    score = models.PositiveIntegerField(null=True, blank=True)
    is_ai_graded = models.BooleanField(default=False)

    class Meta:
        unique_together = ['assessment', 'student']

    def __str__(self):
        return f"{self.student.username}'s submission for {self.assessment.title}"

class StudentAnswer(models.Model):
    submission = models.ForeignKey(AssessmentSubmission, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_options = models.ManyToManyField(QuestionOption, blank=True)
    numerical_value = models.FloatField(null=True, blank=True)
    is_correct = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['submission', 'question']
    
    def __str__(self):
        return f"Answer for {self.question}"
