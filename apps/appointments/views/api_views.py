from ..models import Appointment
from django.http import JsonResponse
from django.views import View
from django.utils.dateparse import parse_date
import json
from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from datetime import date
from django.shortcuts import render
from ..forms.appointment import AppointmentForm, EXTRA_FIELDS_SCHEMA
from django.shortcuts import get_object_or_404
import datetime
import jdatetime
from django.contrib.auth.decorators import login_required
import logging
from django.utils.encoding import force_str

class AppointmentCalendarAPIView(View):
    def get(self, request, *args, **kwargs):
        # تقویم معمولا تاریخ شروع و پایان ویوی فعلی خود را می فرستد
        start_date = request.GET.get('start')
        end_date = request.GET.get('end')

        queryset = Appointment.objects.all()

        if start_date:
            queryset = queryset.filter(date__gte=parse_date(start_date[:10]))
        if end_date:
            queryset = queryset.filter(date__lte=parse_date(end_date[:10]))

        events = []
        for app in queryset:
            # FullCalendar به فیلدهای title, start, end نیاز دارد
            # برای ترکیب تاریخ و ساعت:
            start_datetime = f"{app.date}T{app.start_time}"
            end_datetime = f"{app.date}T{app.end_time}" if app.end_time else None

            # تعیین رنگ بر اساس نوع یا وضعیت
            color = self.get_event_color(app.appointment_type)

            events.append({
                'id': app.id,
                'title': str(app),
                'start': start_datetime,
                'end': end_datetime,
                'color': color,
                'url': f"/appointments/{app.id}/detail/", # لینک به صفحه جزئیات نوبت
            })

        return JsonResponse(events, safe=False)

    def get_event_color(self, app_type):
        # یک دیکشنری ساده برای رنگ‌بندی تقویم بر اساس نوع نوبت
        colors = {
            'new': '#28a745',        # سبز
            'delivery': '#17a2b8',   # آبی روشن
            'follow_up': '#ffc107',  # زرد
            'clinic_call': '#fd7e14',# نارنجی
            'checkup': '#6c757d',    # خاکستری
        }
        return colors.get(app_type, '#007bff') # آبی پیش‌فرض


def calendar_events_api(request):
    # FullCalendar این دو پارامتر را خودش ارسال می‌کند
    start_date_str = request.GET.get('start')
    end_date_str = request.GET.get('end')

    appointments = Appointment.objects.all()

    # فیلتر کردن نوبت‌ها فقط برای ماهی که در حال نمایش است (جهت افزایش سرعت)
    if start_date_str and end_date_str:
        # برش دادن قسمت تاریخ از رشته ISO ارسالی (مثلا 2026-04-01T00:00:00Z)
        start_date = start_date_str.split('T')[0]
        end_date = end_date_str.split('T')[0]
        appointments = appointments.filter(date__range=[start_date, end_date])

    events = []
    for appt in appointments:
        # رنگ‌بندی داینامیک بر اساس نوع بیمار (Color Coding)
        color = '#6c757d'  # رنگ پیش‌فرض (خاکستری)
        if appt.appointment_type == 'new':
            color = '#28a745'  # سبز
        elif appt.appointment_type == 'delivery':
            color = '#17a2b8'  # فیروزه‌ای
        elif appt.appointment_type == 'follow_up':
            color = '#6f42c1'  # بنفش
        elif appt.appointment_type == 'check':
            color = '#fd7e14'  # نارنجی

        # ترکیب تاریخ و ساعت برای نقطه شروع و پایان در تقویم
        start_datetime = f"{appt.date.isoformat()}T{appt.start_time.strftime('%H:%M:%S')}" if appt.start_time else appt.date.isoformat()
        end_datetime = f"{appt.date.isoformat()}T{appt.end_time.strftime('%H:%M:%S')}" if appt.end_time else None

        events.append({
            'id': appt.id,
            'title': f"{appt.patient} ({appt.get_appointment_type_display()})",
            'start': start_datetime,
            'end': end_datetime,
            'color': color,
            'textColor': '#ffffff',
            # با کلیک روی نوبت در تقویم، می‌توانیم کاربر را به صفحه ویرایش بفرستیم
            # 'url': f"/appointments/edit/{appt.id}/"  # فعلاً کامنت شده تا بعداً ویوی آن را بسازیم
        })

    return JsonResponse(events, safe=False)


