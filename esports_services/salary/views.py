from django.contrib.auth.forms import AuthenticationForm
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import TemplateView, ListView, DetailView
from django.contrib.auth.views import LoginView
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import Group
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.db.models import Q, QuerySet

from .forms import *
from .utils import *

import datetime
from typing import *
from dateutil.relativedelta import relativedelta


# Registration, Login, Logout
class RegistrationUser(TitleMixin, SuccessUrlMixin, TemplateView):
    template_name = 'salary/registration.html'
    title = 'Регистрация сотрудника'
    user_form = UserRegistrationForm
    profile_form = EmployeeRegistrationForm

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(
            profile_form=self.profile_form,
            user_form=self.user_form
        )
        return render(request, self.template_name, context=context)

    def post(self, request, **kwargs):
        user_form_class = self.user_form(request.POST)
        profile_form_class = self.profile_form(request.POST, request.FILES)
        if user_form_class.is_valid() and profile_form_class.is_valid():
            user = user_form_class.save(commit=False) 
            profile = profile_form_class.save(commit=False)
            user.save()
            user.is_active = False
            user.groups.add(Group.objects.get(name='employee'))
            if profile.position.name == 'cash_admin':
                user.groups.add(Group.objects.get(name='cashiers'))
            user.save()
            profile.user = user
            profile.save()

            return redirect(self.get_success_url())
        else:
            context = self.get_context_data(
                profile_form=profile_form_class,
                user_form=user_form_class
            )
            return render(request, self.template_name, context=context)


class DismissalEmployee(StaffPermissionRequiredMixin, TitleMixin,
                        SuccessUrlMixin, TemplateView):
    model = Profile
    title = 'Увольнение сотрудника'
    template_name = 'salary/dismissal_user.html'
    profile_form = DismissalEmployeeForm

    def dispatch(self, request, *args, **kwargs):
        self.object = get_object_or_404(
            User.objects.select_related('profile'),
            pk=self.kwargs.get('pk', 0)
        )
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        profile_form_class = self.profile_form(instance=self.object.profile)
        context = self.get_context_data(
            profile_form=profile_form_class,
        )
        return render(request, self.template_name, context=context)

    def post(self, request, **kwargs):
        profile_form_class = self.profile_form(request.POST, instance=self.object.profile)
        if profile_form_class.is_valid():
            self.object.is_active = False
            self.object.save()
            profile = profile_form_class.save(commit=False)
            profile.save()
            return redirect(self.get_success_url())
        else:
            context = self.get_context_data(
                profile_form=profile_form_class,
            )
            return render(request, self.template_name, context=context)


class LoginUser(TitleMixin, SuccessUrlMixin, LoginView):
    template_name = 'salary/login.html'
    form_class = AuthenticationForm
    redirect_authenticated_user = True
    title = 'Авторизация'


def logout_user(request):
    logout(request)
    return redirect('login')


# Staff Functionality
class StaffUserView(StaffPermissionRequiredMixin, TotalDataMixin, TemplateView):
    template_name = 'salary/staff_user_view.html'

    def dispatch(self, request, *args: Any, **kwargs: Any):
        self.required_year = self.kwargs.get('year')
        self.required_month = self.kwargs.get('month')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request_user = self.kwargs.get('request_user')
        get_user = get_object_or_404(User, username=request_user)
        workshifts = WorkingShift.objects.filter(
            shift_date__year=self.required_year,
            shift_date__month=self.required_month
        ).filter(Q(cash_admin=get_user) | Q(hall_admin=get_user))
        context['title'] = f'Данные пользователя {get_user}'
        context['request_user'] = get_user
        context['workshifts'] = workshifts
        context['total_values'] = self.get_total_values(get_user, workshifts)

        return context

class AdminView(StaffPermissionRequiredMixin, StaffOnlyMixin, TitleMixin,
                TemplateView):
    template_name = 'salary/dashboard.html'
    login_url = 'login'
    title = 'Панель управления'


