from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0002_gamesession_question_started_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='gamesession',
            name='question_order',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
