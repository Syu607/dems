from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('PRINCIPAL', 'Principal'),
        ('HOD', 'HOD'),
        ('EVENT_COORDINATOR', 'Event Coordinator'),
        ('STUDENT', 'Student'),
    ]

    DEPARTMENT_CHOICES = [
        ('CSE', 'Computer Science'),
        ('ISE', 'Information Science'),
        ('ECE', 'Electronics'),
        ('MECH', 'Mechanical'),
        ('CIVIL', 'Civil'),
        ('EEE', 'Electrical'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    department = models.CharField(max_length=10, choices=DEPARTMENT_CHOICES, null=True, blank=True)
    phone_regex = RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")
    mobile_number = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    emp_id = models.CharField(max_length=20, unique=True, help_text='Staff ID for Principal/HOD, USN for Student/Event Coordinator')
    is_approved = models.BooleanField(default=False)
    email = models.EmailField(unique=True)

    def __str__(self):
        return f"{self.username} - {self.role}"

    def save(self, *args, **kwargs):
        if self.role == 'PRINCIPAL':
            self.is_staff = True
        if self.role not in ['STUDENT', 'EVENT_COORDINATOR', 'HOD'] and self.department:
            self.department = None
        super().save(*args, **kwargs)
        
    def approve_user(self):
        """Method to approve a user account"""
        self.is_approved = True
        self.save()
        return True

    class Meta:
        permissions = [
            ('can_approve_users', 'Can approve user registrations'),
            ('can_manage_events', 'Can manage events'),
            ('can_view_analytics', 'Can view analytics'),
        ]

# Create your models here.