class AdminUserView(StaffPermissionRequiredMixin, TitleMixin, ListView):
    template_name = 'salary/show_users.html'
    model = User
    title = 'Управление персоналом'

    def get_queryset(self):
        query = User.objects.exclude(is_staff=True).select_related(
            'profile',
            'profile__position'
        ).order_by('-profile__position')

        if not self.kwargs.get('all'):
            return query.filter(profile__dismiss_date__isnull=True)

        return query

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.kwargs.get('all'):
            context['only_actived'] = True
        return context

class ReportsView(StaffPermissionRequiredMixin, TitleMixin, ListView):
    template_name = 'salary/reports_list.html'
    model = WorkingShift
    title = 'Отчеты'

    def get_queryset(self):
        query = WorkingShift.objects.dates('shift_date', 'month')
        return query


class AdminWorkshiftsView(StaffPermissionRequiredMixin, TitleMixin, ListView):
    template_name = 'salary/staff_view_workshifts.html'
    model = WorkingShift
    title = 'Смены'
    paginate_by = 5

    def get_queryset(self):
        workshifts = WorkingShift.objects.filter(is_verified=False).select_related(
            'hall_admin__profile',
            'cash_admin__profile',
        )
        if self.kwargs.get('all'):
            workshifts = WorkingShift.objects.all().select_related(
                'hall_admin__profile',
                'cash_admin__profile',
            )

        return workshifts

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.kwargs.get('all'):
            context['only_verified'] = True
        return context


class DeleteWorkshift(PermissionRequiredMixin, TitleMixin, SuccessUrlMixin,
                        DeleteView):
    model = WorkingShift
    permission_required = 'salary.delete_workingshift'
    title = 'Удаление смены'


class MonthlyReportListView(PermissionRequiredMixin, StaffOnlyMixin, 
                            TitleMixin, ListView):
    model = WorkingShift
    permission_required = 'salary.view_workingshift'
    template_name = 'salary/monthlyreport_list.html'
    title = 'Сводный отчёт'

    def dispatch(self, request, *args, **kwargs):
        self.year = self.kwargs.get('year')
        self.month = self.kwargs.get('month')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = WorkingShift.objects.select_related(
            'cash_admin__profile__position',
            'hall_admin__profile__position',
        ).filter(
            shift_date__month=self.month,
            shift_date__year=self.year,
            is_verified=True
        )

        return queryset

    def get_sum_dict_values(self, first_dict: dict, second_dict:dict) -> dict:
        summable_fields = (
            'summary_revenue',
            'count',
            'penalties',
            'estimated_earnings',
            'shortage',
        )

        total_values_dict = {
            key: round(sum((first_dict.get(key, 0), second_dict.get(key, 0))), 2)
            for key in summable_fields
        }

        return total_values_dict

    def get_earnings_data_dict(self, workshifts: QuerySet) -> tuple:
        earnings_data_list = list()
        for workshift in workshifts:
            admin_earnings_dict = workshift.hall_admin_earnings_calc()
            cashier_earnings_dict = workshift.cashier_earnings_calc()
            admin_dict = dict()
            cashier_dict = dict()
            earnings_data_dict = dict()
            summary_data_dict = dict()
            general_dict = {
                'summary_revenue': workshift.get_summary_revenue(),
                'count': 1,
            }

            admin_dict.update({
                'username': workshift.hall_admin,
                'penalties': admin_earnings_dict['penalty'],
                'estimated_earnings': admin_earnings_dict['estimated_earnings'],
            })
            admin_dict.update(general_dict)

            cashier_dict.update({
                'username': workshift.cash_admin,
                'shortage': workshift.shortage,
                'penalties': cashier_earnings_dict['penalty'],
                'estimated_earnings': cashier_earnings_dict['estimated_earnings'],
            })
            cashier_dict.update((general_dict))

            earnings_data_list.extend([admin_dict, cashier_dict])

        for current_dict in earnings_data_list:
            existing_dict = earnings_data_dict.get(current_dict['username'].get_full_name())
            if existing_dict:
                existing_dict.update(
                    self.get_sum_dict_values(existing_dict, current_dict)
                )
            else:
                earnings_data_dict.update({
                    current_dict['username'].get_full_name(): current_dict
                })
            summary_data_dict.update(
                self.get_sum_dict_values(summary_data_dict, current_dict)
            )
        earnings_data_dict = dict(
            sorted(earnings_data_dict.items(), key=lambda item: item[1]['summary_revenue'], reverse=True)
        )
        summary_data_dict['count'] = workshifts.count()
        summary_data_dict['summary_revenue'] = sum(
            [workshift.get_summary_revenue() for workshift in workshifts]
        )
        return (earnings_data_dict, summary_data_dict, )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee_earnings_data, summary_earnings_data = self.get_earnings_data_dict(self.object_list)

        context.update({
            'employee_earnings_data': employee_earnings_data,
            'summary_earnings_data': summary_earnings_data,
            'current_date': datetime.date(self.year, self.month, 1),
        })

        return context


