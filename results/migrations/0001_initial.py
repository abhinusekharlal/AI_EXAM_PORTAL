# Generated by Django 5.1.6 on 2025-03-19 08:10

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('classroom', '0012_exam_status'),
        ('monitoring', '0004_remove_alert_reviewed_at_remove_alert_reviewed_by_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ExamResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('score', models.FloatField(help_text='Percentage score (0-100)')),
                ('correct_answers', models.PositiveIntegerField(default=0)),
                ('total_questions', models.PositiveIntegerField(default=0)),
                ('start_time', models.DateTimeField()),
                ('completion_time', models.DateTimeField()),
                ('time_taken', models.DurationField(help_text='Total time taken to complete the exam')),
                ('responses', models.JSONField(default=dict, help_text="Student's answers to each question")),
                ('status', models.CharField(choices=[('passed', 'Passed'), ('failed', 'Failed'), ('partial', 'Partial'), ('flagged', 'Flagged'), ('under_review', 'Under Review'), ('penalty_applied', 'Penalty Applied')], default='failed', max_length=15)),
                ('is_flagged', models.BooleanField(default=False, help_text='Whether this exam was flagged for suspicious behavior')),
                ('is_reviewed', models.BooleanField(default=False, help_text='Whether this exam has been reviewed by the teacher')),
                ('penalty_percentage', models.FloatField(default=0, help_text='Percentage points deducted due to violations')),
                ('original_score', models.FloatField(blank=True, help_text='Score before penalties were applied', null=True)),
                ('teacher_notes', models.TextField(blank=True, help_text="Teacher's notes after reviewing the exam")),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('exam', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='results', to='classroom.exam')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exam_results', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Exam Result',
                'verbose_name_plural': 'Exam Results',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ExamViolation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('violation_type', models.CharField(choices=[('cheating', 'Cheating'), ('unauthorized_assistance', 'Unauthorized Assistance'), ('impersonation', 'Impersonation'), ('unauthorized_materials', 'Unauthorized Materials'), ('communication', 'Unauthorized Communication'), ('device_usage', 'Unauthorized Device Usage'), ('technical_violation', 'Technical Rule Violation'), ('other', 'Other Violation')], max_length=30)),
                ('description', models.TextField()),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('severity', models.CharField(choices=[('minor', 'Minor'), ('moderate', 'Moderate'), ('major', 'Major'), ('critical', 'Critical')], default='moderate', max_length=10)),
                ('penalty_applied', models.FloatField(default=0, help_text='Percentage points deducted for this violation')),
                ('evidence_screenshot', models.ImageField(blank=True, null=True, upload_to='violations/evidence/')),
                ('alert', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='confirmed_violations', to='monitoring.alert')),
                ('exam_result', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='violations', to='results.examresult')),
                ('reviewed_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_violations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='examresult',
            index=models.Index(fields=['student', 'exam'], name='results_exa_student_321d0b_idx'),
        ),
        migrations.AddIndex(
            model_name='examresult',
            index=models.Index(fields=['exam', 'status'], name='results_exa_exam_id_f41f8c_idx'),
        ),
        migrations.AddIndex(
            model_name='examresult',
            index=models.Index(fields=['is_flagged'], name='results_exa_is_flag_bd228d_idx'),
        ),
        migrations.AddIndex(
            model_name='examresult',
            index=models.Index(fields=['is_reviewed'], name='results_exa_is_revi_f7776d_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='examresult',
            unique_together={('student', 'exam')},
        ),
        migrations.AddIndex(
            model_name='examviolation',
            index=models.Index(fields=['exam_result'], name='results_exa_exam_re_51031c_idx'),
        ),
        migrations.AddIndex(
            model_name='examviolation',
            index=models.Index(fields=['violation_type'], name='results_exa_violati_ba6c37_idx'),
        ),
        migrations.AddIndex(
            model_name='examviolation',
            index=models.Index(fields=['severity'], name='results_exa_severit_7b6743_idx'),
        ),
    ]
