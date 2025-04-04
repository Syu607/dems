# Generated by Django 5.0.1 on 2025-03-12 20:44

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('events', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='assessmentsubmission',
            name='student',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assessment_submissions', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='event',
            name='coordinator',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='coordinated_events', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='eventassessment',
            name='event',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assessments', to='events.event'),
        ),
        migrations.AddField(
            model_name='assessmentsubmission',
            name='assessment',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='submissions', to='events.eventassessment'),
        ),
        migrations.AddField(
            model_name='eventfeedback',
            name='event',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='feedbacks', to='events.event'),
        ),
        migrations.AddField(
            model_name='eventfeedback',
            name='student',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='given_feedbacks', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='eventmaterial',
            name='event',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='materials', to='events.event'),
        ),
        migrations.AddField(
            model_name='eventregistration',
            name='event',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='registrations', to='events.event'),
        ),
        migrations.AddField(
            model_name='eventregistration',
            name='student',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='event_registrations', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='eventschedule',
            name='event',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='schedules', to='events.event'),
        ),
        migrations.AlterUniqueTogether(
            name='assessmentsubmission',
            unique_together={('assessment', 'student')},
        ),
        migrations.AlterUniqueTogether(
            name='eventfeedback',
            unique_together={('event', 'student')},
        ),
        migrations.AlterUniqueTogether(
            name='eventregistration',
            unique_together={('event', 'student')},
        ),
    ]
