from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.urls import reverse_lazy
from django.utils import timezone

import datetime
from dateutil.relativedelta import relativedelta


HOURS_VARIANT = ('час', 'часа', 'часов')
DAYS_VARIANT = ('день', 'дня', 'дней')
MONTH_VARIANT = ('месяц','месяца','месяцев')
YEARS_VARIANT = ('год', 'года', 'лет')

REQUIRED_EXPERIENCE = 90
EXPERIENCE_BONUS = 200.0
PUBLICATION_BONUS = 100.0

ATTESTATION_BONUS = 200.0
DISCIPLINE_AWARD = 1000.0
HALL_CLEANING_BONUS = 400.0
HOOKAH_BONUS_RATIO = 0.2

ADMIN_BONUS_CRITERIA = {
    'bar' : [(0, 0.005), (3000, 0.01), (4000, 0.02), (6000, 0.025), (8000, 0.03)],
    'game_zone': [(0, 0.005), (20000, 0.01), (25000, 0.0125), (27500, 0.015), (30000, 0.0175)],
    'vr': [(0, 0.1), (1000, 0.12), (2000, 0.13), (3000, 0.14), (5000, 0.15)]
}

CASHIER_BONUS_CRITERIA = {
    'bar' : [(0, 0.03), (3000, 0.04), (4000, 0.05), (6000, 0.06), (8000, 0.07)],
    'game_zone': [(0, 0.005), (20000, 0.01), (25000, 0.0125), (27500, 0.015), (30000, 0.0175)],
    'vr': [(0, 0.05), (1000, 0.06), (2000, 0.065), (3000, 0.07), (5000, 0.075)]
}


def user_directory_path(instance, filename):
    return 'user_{0}/{1}'.format(instance.user.id, filename)


def get_last_name(self):
    return f'{self.last_name} {self.first_name}'

User.add_to_class("get_full_name", get_last_name)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    birth_date = models.DateField(null=True, verbose_name='Дата рождения')
    employment_date = models.DateField(null=True, verbose_name='Дата трудоустройства')
    position = models.ForeignKey('Position', on_delete=models.PROTECT, null=True, verbose_name='Должность')
    attestation_date = models.DateField(blank=True, null=True, verbose_name='Дата прохождения аттестации')
    dismiss_date = models.DateField(blank=True, null=True, verbose_name='Дата увольнения')
    photo = models.ImageField(blank=True, null=True, upload_to=user_directory_path, verbose_name='Фото профиля')

    def __str__(self) -> str:
        return f'{self.user.first_name} {self.user.last_name} [{self.user.username}]'

    class Meta:
        verbose_name = 'Профиль сотрудника'
        verbose_name_plural = 'Профили сотрудников'

    @classmethod
    def get_choice_plural(cls, amount, variants):
        if amount % 10 == 1 and amount % 100 != 11:
            choice = 0
        elif amount % 10 >= 2 and amount % 10 <= 4 and \
                (amount % 100 < 10 or amount % 100 >= 20):
            choice = 1
        else:
            choice = 2

        return variants[choice]

    def get_experience_text(self):
        end_date = self.dismiss_date if self.dismiss_date else datetime.date.today()
        experience = relativedelta(end_date, self.employment_date)
        days, months, years = experience.days, experience.months, experience.years
        experience_text = ''

        if years:
            experience_text = f'{years} {self.get_choice_plural(years, YEARS_VARIANT)} '

        if months:
            experience_text += f'{months} {self.get_choice_plural(months, MONTH_VARIANT)} '

        if days or not experience_text:
            experience_text += f'{days} {self.get_choice_plural(days, DAYS_VARIANT)}'

        return experience_text


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        instance.profile = Profile.objects.create(user=instance)
    instance.profile.save()


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()


class DisciplinaryRegulations(models.Model):
    article = models.CharField(max_length=10, verbose_name='Пункт')
    title = models.CharField(max_length=255, verbose_name='Наименование')
    base_penalty = models.FloatField(default=0.0, verbose_name='Сумма штрафа')
    sanction = models.CharField(max_length=255, verbose_name='Санкция', blank=True, null=True)

    class Meta:
        verbose_name = 'Пункт регламента'
        verbose_name_plural = 'Дисциплинарный регламент'

    def __str__(self) -> str:
        return f'{self.article} {self.title}'


