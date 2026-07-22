from django.http import JsonResponse
from django.views import View
from ..models.appointment import Appointment
import datetime
from django.views.generic import TemplateView

class CalendarApiView(View):
    def get(self, request, *args, **kwargs):
        # دریافت بازه زمانی از سمت FullCalendar (در صورت نیاز به فیلتر کردن)
        # start_str = request.GET.get('start')
        # end_str = request.GET.get('end')
        
        appointments = Appointment.objects.all()
        events = []
        for appointment in appointments:
            # ۱. تبدیل تاریخ شمسی به میلادی
            if appointment.date:
                gregorian_date = appointment.date.togregorian() # خروجی به شکل 2026-07-01
            else:
                continue # یا مدیریت حالت بدون تاریخ

            # ۲. ترکیب تاریخ میلادی با زمان
            start_datetime = f"{gregorian_date}T{appointment.start_time}" if appointment.start_time else str(gregorian_date)
            
            end_datetime = None
            if appointment.end_time:
                end_datetime = f"{gregorian_date}T{appointment.end_time}"

            # ۳. افزودن به لیست
            events.append({
                "id": appointment.id,
                "title": f"{appointment.patient.name} ({appointment.get_status_display()})" if appointment.patient else "بیمار جدید",
                "start": start_datetime, # حالا فرمت میلادی است: 2026-07-01T12:00:00
                "end": end_datetime,
                "color": "#28a745", # بر اساس لاجیک خودتان تنظیم کنید
                "textColor": "#ffffff"
            })

        return JsonResponse(events, safe=False)


class CalendarTemplateView(TemplateView):
    template_name = 'appointments/calendar.html' # آدرس فایل HTML خود را اینجا بگذارید