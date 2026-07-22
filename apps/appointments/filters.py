import django_filters
from django import forms
from django.db.models import Q
from .models import Appointment
# ایمپورت AppointmentType اضافه شد
from .models.choices import AppointmentStatus, AppointmentType

class AppointmentFilter(django_filters.FilterSet):
    patient_name = django_filters.CharFilter(
        method='filter_by_name',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'نام یا نام خانوادگی...'})
    )
    
    start_date = django_filters.CharFilter(
        method='filter_start_date',
        widget=forms.TextInput(attrs={'class': 'form-control date-filter', 'placeholder': 'YYYY/MM/DD'})
    )
    
    end_date = django_filters.CharFilter(
        method='filter_end_date',
        widget=forms.TextInput(attrs={'class': 'form-control date-filter', 'placeholder': 'YYYY/MM/DD'})
    )
    
    status = django_filters.ChoiceFilter(
        choices=AppointmentStatus.choices,
        empty_label='همه وضعیت‌ها',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # فیلتر نوع نوبت اضافه شد
    appointment_type = django_filters.ChoiceFilter(
        choices=AppointmentType.choices,
        empty_label='همه نوع‌ها',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Appointment
        # فیلد appointment_type به لیست اضافه شد
        fields = ['patient_name', 'start_date', 'end_date', 'status', 'appointment_type']

    def filter_by_name(self, queryset, name, value):
        if not value:
            return queryset
            
        # ایجاد یک شئ Q خالی
        query = Q()
        
        # جدا کردن کلمات جستجو شده (مثلاً نام و نام خانوادگی)
        for term in value.split():
            # هر کلمه باید در یکی از فیلدهای زیر وجود داشته باشد
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