@require_http_methods(["POST"])
def update_event_time(request):
    try:
        data = json.loads(request.body)
        appointment_id = data.get('id')

        if not appointment_id:
            return JsonResponse({'error': 'شناسه نوبت ارسال نشده است'}, status=400)

        appointment = Appointment.objects.get(id=appointment_id)

        # حالت ۱: نمای ماهانه FullCalendar
        # فقط تاریخ تغییر می‌کند و ساعت قبلی حفظ می‌شود
        if 'date' in data and data.get('date'):
            # تاریخ ورودی از FullCalendar میلادی است: YYYY-MM-DD
            gregorian_date = datetime.date.fromisoformat(data['date'])

            # تبدیل تاریخ میلادی به جلالی برای jDateField
            jalali_date = jdatetime.date.fromgregorian(date=gregorian_date)

            appointment.date = jalali_date

        # حالت ۲: نمای روز/هفته
        # تاریخ و ساعت شروع/پایان تغییر می‌کند
        elif 'start' in data and data.get('start'):
            start_full = data['start']

            # نمونه ورودی مورد انتظار:
            # 2026-07-28T15:00:00
            start_date_part = start_full.split('T')[0]
            start_time_part = start_full.split('T')[1].split('.')[0][:8]

            gregorian_date = datetime.date.fromisoformat(start_date_part)
            jalali_date = jdatetime.date.fromgregorian(date=gregorian_date)

            appointment.date = jalali_date
            appointment.start_time = datetime.time.fromisoformat(start_time_part)

            if data.get('end'):
                end_full = data['end']
                end_time_part = end_full.split('T')[1].split('.')[0][:8]
                appointment.end_time = datetime.time.fromisoformat(end_time_part)
            else:
                appointment.end_time = None

        else:
            return JsonResponse({'error': 'داده معتبر برای تغییر زمان ارسال نشده است'}, status=400)

        appointment.save()

        return JsonResponse({
            'success': True,
            'id': appointment.id,
        })

    except Appointment.DoesNotExist:
        return JsonResponse({'error': 'نوبت پیدا نشد'}, status=404)

    except ValueError as e:
        return JsonResponse({'error': f'فرمت تاریخ یا ساعت نامعتبر است: {str(e)}'}, status=400)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)



def load_dynamic_fields(request):
    """
    این ویو نوع نوبت را از طریق AJAX دریافت کرده و فقط HTML فیلدهای مربوطه را برمی‌گرداند.
    """
    appointment_type = request.GET.get('type')
    
    # مقداردهی اولیه فرم با نوع نوبت انتخاب شده تا فیلدهای مربوطه در init ساخته شوند
    form = AppointmentForm(initial={'appointment_type': appointment_type})
    
    # استخراج فقط فیلدهای داینامیک برای ارسال به قالب
    schema = EXTRA_FIELDS_SCHEMA.get(appointment_type, {})
    dynamic_fields = [form[field_name] for field_name in schema.keys()]
    
    return render(request, 'appointments/components/_partial_dynamic_fields.html', {
        'dynamic_fields': dynamic_fields
    })


class ToggleSMSStatusView(View):
    def post(self, request, pk):
        appointment = get_object_or_404(Appointment, pk=pk)

        try:
            data = json.loads(request.body)
            sms_type = data.get('sms_type')
            state = data.get('state')

            allowed_sms_types = ['address_sms_sent', 'reminder_sms_sent']

            if sms_type not in allowed_sms_types:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid SMS type'
                }, status=400)

            if not isinstance(state, bool):
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid state value'
                }, status=400)

            if not isinstance(appointment.extra_data, dict):
                appointment.extra_data = {}

            appointment.extra_data[sms_type] = state
            appointment.save(update_fields=['extra_data'])

            return JsonResponse({
                'success': True,
                'sms_type': sms_type,
                'state': state
            }, status=200)

        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON'
            }, status=400)

        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)



logger = logging.getLogger(__name__)




@login_required
@require_POST
def update_appointment_status(request):
    NOTE_STATUSES = {'canceled', 'no_show', 'rescheduled'}
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse(
            {'success': False, 'error': 'داده ارسالی JSON معتبر نیست.'},
            status=400
        )

    appointment_id = payload.get('id')
    new_status = payload.get('status')
    note = (payload.get('note') or '').strip()[:500]
    
    if not appointment_id or not new_status:
        return JsonResponse(
            {'success': False, 'error': 'شناسه نوبت و وضعیت جدید الزامی است.'},
            status=400
        )

    valid_statuses = {
        str(value) for value, _label in Appointment._meta.get_field('status').choices
    }

    if new_status not in valid_statuses:
        return JsonResponse(
            {'success': False, 'error': 'وضعیت ارسال‌شده معتبر نیست.'},
            status=400
        )

    try:
        appointment = Appointment.objects.get(pk=appointment_id)
    except Appointment.DoesNotExist:
        return JsonResponse(
            {'success': False, 'error': 'نوبت موردنظر پیدا نشد.'},
            status=404
        )

    try:
        appointment._changed_by = request.user
        appointment.status = new_status
        # توضیحات فقط برای وضعیت‌های لغو، عدم حضور و جابه‌جایی نگه داشته می‌شود
        appointment.status_note = note if new_status in NOTE_STATUSES else ''
        appointment.save(update_fields=['status', 'status_note'])
    except Exception as error:
        logger.exception('Unexpected error while updating appointment status')
        return JsonResponse(
            {'success': False, 'error': f'خطای داخلی هنگام تغییر وضعیت نوبت: {error}'},
            status=500
        )

    return JsonResponse({
        'success': True,
        'id': appointment.pk,
        'status': appointment.status,
        'status_label': force_str(appointment.get_status_display()),
        'status_note': appointment.status_note,
    })
