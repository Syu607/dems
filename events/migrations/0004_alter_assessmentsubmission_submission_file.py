# Generated by Django 5.0.1 on 2025-03-14 20:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0003_eventassessment_total_marks'),
    ]

    operations = [
        migrations.AlterField(
            model_name='assessmentsubmission',
            name='submission_file',
            field=models.FileField(blank=True, null=True, upload_to='assessment_submissions/'),
        ),
    ]