class Misconduct(models.Model):
    class MisconductStatus(models.TextChoices):
        ADDED = 'AD', 'Ожидает объяснение'
        WAIT = 'WT', 'Ожидает решение'
        CLOSED = 'CL', 'Решение принято'

    misconduct_date = models.DateField(verbose_name='Дата нарушения')
    workshift_date = models.DateField(verbose_name='Дата смены')
    intruder = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name='Сотрудник', related_name='intruder')
    regulations_article = models.ForeignKey(DisciplinaryRegulations, on_delete=models.PROTECT, verbose_name='Пункт дисциплинарного регламента')
    penalty = models.FloatField(verbose_name='Сумма штрафа', default=0.0)
    explanation_exist = models.BooleanField(verbose_name='Наличие объяснительной', default=False)
    moderator = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name='Арбитр (кто выявил)', related_name='moderator')
    comment = models.TextField(verbose_name='Примечание', blank=True)
    status = models.CharField(max_length=60, choices=MisconductStatus.choices, default=MisconductStatus.ADDED, verbose_name='Статус рассмотрения')
    slug = models.SlugField(max_length=60, unique=True, verbose_name='URL', null=True, blank=True)
    change_date = models.DateTimeField(verbose_name='Дата изменения', blank=True, null=True)
    editor = models.TextField(verbose_name='Редактор', blank=True, editable=False)

    class Meta:
        verbose_name = 'Дисциплинарный проступок'
        verbose_name_plural = 'Дисциплинарные проступки'
        ordering = ['-misconduct_date']

    def __str__(self) -> str:
        return f'{self.misconduct_date} {self.intruder.get_full_name()}'

    def save(self, *args, **kwargs):
        if self.explanation_exist and self.status == self.MisconductStatus.ADDED:
            self.status = self.MisconductStatus.WAIT
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse_lazy('misconduct_detail', kwargs={'slug': self.slug})


