# Generated by Django 5.1.5 on 2025-02-03 19:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("classroom", "0010_exam_teacher"),
    ]

    operations = [
        migrations.AlterField(
            model_name="question",
            name="correct_option",
            field=models.CharField(
                choices=[
                    ("1", "Option 1"),
                    ("2", "Option 2"),
                    ("3", "Option 3"),
                    ("4", "Option 4"),
                ],
                max_length=1,
            ),
        ),
    ]