class AddMisconductView(StaffPermissionRequiredMixin, TitleMixin,
                        SuccessUrlMixin, CreateView):
    model = Misconduct
    title = 'Добавление дисциплинарного проступка'
    form_class = AddMisconductForm

    def form_valid(self, form):
        object = form.save(commit=False)
        object.moderator = self.request.user
        object.editor = self.request.user.get_full_name()
        object.change_date = timezone.localtime(timezone.now())
        object.slug = return_misconduct_slug(
            object.intruder.last_name,
            object.misconduct_date
        )
        workshift_queryset = WorkingShift.objects.filter(
            shift_date=object.misconduct_date
        )
        if workshift_queryset.exists():
            current_workshift = workshift_queryset.get()
            object.workshift = current_workshift
            if object.intruder == current_workshift.hall_admin:
                current_workshift.hall_admin_penalty += object.penalty
            elif object.intruder == current_workshift.cash_admin:
                current_workshift.cash_admin_penalty += object.penalty
            current_workshift.save()

        return super().form_valid(form)


def load_regulation_data(request):
    requested_article = request.GET.get('regulations_article')
    regulation_article = DisciplinaryRegulations.objects.get(pk=requested_article)
    response = {
        'title': f'п. {regulation_article.article} {regulation_article.title}',
        'sanction': regulation_article.sanction,
        'penalty': regulation_article.base_penalty,
    }
    return JsonResponse(response)


class MisconductListView(StaffPermissionRequiredMixin, TitleMixin, ListView):
    model = Misconduct
    title = 'Список нарушителей'
    template_name = 'salary/intruders_list.html'

    def get_queryset(self):
        queryset = Misconduct.objects.all().select_related('intruder')
        intruder_dict = dict()
        for misconduct in queryset:
            count = intruder_dict.get(misconduct.intruder)
            if count:
                count += 1
                intruder_dict.update({
                    misconduct.intruder: count
                })
            else:
                intruder_dict.update({
                    misconduct.intruder: 1
                })

        return dict(sorted(intruder_dict.items(), key=lambda item: item[1], reverse=True))


class MisconductUserView(LoginRequiredMixin, TitleMixin, ListView):
    model = Misconduct
    title = 'Нарушения'

    def dispatch(self, request, *args: Any, **kwargs: Any):
        self.intruder = self.kwargs.get('username')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Misconduct.objects.filter(intruder__username=self.intruder).select_related('intruder', 'regulations_article')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['intruder'] = get_object_or_404(User, username=self.intruder)
        return context


