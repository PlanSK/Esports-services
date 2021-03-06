# Generated by Django 4.0.4 on 2022-06-19 09:27

from django.db import migrations, models
import salary.models
import salary.utils


class Migration(migrations.Migration):

    dependencies = [
        ('salary', '0011_alter_profile_profile_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='photo',
            field=models.ImageField(blank=True, null=True, storage=salary.utils.OverwriteStorage(), upload_to=salary.models.user_directory_path, verbose_name='Фото профиля'),
        ),
    ]
