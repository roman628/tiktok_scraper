# Generated migration for ML metrics fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('server', '0003_transcription'),
    ]

    operations = [
        migrations.AddField(
            model_name='mltrainingrun',
            name='r2_score',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='mltrainingrun',
            name='mae',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='mltrainingrun',
            name='rmse',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='mltrainingrun',
            name='prediction_range',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='mltrainingrun',
            name='prediction_std',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='mltrainingrun',
            name='cv_mean',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='mltrainingrun',
            name='cv_std',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='mltrainingrun',
            name='effectiveness_score',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='mltrainingrun',
            name='test_predictions',
            field=models.JSONField(blank=True, null=True),
        ),
    ]