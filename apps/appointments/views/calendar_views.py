from django.urls import reverse
from django.http import JsonResponse
from django.views import View
from ..models.appointment import Appointment
from django.views.generic import TemplateView


def get_patient_name(patient):
    if not patient:
        return 'بیمار جدید'

    first_name = getattr(patient, 'first_name', '') or ''
    last_name = getattr(patient, 'last_name', '') or ''
    full_name = f'{first_name} {last_name}'.strip()

    return full_name if full_name else str(patient)


class CalendarApiView(View):
    def get(self, request, *args, **kwargs):
        appointments = Appointment.objects.all()
        events = []

        for appointment in appointments:
            if not appointment.date:
                continue

            gregorian_date = appointment.date.togregorian()

            start_datetime = f"{gregorian_date}T{appointment.start_time}" if appointment.start_time else str(gregorian_date)
            end_datetime = f"{gregorian_date}T{appointment.end_time}" if appointment.end_time else None

            VISIT_TYPE_COLORS = {
                'new': '#10b981',
                'follow_up': '#3b82f6',
                'clinic_call': '#0b3578',
                'delivery': '#f59e0b',
                'checkup': '#f5d20b',
            }

            visit_type = getattr(appointment, 'appointment_type', None)
            event_color = VISIT_TYPE_COLORS.get(visit_type, '#10b981')
            patient_name = get_patient_name(appointment.patient)

            # ساخت آدرس‌های صحیح با reverse
            try:
                detail_url = reverse('appointments:detail', kwargs={'pk': appointment.pk})
            except Exception:
                detail_url = None

            try:
                edit_url = reverse('appointments:update', kwargs={'pk': appointment.pk})
            except Exception:
                edit_url = None

            events.append({
                'id': appointment.id,
                'title': patient_name,
                'start': start_datetime,
                'end': end_datetime,
                'backgroundColor': event_color,
                'borderColor': event_color,
                'textColor': '#ffffff',
                'extendedProps': {
                    'patient': patient_name,
                    'status': getattr(appointment, 'status', ''),
                    'statusLabel': appointment.get_status_display() if hasattr(appointment, 'get_status_display') else '',
                    'startTime': appointment.start_time.strftime('%H:%M') if appointment.start_time else '',
                    'endTime': appointment.end_time.strftime('%H:%M') if appointment.end_time else '',
                    'detailUrl': detail_url,
                    'editUrl': edit_url,
                }
            })

        return JsonResponse(events, safe=False)


class CalendarTemplateView(TemplateView):
    template_name = 'appointments/calendar.html'