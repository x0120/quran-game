from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0004_gamesession_revealed_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='gamesession',
            name='selected_letters',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