class MisconductUpdateView(StaffPermissionRequiredMixin, TitleMixin, 
                            EditModelEditorFields, SuccessUrlMixin, UpdateView):
    model = Misconduct
    title = 'Редактирование данных нарушения'
    form_class = EditMisconductForm

    def form_valid(self, form):
        if self.object.workshift:
            old_penalty = Misconduct.objects.filter(misconduct_date=self.object.workshift.shift_date, intruder=self.object.intruder).get().penalty
            if self.object.workshift.cash_admin == self.object.intruder:
                self.object.workshift.cash_admin_penalty += -old_penalty + self.object.penalty
            elif self.object.workshift.hall_admin == self.object.intruder:
                self.object.workshift.hall_admin_penalty += -old_penalty + self.object.penalty
            self.object.workshift.save()

        return super().form_valid(form)


class MisconductDeleteView(StaffPermissionRequiredMixin, TitleMixin,
                            SuccessUrlMixin, DeleteView):
    model = Misconduct
    title = 'Удаление нарушения'

    def post(self, request, *args, **kwargs):
        object = self.get_object()
        if object.workshift:
            if object.workshift.cash_admin == object.intruder:
                if object.penalty <= object.workshift.cash_admin_penalty:
                    object.workshift.cash_admin_penalty -= object.penalty
                else:
                    object.workshift.cash_admin_penalty = 0.0
            elif object.workshift.hall_admin == object.intruder:
                if object.penalty <= object.workshift.hall_admin_penalty:
                    object.workshift.hall_admin_penalty -= object.penalty
                else:
                    object.workshift.hall_admin_penalty = 0.0

            object.workshift.save()
        return super().post(request, *args, **kwargs)


# Employee functionality
class EditUser(LoginRequiredMixin, TitleMixin, SuccessUrlMixin, TemplateView):
    template_name = 'salary/edit_user_profile.html'
    title = 'Редактирование пользователя'
    userform = EditUserForm
    profileform = EditProfileForm

    def dispatch(self, request, *args: Any, **kwargs: Any):
        if self.kwargs.get('pk'):
            self.edited_user = get_object_or_404(User.objects.select_related('profile'), pk=self.kwargs.get('pk', 0))
        else:
            self.edited_user = self.request.user
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args: Any, **kwargs: Any):
        user_form_class = self.userform(instance=self.edited_user)
        profile_form_class = self.profileform(instance=self.edited_user.profile)
        context = self.get_context_data(
            profile_form=profile_form_class,
            user_form=user_form_class
        )
        return render(request, self.template_name, context=context)

    def post(self, request, **kwargs):
        user_form_class = self.userform(request.POST, instance=self.edited_user)
        profile_form_class = self.profileform(request.POST, request.FILES, instance=self.edited_user.profile)
        if user_form_class.is_valid() and profile_form_class.is_valid():
            user = user_form_class.save(commit=False)
            profile = profile_form_class.save(commit=False)
            user.save()
            profile.save()
            return redirect(self.get_success_url())
        else:
            user_form_class = self.userform
            profile_form_class = self.profileform
            context = self.get_context_data(
                profile_form=profile_form_class,
                user_form=user_form_class
            )
            return render(request, self.template_name, context=context)


class StaffEditUser(StaffPermissionRequiredMixin, EditUser):
    userform = StaffEditUserForm
    profileform = StaffEditProfileForm
    title = 'Редактирование профиля'


class WorkshiftDetailView(LoginRequiredMixin, TitleMixin, DetailView):
    model = WorkingShift
    title = 'Детальный просмотр смены'
    queryset = WorkingShift.objects.select_related(
            'cash_admin__profile__position',
            'hall_admin__profile__position',
    )
    context_object_name = 'work_shift'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['yesterday'] = context['object'].shift_date - datetime.timedelta(days=1)

        return context

class MisconductDetailView(LoginRequiredMixin, TitleMixin, DetailView):
    model = Misconduct
    title = 'Протокол нарушения'
    context_object_name = 'misconduct'
    queryset = Misconduct.objects.select_related('intruder', 'moderator', 'regulations_article')


