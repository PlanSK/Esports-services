# Generated by Django 4.0 on 2021-12-14 07:43

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('salary', '0011_alter_employee_position_alter_workingshift_shortage'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='position',
            options={'verbose_name': 'Должность'},
        ),
        migrations.AlterField(
            model_name='employee',
            name='birth_date',
            field=models.DateField(null=True, verbose_name='Дата рождения'),
        ),
        migrations.AlterField(
            model_name='employee',
            name='employment_date',
            field=models.DateField(null=True, verbose_name='Дата трудоустройства'),
        ),
        migrations.AlterField(
            model_name='employee',
            name='position',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='salary.position'),
        ),
    ]
