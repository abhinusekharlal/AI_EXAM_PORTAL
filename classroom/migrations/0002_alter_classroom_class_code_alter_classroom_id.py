# Generated by Django 5.1.5 on 2025-01-17 18:28

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("classroom", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="classroom",
            name="class_code",
            field=models.CharField(max_length=10, unique=True),
        ),
        migrations.AlterField(
            model_name="classroom",
            name="id",
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, primary_key=True, serialize=False
            ),
        ),
    ]
