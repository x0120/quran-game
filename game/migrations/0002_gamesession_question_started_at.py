from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='gamesession',
            name='question_started_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
