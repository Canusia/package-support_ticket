# Generated manually 2026-06-29

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('support_ticket', '0005_drop_media_fields'),
    ]

    operations = [
        # status: drop choices, widen to 40 chars
        migrations.AlterField(
            model_name='ticket',
            name='status',
            field=models.CharField(default='Submitted', max_length=40),
        ),
        # submitted_on: was auto_now (updates on every save) → auto_now_add (created time only)
        migrations.AlterField(
            model_name='ticket',
            name='submitted_on',
            field=models.DateTimeField(auto_now_add=True),
        ),
        # last_updated_on: was nullable with no auto behaviour → auto_now (updated on every save)
        # preserve_default=False so the migration default is one-off (not kept on the model field).
        migrations.AlterField(
            model_name='ticket',
            name='last_updated_on',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
