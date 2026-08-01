from django.http import JsonResponse
from django.views import View
from ..models.appointment import Appointment
import datetime
from django.views.generic import TemplateView


# helper

def get_patient_name(patient):
    if not patient:
        return 'بیمار جدید'

    first_name = getattr(patient, 'first_name', '') or ''
    last_name = getattr(patient, 'last_name', '') or ''

    full_name = f'{first_name} {last_name}'.strip()

    if full_name:
        return full_name

    return str(patient)


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
                
            VISIT_TYPE_COLORS = {
                'new': '#10b981',          # ویزیت جدید
                'follow_up': '#3b82f6',           # ویزیت فالوآپ
                'clinic_call': '#0b3578',     # ویزیت فالوآپ تماسی
                'delivery': '#f59e0b',   # تحویل خدمات
                'checkup': '#f5d20b',      # بررسی خدمات
            }

            visit_type = getattr(appointment, 'appointment_type', None)
            event_color = VISIT_TYPE_COLORS.get(visit_type, '#10b981')

            patient_name = get_patient_name(appointment.patient)

            # ۳. افزودن به لیست
            events.append({
                'id': appointment.id,
                'title': patient_name,
                'start': start_datetime,
                'end': end_datetime,
                'backgroundColor': event_color,
                'borderColor': event_color,
                'textColor': '#ffffff',
                'extendedProps': {
                    'patient': str(appointment.patient),
                    'status': getattr(appointment, 'status', ''),
                    'statusLabel': appointment.get_status_display() if hasattr(appointment, 'get_status_display') else '',
                    'startTime': appointment.start_time.strftime('%H:%M') if appointment.start_time else '',
                    'endTime': appointment.end_time.strftime('%H:%M') if appointment.end_time else '',
                    'detailUrl': f'/appointments/{appointment.id}/',
                    'editUrl': f'/appointments/{appointment.id}/edit/',
                }
            })


        return JsonResponse(events, safe=False)


class CalendarTemplateView(TemplateView):
    template_name = 'appointments/calendar.html' # آدرس فایل HTML خود را اینجا بگذارید