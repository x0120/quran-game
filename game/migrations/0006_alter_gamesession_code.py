from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0005_gamesession_selected_letters'),
    ]

    operations = [
        migrations.AlterField(
            model_name='gamesession',
            name='code',
            field=models.CharField(max_length=4, unique=True),
        ),
    ]
