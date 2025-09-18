"""
This migration is a no-op to fix the mismatch between Django models and database.
The model_version and status fields already exist in the database.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0005_collector_status'),
    ]

    operations = [
        # No operations needed - fields already exist in database
        # This migration just marks that Django knows about these fields
    ]