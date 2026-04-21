from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0006_alter_gamesession_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='gamesession',
            name='mode',
            field=models.CharField(default='multiplayer', max_length=20),
        ),
    ]
