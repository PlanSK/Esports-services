# Generated by Django 4.0 on 2021-12-11 21:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('salary', '0008_alter_workingshift_cash_admin'),
    ]

    operations = [
        migrations.AlterField(
            model_name='workingshift',
            name='shortage',
            field=models.FloatField(null=True),
        ),
    ]