class NewUserView(TitleMixin, TemplateView):
    template_name = 'salary/userboard.html'
    title = 'Новая панель пользователя'


class IndexView(LoginRequiredMixin, TitleMixin, TotalDataMixin,
                SuccessUrlMixin, ListView):
    model = WorkingShift
    login_url = 'login'
    template_name = 'salary/account.html'
    title = 'Личный кабинет'

    def dispatch(self, request, *args, **kwargs):
        if self.request.user.is_staff:
            return redirect('dashboard')
        if request.user.is_authenticated:
            self.employee = get_object_or_404(
                User.objects.select_related('profile__position'),
                pk=self.request.user.pk
            )
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        query = WorkingShift.objects.filter(Q(cash_admin=self.employee) | Q(hall_admin=self.employee))
        return query

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        current_year = self.kwargs.get('year', datetime.date.today().year)
        current_month = self.kwargs.get('month', datetime.date.today().month)
        current_workshifts = self.object_list.filter(shift_date__month=current_month, shift_date__year=current_year)

        # Note
        previous_date = datetime.date(current_year, current_month, 1) - relativedelta(months=1)
        next_date = datetime.date(current_year, current_month, 1) + relativedelta(months=1)
        if self.object_list.filter(shift_date__month=previous_date.month, shift_date__year=previous_date.year).exists():
            context['previous_date'] = previous_date
        if self.object_list.filter(shift_date__month=next_date.month, shift_date__year=next_date.year).exists():
            context['next_date'] = next_date

        context.update({
            'current_date': datetime.date(current_year, current_month, 1),
            'experience': self.employee.profile.get_work_experience,
            'workshifts': current_workshifts,
            'total_values': self.get_total_values(self.employee, current_workshifts),
            'today_workshift_exists': WorkingShift.objects.filter(shift_date=datetime.date.today()).exists(),
        })

        return context


class AddWorkshiftData(PermissionRequiredMixin, TitleMixin, SuccessUrlMixin,
                        CreateView):
    form_class = AddWorkshiftDataForm
    permission_required = 'salary.add_workingshift'
    template_name = 'salary/add_workshift.html'
    title = 'Добавление смен'

    def get_initial(self):
        initional = super().get_initial()
        initional.update({
            'cash_admin': self.request.user,
            'shift_date': datetime.date.today().strftime('%Y-%m-%d'),
        })
        return initional

    def form_valid(self, form):
        object = form.save(commit=False)
        object.editor = self.request.user.get_full_name()
        object.change_date = timezone.localtime(timezone.now())
        object.slug = object.shift_date
        if Misconduct.objects.filter(misconduct_date=object.shift_date).exists():
            object.save()
            for misconduct in Misconduct.objects.filter(
                    misconduct_date=object.shift_date):
                misconduct.workshift = object
                misconduct.save()
                if object.hall_admin == misconduct.intruder:
                    object.hall_admin_penalty += misconduct.penalty
                elif object.cash_admin == misconduct.intruder:
                    object.cash_admin_penalty += misconduct.penalty
                object.save()

        return super().form_valid(form)


class EditWorkshiftData(PermissionRequiredMixin, SuccessUrlMixin,
                        EditModelEditorFields, UpdateView):
    model = WorkingShift
    form_class = EditWorkshiftDataForm
    permission_required = 'salary.change_workingshift'
    template_name = 'salary/edit_workshift.html'

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        context['start_date'] = context['object'].shift_date - relativedelta(days=1)
        return context


class StaffEditWorkshift(StaffOnlyMixin, EditWorkshiftData):
    form_class = StaffEditWorkshiftForm


# Additional functionality
def page_not_found(request, exception):
    response = render(request, 'salary/404.html', {'title': 'Page not found'})
    response.status_code = 404
    return response


def page_forbidden(request, exception):
    response = render(request, 'salary/403.html', {'title': 'Access forbidden'})
    response.status_code = 403
    return response