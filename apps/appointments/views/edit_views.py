from django.views.generic import UpdateView
from django.urls import reverse_lazy
from ..models import Appointment
from ..forms.appointment import AppointmentForm

class AppointmentUpdateView(UpdateView):
    model = Appointment
    form_class = AppointmentForm
    template_name = 'appointments/appointment_form.html' # استفاده از همان قالب ایجاد نوبت
    success_url = reverse_lazy('appointments:list') # پس از ویرایش موفق به لیست برگردد

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # ارسال یک متغیر به قالب تا متوجه شود در حالت ویرایش است
        context['is_update'] = True 
        return context
