from django.views.generic import CreateView, UpdateView
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.shortcuts import render, redirect
from ..models import Appointment
from ..forms.appointment import AppointmentForm
import logging
import jdatetime
from django.shortcuts import get_object_or_404
from django.views import View
import json
from django.views.generic import DetailView
from apps.calls.services import queue_sms_commands
import re

logger = logging.getLogger(__name__)


class AppointmentCreateView(CreateView):
    model = Appointment
    form_class = AppointmentForm
    template_name = 'appointments/appointment_form.html'
    success_url = reverse_lazy('appointments:list')

    def get_initial(self):
        initial = super().get_initial()
        app_type = self.request.GET.get('type')
        if app_type:
            initial['appointment_type'] = app_type

        date_param = self.request.GET.get('date')
        if date_param:
            initial['date'] = date_param
        return initial
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        date_param = self.request.GET.get('date')
        if date_param:
            context['jalali_date_value'] = date_param
        else:
            context['jalali_date_value'] = jdatetime.date.today().strftime('%Y-%m-%d')
        return context
    
    def get(self, request, *args, **kwargs):
        self.object = None
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, self.template_name, self.get_context_data())
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object._changed_by = self.request.user if self.request.user.is_authenticated else None
        self.object.save()
        form.save_m2m()

        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})

        return redirect(self.get_success_url())

    def form_invalid(self, form):
        logger.warning(f"Create form errors: {form.errors.as_json()}")
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(
                self.request, self.template_name,
                self.get_context_data(form=form), status=400
            )
        return super().form_invalid(form)


class AppointmentUpdateView(UpdateView):
    model = Appointment
    form_class = AppointmentForm
    template_name = 'appointments/appointment_form.html'
    success_url = reverse_lazy('appointments:list')

    _DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')

    def get_queryset(self):
        return Appointment.objects.select_related('patient')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_update'] = True

        form = context['form']
        if form.is_bound:
            # بعد از خطای اعتبارسنجی، مقدار ارسال‌شده نمایش داده شود
            raw = str(form.data.get('date', '')).strip()
            context['jalali_date_value'] = raw.translate(self._DIGITS)
        elif self.object.date:
            context['jalali_date_value'] = self.object.date.isoformat()
        else:
            context['jalali_date_value'] = ''
        return context

    def _is_ajax(self):
        return self.request.headers.get('x-requested-with') == 'XMLHttpRequest'

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object._changed_by = self.request.user if self.request.user.is_authenticated else None
        self.object.save()
        form.save_m2m()

        if self._is_ajax():
            return JsonResponse({'success': True, 'id': self.object.pk})
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        logger.warning(f"Update form errors: {form.errors.as_json()}")
        if self._is_ajax():
            return render(
                self.request, self.template_name,
                self.get_context_data(form=form), status=400
            )
        return super().form_invalid(form)

    
class AppointmentDeleteView(View):
    def post(self, request, pk, *args, **kwargs):

        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        if not is_ajax:
            return JsonResponse(
                {'success': False, 'message': 'درخواست باید از طریق AJAX ارسال شود.'},
                status=400
            )

        try:
            appointment = get_object_or_404(Appointment, pk=pk)
            appointment._changed_by = request.user if request.user.is_authenticated else None
            appointment.delete()
            return JsonResponse({'success': True, 'message': 'نوبت با موفقیت حذف شد.'})
        except Exception as e:
            # برای دیباگ
            print("Error during delete:", str(e))
            return JsonResponse(
                {'success': False, 'message': 'خطا در حذف نوبت.'},
                status=500
            )
    
class SendSMSView(View):
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'ابتدا وارد شوید.'}, status=401)

        appointment = get_object_or_404(Appointment.objects.select_related('patient'), pk=pk)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'ساختار داده‌های ارسالی نامعتبر است.'}, status=400)

        message_text = (data.get('message') or '').strip()
        phones = data.get('phones') or []

        if not message_text:
            return JsonResponse({'success': False, 'error': 'متن پیامک نمی‌تواند خالی باشد.'}, status=400)
        if not isinstance(phones, list) or not phones:
            return JsonResponse({'success': False, 'error': 'حداقل یک شماره تماس باید انتخاب شود.'}, status=400)

        # فقط شماره‌های متعلق به همین نوبت مجاز هستند (جلوگیری از ارسال به شماره دلخواه)
        allowed = {
            self._normalize(p)
            for p in (appointment.display_phone_1, appointment.display_phone_2)
            if p
        }
        valid_phones = [p for p in phones if self._normalize(p) in allowed]

        if not valid_phones:
            return JsonResponse({'success': False, 'error': 'شماره انتخاب‌شده متعلق به این نوبت نیست.'}, status=400)

        commands = queue_sms_commands(valid_phones, message_text)

        return JsonResponse({
            'success': True,
            'queued': len(commands),
            'message': f'{len(commands)} پیامک در صف ارسال قرار گرفت.',
        })

    @staticmethod
    def _normalize(number):
        digits = str(number).translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789'))
        return re.sub(r'\D', '', digits)

class AppointmentDetailView(DetailView):
    model = Appointment
    template_name = 'appointments/components/appointment_detail_modal.html'
    context_object_name = 'appointment'

    # لیست اکشن‌های تغییر وضعیت (برچسب کوتاه برای دکمه‌ها)
    STATUS_ACTIONS = [
        {'value': 'scheduled', 'label': 'رزرو شده',       'icon': 'fa-calendar-check',  'color': 'primary'},
        {'value': 'confirmed', 'label': 'تایید شده',      'icon': 'fa-circle-check',    'color': 'success'},
        {'value': 'waiting',   'label': 'حضور در کلینیک', 'icon': 'fa-user-clock',      'color': 'info'},
        {'value': 'completed', 'label': 'انجام شده',      'icon': 'fa-flag-checkered',  'color': 'secondary'},
        {'value': 'canceled',  'label': 'لغو شده',        'icon': 'fa-ban',             'color': 'danger'},
        {'value': 'no_show',   'label': 'عدم حضور',       'icon': 'fa-user-slash',      'color': 'warning'},
        {'value': 'rescheduled', 'label': 'جابه‌جا شده', 'icon': 'fa-right-left', 'color': 'dark'},
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        extra = self.object.extra_data if isinstance(self.object.extra_data, dict) else {}

        context['appointment_type_label'] = self.object.get_appointment_type_display()
        context['status_actions'] = self.STATUS_ACTIONS
        context['address_sms_sent'] = bool(extra.get('address_sms_sent'))
        context['reminder_sms_sent'] = bool(extra.get('reminder_sms_sent'))
        return context