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
    
    def get_queryset(self):
        queryset = Appointment.objects.all()
        
        # کپی کردن پارامترهای GET برای بررسی اینکه آیا فیلتری ارسال شده است یا خیر
        query_params = self.request.GET.copy()
        
        # حذف پارامتر page از بررسی تا در صورت صفحه‌بندی (ورود به صفحه دوم نوبت‌های امروز)، فیلتر امروز غیرفعال نشود
        query_params.pop('page', None)
        
        # اگر هیچ فیلتری توسط کاربر اعمال نشده است (بدو ورود)
        if not query_params:
            today = timezone.localdate()
            queryset = queryset.filter(date=today)
            
        return queryset.order_by('-date', '-start_time')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_form'] = AppointmentForm() 
        return context