class WorkingShift(models.Model):
    hall_admin = models.ForeignKey(User, on_delete=models.PROTECT, related_name='hall_admin')
    cash_admin = models.ForeignKey(User, on_delete=models.PROTECT, related_name='cash_admin')
    shift_date = models.DateField(verbose_name='Дата смены', unique=True, db_index=True)
    bar_revenue = models.FloatField(verbose_name='Выручка по бару', default=0.0)
    game_zone_revenue = models.FloatField(verbose_name='Выручка игровой зоны (без доп. услуг)', default=0.0)
    game_zone_error = models.FloatField(verbose_name='Сумма ошибок', default=0.0)
    vr_revenue = models.FloatField(verbose_name='Выручка доп. услуги и VR', default=0.0)
    hookah_revenue = models.FloatField(verbose_name='Выручка по кальянам', default=0.0)
    hall_cleaning = models.BooleanField(default=True, verbose_name='Наведение порядка')
    shortage = models.FloatField(default=0, verbose_name='Недостача')
    shortage_paid = models.BooleanField(default=False, verbose_name="Отметка о погашении недостачи")
    summary_revenue = models.FloatField(default=0, verbose_name='Суммарная выручка')
    slug = models.SlugField(max_length=60, unique=True, verbose_name='URL', null=True, blank=True)
    is_verified = models.BooleanField(default=False, verbose_name='Проверено', db_index=True)
    comment_for_cash_admin = models.TextField(verbose_name='Примечание для кассира', blank=True)
    comment_for_hall_admin = models.TextField(verbose_name='Примечание для админа', blank=True)
    publication_link = models.TextField(verbose_name='СММ-публикация (ссылка)', blank=True)
    publication_is_verified = models.BooleanField(default=False, verbose_name='СММ-публикация проверена')
    change_date = models.DateTimeField(verbose_name='Дата изменения', blank=True, null=True)
    editor = models.TextField(verbose_name='Редактор', blank=True, editable=False)
    hall_admin_penalty = models.FloatField(verbose_name='Штраф администратора зала', default=0.0)
    cash_admin_penalty = models.FloatField(verbose_name='Штраф администратора кассы', default=0.0)

    class Meta:
        verbose_name = 'Смена'
        verbose_name_plural = 'Смены'
        ordering = ['-shift_date']
        permissions = [
            ("view_workshift_report", "Can view monthly reports"),
            ("advanced_change_workshift", "Can edit the entire contents of the workingshift"),
        ]

    def __str__(self) -> str:
        return self.shift_date.strftime('%d-%m-%Y')

     # Earnings block

    def get_experience_bonus(self, employee) -> float:
        current_experience = (self.shift_date - employee.profile.employment_date).days
        if REQUIRED_EXPERIENCE <= current_experience:
            return EXPERIENCE_BONUS

        return 0.0

    def get_publication_bonus(self) -> float:
        if self.publication_link and self.publication_is_verified:
            return PUBLICATION_BONUS

        return 0.0

    def get_attestation_bonus(self, employee) -> float:
        if (employee.profile.attestation_date and
                employee.profile.attestation_date <= self.shift_date):
            return ATTESTATION_BONUS

        return 0.0

    def get_revenue_bonuses(self, criteria: dict) -> dict:
        if self.game_zone_revenue >= self.game_zone_error:
            game_zone_subtotal = self.game_zone_revenue - self.game_zone_error 
        else:
            game_zone_subtotal = 0.0

        revenue_tuple = (
            self.bar_revenue,
            game_zone_subtotal,
            self.vr_revenue
        )

        result_list = []
        for revenue, current_critera in zip(revenue_tuple, criteria.values()):
            criteria_ratio = list(filter(lambda x: x[0] <= revenue, current_critera))[-1][1]
            result_list.append((round(revenue * criteria_ratio, 2), round(criteria_ratio * 100, 1)))

        return {
            'bar': result_list[0],
            'game_zone': result_list[1],
            'vr': result_list[2]
        }

    def employee_earnings_calc(self, employee) -> dict:
        base_earnings = {
            'salary': employee.profile.position.position_salary,
            'experience': self.get_experience_bonus(employee),
            'penalty': 0.0,
            'award': DISCIPLINE_AWARD,
            'attestation': self.get_attestation_bonus(employee),
            'publication_bonus': self.get_publication_bonus(),
            'game_zone': (0.0, 0.0),
            'bar': (0.0, 0.0),
            'vr': (0.0, 0.0),
        }

        return base_earnings

    def final_earnings_calculation(self, earnings: dict) -> dict:
        tuple_fields = ('bar', 'game_zone', 'vr')
        exclude_bonus_fields = ('salary', 'penalty', 'experience', 'attestation')
        bonus_part = 0.0

        for key, value in earnings.items():
            if key not in exclude_bonus_fields:
                if key not in tuple_fields:
                    bonus_part += value
                else:
                    bonus_part += value[0]

        if bonus_part > earnings['penalty']:
            remaining_bonus_part = bonus_part - earnings['penalty']
        else: 
            remaining_bonus_part = 0.0

        basic_part = sum([
                earnings.get('salary'),
                earnings.get('experience'),
                earnings.get('attestation')
        ])

        return {
            'basic_part': round(basic_part, 2),
            'bonus_part': round(bonus_part, 2),
            'retention': round(bonus_part - remaining_bonus_part, 2),
            'estimated_earnings': round(bonus_part + basic_part, 2),
            'final_earnings': round(remaining_bonus_part + basic_part,2),
        }

    def hall_admin_earnings_calc(self) -> dict:
        earnings = self.employee_earnings_calc(self.hall_admin)
        earnings['penalty'] = self.hall_admin_penalty
        earnings['cleaning'] = HALL_CLEANING_BONUS if self.hall_cleaning else 0.0
        earnings['hookah'] = round(self.hookah_revenue * HOOKAH_BONUS_RATIO, 2)
        earnings.update(self.get_revenue_bonuses(ADMIN_BONUS_CRITERIA))
        earnings.update(self.final_earnings_calculation(earnings))

        return earnings

    def cashier_earnings_calc(self) -> dict:
        earnings = self.employee_earnings_calc(self.cash_admin)
        earnings['penalty'] = self.cash_admin_penalty
        earnings.update(self.get_revenue_bonuses(CASHIER_BONUS_CRITERIA))
        earnings.update(self.final_earnings_calculation(earnings))
        earnings['before_shortage'] = earnings['final_earnings']
        if self.shortage and not self.shortage_paid:
            earnings['final_earnings'] = round(earnings['final_earnings'] - self.shortage * 2, 2)

        return earnings

    def get_absolute_url(self):
        return reverse_lazy('detail_workshift', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        total_revenue = sum((
            self.bar_revenue,
            self.game_zone_revenue,
            self.vr_revenue,
            self.hookah_revenue,
            -self.game_zone_error,
        ))
        self.summary_revenue=round(
            total_revenue, 2) if total_revenue > 0.0 else 0.0

        misconduct_queryset = Misconduct.objects.filter(
            workshift_date=self.shift_date,
            status=Misconduct.MisconductStatus.CLOSED,
        )
        self.cash_admin_penalty = 0.0
        self.hall_admin_penalty = 0.0
        for misconduct in misconduct_queryset:
            if misconduct.intruder == self.cash_admin:
                self.cash_admin_penalty += misconduct.penalty
            elif misconduct.intruder == self.hall_admin:
                self.hall_admin_penalty += misconduct.penalty
        super().save(*args, **kwargs)


@receiver(post_save, sender=Misconduct)
@receiver(post_delete, sender=Misconduct)
def run_calculating_penalties(sender, instance, created=None, **kwargs):
    workshift_queryset = WorkingShift.objects.filter(
            shift_date=instance.workshift_date
    ).first()
    if workshift_queryset:
        workshift_queryset.save()


class Position(models.Model):
    title = models.CharField(max_length=255)
    name = models.CharField(max_length=60)
    position_salary = models.FloatField(blank=True, null=True)

    class Meta:
        verbose_name = 'Должность'
        verbose_name_plural = 'Должности'

    def __str__(self) -> str:
        return self.title
