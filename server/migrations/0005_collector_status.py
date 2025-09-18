# Generated manually for CollectorStatus model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0004_ml_metrics'),
    ]

    operations = [
        migrations.CreateModel(
            name='CollectorStatus',
            fields=[
                ('id', models.IntegerField(default=1, primary_key=True, serialize=False)),
                ('status', models.CharField(default='stopped', max_length=20)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('stopped_at', models.DateTimeField(blank=True, null=True)),
                ('last_activity', models.DateTimeField(auto_now=True)),
                ('urls_processed', models.IntegerField(default=0)),
                ('pid', models.IntegerField(blank=True, null=True)),
            ],
            options={
                'db_table': 'collector_status',
            },
        ),
    ]