import django_filters
from django import forms
from django.db.models import Q
from .models import Appointment
from .models.choices import AppointmentStatus, AppointmentType

class AppointmentFilter(django_filters.FilterSet):
    patient_name = django_filters.CharFilter(
        method='filter_by_name',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'نام یا نام خانوادگی...'
        })
    )
    
    start_date = django_filters.CharFilter(
        method='filter_start_date',
        widget=forms.TextInput(attrs={
            'class': 'form-control date-filter',
            'placeholder': 'انتخاب تاریخ',
            'autocomplete': 'off',
        })
    )

    end_date = django_filters.CharFilter(
        method='filter_end_date',
        widget=forms.TextInput(attrs={
            'class': 'form-control date-filter',
            'placeholder': 'انتخاب تاریخ',
            'autocomplete': 'off',
        })
    )
    
    # ===== تغییر به MultipleChoiceFilter =====
    status = django_filters.MultipleChoiceFilter(
        choices=AppointmentStatus.choices,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-select select2-multiple',
            'data-placeholder': 'انتخاب وضعیت‌ها...'
        })
    )

    appointment_type = django_filters.MultipleChoiceFilter(
        choices=AppointmentType.choices,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-select select2-multiple',
            'data-placeholder': 'انتخاب نوع‌ها...'
        })
    )

    class Meta:
        model = Appointment
        fields = ['patient_name', 'start_date', 'end_date', 'status', 'appointment_type']

    def filter_by_name(self, queryset, name, value):
        if not value:
            return queryset
        query = Q()
        for term in value.split():
            query &= (
                Q(patient__first_name__icontains=term) |
                Q(patient__last_name__icontains=term) |
                Q(first_name__icontains=term) |
                Q(last_name__icontains=term)
            )
        return queryset.filter(query)

    def _clean_persian_date(self, date_str):
        if not date_str:
            return date_str
        persian_to_eng = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
        fixed_date = date_str.translate(persian_to_eng)
        return fixed_date.replace('/', '-')

    def filter_start_date(self, queryset, name, value):
        if value:
            clean_date = self._clean_persian_date(value)
            return queryset.filter(date__gte=clean_date)
        return queryset

    def filter_end_date(self, queryset, name, value):
        if value:
            clean_date = self._clean_persian_date(value)
            return queryset.filter(date__lte=clean_date)
        return queryset