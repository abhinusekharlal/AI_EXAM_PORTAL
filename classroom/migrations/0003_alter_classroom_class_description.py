# Generated by Django 5.1.5 on 2025-01-17 18:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("classroom", "0002_alter_classroom_class_code_alter_classroom_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="classroom",
            name="class_description",
            field=models.TextField(default=""),
        ),
    ]
