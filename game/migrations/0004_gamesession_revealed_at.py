from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0003_gamesession_question_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='gamesession',
            name='revealed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
