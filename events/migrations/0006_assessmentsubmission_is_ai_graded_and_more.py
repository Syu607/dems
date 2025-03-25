# Generated by Django 5.0.1 on 2025-03-15 21:18

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0005_eventregistration_certificate_generated_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='assessmentsubmission',
            name='is_ai_graded',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='eventassessment',
            name='is_ai_generated',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='eventassessment',
            name='passing_score',
            field=models.PositiveIntegerField(default=3),
        ),
        migrations.AlterField(
            model_name='assessmentsubmission',
            name='submission_file',
            field=models.FileField(blank=True, null=True, upload_to='events/assessment_submissions/'),
        ),
        migrations.CreateModel(
            name='Question',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question_text', models.TextField()),
                ('question_type', models.CharField(choices=[('MCQ', 'Multiple Choice Question'), ('MSQ', 'Multiple Select Question'), ('NAT', 'Numerical Answer Type')], max_length=3)),
                ('marks', models.PositiveIntegerField(default=1)),
                ('assessment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questions', to='events.eventassessment')),
            ],
        ),
        migrations.CreateModel(
            name='NumericalAnswer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('correct_answer', models.FloatField()),
                ('tolerance', models.FloatField(default=0.0)),
                ('question', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='numerical_answer', to='events.question')),
            ],
        ),
        migrations.CreateModel(
            name='QuestionOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('option_text', models.CharField(max_length=255)),
                ('is_correct', models.BooleanField(default=False)),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='options', to='events.question')),
            ],
        ),
        migrations.CreateModel(
            name='StudentAnswer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numerical_value', models.FloatField(blank=True, null=True)),
                ('is_correct', models.BooleanField(default=False)),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='events.question')),
                ('selected_options', models.ManyToManyField(blank=True, to='events.questionoption')),
                ('submission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='answers', to='events.assessmentsubmission')),
            ],
            options={
                'unique_together': {('submission', 'question')},
            },
        ),
    ]
