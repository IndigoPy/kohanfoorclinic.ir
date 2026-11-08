from datetime import timedelta

import jdatetime
from django.utils import timezone
from django_filters.views import FilterView
from ..models import Appointment
from ..filters import AppointmentFilter
from ..forms.appointment import AppointmentForm


class AppointmentListView(FilterView):
    model = Appointment
    template_name = 'appointments/appointment_list.html'
    context_object_name = 'appointments'
    filterset_class = AppointmentFilter
    paginate_by = 20

    def _has_user_filters(self):
        params = self.request.GET.copy()
        params.pop('page', None)
        return bool(params)

    def get_queryset(self):
        queryset = Appointment.objects.select_related('patient')

        # بدون هیچ فیلتری (ورود اولیه) فقط نوبت‌های امروز
        if not self._has_user_filters():
            queryset = queryset.filter(date=timezone.localdate())

        return queryset.order_by('-date', '-start_time')

    def _quick_dates(self):
        today = jdatetime.date.fromgregorian(date=timezone.localdate())
        fmt = '%Y-%m-%d'

        week_start = today - timedelta(days=today.weekday())  # شنبه
        week_end = week_start + timedelta(days=6)

        month_start = today.replace(day=1)
        next_month = (month_start + timedelta(days=32)).replace(day=1)
        month_end = next_month - timedelta(days=1)

        return {
            'today': today.strftime(fmt),
            'tomorrow': (today + timedelta(days=1)).strftime(fmt),
            'week_start': week_start.strftime(fmt),
            'week_end': week_end.strftime(fmt),
            'month_start': month_start.strftime(fmt),
            'month_end': month_end.strftime(fmt),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_form'] = AppointmentForm()
        context['showing_today_default'] = not self._has_user_filters()
        context['quick'] = self._quick_dates()
        return context