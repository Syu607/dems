# Generated by Django 5.0.1 on 2025-03-14 20:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventassessment',
            name='total_marks',
            field=models.PositiveIntegerField(default=100),
        ),
    ]
