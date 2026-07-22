from django.views.generic import CreateView, UpdateView
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.shortcuts import render
from ..models import Appointment
from ..forms.appointment import AppointmentForm
import logging
import jdatetime
from django.shortcuts import get_object_or_404
from django.views import View
import json
from django.views.generic import DetailView

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
        self.object = form.save()
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return super().form_valid(form)

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

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        
        # موقت — فقط برای دیباگ
        if request.GET.get('debug') == '1':
            from django.http import HttpResponse
            return HttpResponse(
                f"date type: {type(self.object.date)}<br>"
                f"date value: {self.object.date}<br>"
                f"jalali_date_value: {context.get('jalali_date_value')}"
            )
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, self.template_name, context)
        return render(request, self.template_name, context)

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.warning(f"Update form errors: {form.errors.as_json()}")
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            context = self.get_context_data(form=form)
            return render(self.request, self.template_name, context, status=400)
        return super().form_invalid(form)
    
class AppointmentDeleteView(View):
    def post(self, request, pk, *args, **kwargs):
        # بررسی اینکه درخواست حتما از طریق AJAX ارسال شده باشد
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            appointment = get_object_or_404(Appointment, pk=pk)
            appointment.delete()
            return JsonResponse({'success': True, 'message': 'نوبت با موفقیت حذف شد.'})
        
        return JsonResponse({'success': False, 'message': 'درخواست نامعتبر است.'}, status=400)
    
class SendSMSView(View):
    def post(self, request, pk):
        try:
            # دریافت داده‌های JSON از بدنه درخواست
            data = json.loads(request.body)
            message_text = data.get('message', '').strip()
            phones = data.get('phones', [])

            # اعتبارسنجی اولیه
            if not message_text:
                return JsonResponse({'success': False, 'error': 'متن پیامک نمی‌تواند خالی باشد.'}, status=400)
            
            if not phones or not isinstance(phones, list):
                return JsonResponse({'success': False, 'error': 'حداقل یک شماره تماس باید انتخاب شود.'}, status=400)

            # TODO 1: در آینده اتصال به ماژول/اپلیکیشن 'messages' برای ثبت سوابق (History) در دیتابیس در اینجا انجام می‌شود
            
            # TODO 2: در آینده فراخوانی API پنل پیامکی (مانند کاوه نگار، ملی پیامک و ...) در اینجا انجام می‌شود
            # for phone in phones:
            #     send_sms_api(phone, message_text)

            # در حال حاضر فقط یک پاسخ موفقیت‌آمیز برمی‌گردانیم
            return JsonResponse({
                'success': True, 
                'message': 'درخواست ارسال پیامک با موفقیت پردازش شد.'
            })

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'ساختار داده‌های ارسالی نامعتبر است.'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'خطای سرور: {str(e)}'}, status=500)

class AppointmentDetailView(DetailView):
    model = Appointment
    template_name = 'appointments/components/appointment_detail_modal.html'
    context_object_name = 'appointment'

    def get_context_data(self,**kwargs):
        context = super().get_context_data(**kwargs)
        # می‌توانید متغیرهای اضافی برای ترجمه انواع نوبت‌ها به قالب پاس دهید
        type_labels = {
            'existing': 'بیمار فعلی',
            'new': 'بیمار جدید',
            'delivery': 'تحویل',
            'followup': 'پیگیری',
            'clinic_call': 'تماس کلینیک',
            'checkup': 'چکاپ'
        }
        context['appointment_type_label'] = type_labels.get(self.object.appointment_type, self.object.appointment_type)
        return context
            