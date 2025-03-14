# Generated by Django 5.1.5 on 2025-01-23 16:15

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("classroom", "0003_alter_classroom_class_description"),
    ]

    operations = [
        migrations.CreateModel(
            name="Question",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("question_text", models.TextField()),
                ("option1", models.CharField(max_length=100)),
                ("option2", models.CharField(max_length=100)),
                ("option3", models.CharField(max_length=100)),
                ("option4", models.CharField(max_length=100)),
                ("correct_option", models.CharField(max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "exam",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="questions",
                        to="classroom.exam",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Questions",
                "ordering": ["-created_at"],
            },
        ),
    ]
