from django import forms
from ..models import Appointment
from ...reception.models import Patient 
import logging
from django_jalali.forms import jDateField
from django.urls import reverse
from ...reception.utils import resolve_referrer, referrer_initial

logger = logging.getLogger(__name__)

SERVICE_CHOICES = [
    ('insole', 'کفی طبی'),
    ('shoe', 'کفش طبی'),
    ('brace', 'بریس'),
    ('scan', 'اسکن کف پا'),
    ('diabetic', 'ویزیت پای دیابتی'),
]

# توسعه اسکیما برای پشتیبانی از نوبت‌های درخواستی
EXTRA_FIELDS_SCHEMA = {
    'existing': {
        'patient': {'is_patient_fk': True, 'required': True, 'label': 'انتخاب پرونده بیمار'},
        'reason_for_visit': {'type': forms.CharField, 'required': False, 'label': 'علت مراجعه', 'widget': forms.Textarea(attrs={'rows': 2})},
    },
    'new': {
        'first_name': {'type': forms.CharField, 'required': True, 'label': 'نام'},
        'last_name': {'type': forms.CharField, 'required': True, 'label': 'نام خانوادگی'},
        'phone_number_1': {'type': forms.CharField, 'required': True, 'label': 'شماره تماس اصلی'},
        'phone_number_2': {'type': forms.CharField, 'required': False, 'label': 'شماره تماس دوم'},
        'referrer': {'is_referrer': True, 'required': False, 'label': 'معرف'},
    },
    'delivery': {
        'patient': {'is_patient_fk': True, 'required': True, 'label': 'انتخاب پرونده بیمار'},
        'provided_services': {
            'type': forms.MultipleChoiceField, 
            'required': False, 
            'label': 'خدمات قابل ارائه',
            'choices': SERVICE_CHOICES,
            'widget': forms.SelectMultiple(attrs={'class': 'form-select select2', 'data-placeholder': 'انتخاب خدمات...'})
        },
    },
    'follow_up': {
        'patient': {'is_patient_fk': True, 'required': True, 'label': 'انتخاب پرونده بیمار'},
    },
    'checkup': {
        'patient': {'is_patient_fk': True, 'required': True, 'label': 'انتخاب پرونده بیمار'},
    },
    'clinic_call': {
        'patient': {'is_patient_fk': True, 'required': True, 'label': 'انتخاب پرونده بیمار'},
    }
}

# ترجمه یک‌بار ساخته می‌شه و در همه جا استفاده می‌شه
_DIGIT_TRANS = str.maketrans(
    '۰۱۲۳۴۵۶۷۸۹' + '٠١٢٣٤٥٦٧٨٩',
    '0123456789'  * 2
)

class AppointmentForm(forms.ModelForm):
    
    date = jDateField(
        input_formats=['%Y-%m-%d', '%Y/%m/%d'],
        widget=forms.HiddenInput(attrs={'id': 'id_date'})
    )
    
    class Meta:
        model = Appointment
        fields = ['date', 'start_time', 'end_time', 'appointment_type']
        widgets = {
            'start_time': forms.TextInput(attrs={
                'class': 'form-control time-picker',
                'autocomplete': 'off',
            }),
            'appointment_type': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        # ترجمه اعداد فارسی تاریخ
        data = None
        if args and args[0]:
            data = args[0].copy() if hasattr(args[0], 'copy') else dict(args[0])
        elif 'data' in kwargs and kwargs['data']:
            data = kwargs['data'].copy() if hasattr(kwargs['data'], 'copy') else dict(kwargs['data'])

        if data is not None and 'date' in data:
            raw = str(data['date']).strip()
            if raw:
                data['date'] = raw.translate(_DIGIT_TRANS)
            if args and args[0]:
                args = (data,) + args[1:]
            else:
                kwargs['data'] = data

        super().__init__(*args, **kwargs)

        # تشخیص نوع نوبت
        appointment_type = None

        if self.is_bound:
            # حالت POST
            appointment_type = self.data.get('appointment_type')
        elif self.instance and self.instance.pk:
            # حالت ویرایش (GET با instance)
            appointment_type = self.instance.appointment_type
        else:
            appointment_type = (
                kwargs.get('initial', {}).get('appointment_type')
                or self.initial.get('appointment_type')
                or self.fields['appointment_type'].initial 
            )

        # تزریق فیلدهای داینامیک
        if appointment_type and appointment_type in EXTRA_FIELDS_SCHEMA:
            schema = EXTRA_FIELDS_SCHEMA[appointment_type]
            for field_name, field_config in schema.items():
                if field_config.get('is_patient_fk'):
                    self.fields[field_name] = forms.ModelChoiceField(
                        queryset=Patient.objects.all(),
                        required=field_config.get('required', True),
                        label=field_config.get('label', 'بیمار'),
                        widget=forms.Select(attrs={'class': 'form-select select2'})
                    )
                elif field_config.get('is_referrer'):
                    self.fields[field_name] = forms.CharField(
                        required=False,
                        label=field_config.get('label', 'معرف'),
                        widget=forms.Select(
                            choices=[('', '')],  # هر درخواست، ویجت تازه می‌سازد
                            attrs={
                                'class': 'form-select referrer-select',
                                'data-url': reverse('reception:search-referrers'),
                                'data-quick-url': reverse('reception:quick-create-referrer'),
                                'data-placeholder': 'جستجوی معرف یا بیمار...',
                            },
                        ),
                    )
                else:
                    widget = field_config.get(
                        'widget', 
                        forms.TextInput(attrs={'class': 'form-control'})
                    )
                    
                    if 'class' not in widget.attrs:
                        widget.attrs['class'] = 'form-control'
                    
                    # پارامترهای فیلد
                    field_kwargs = {
                        'required': field_config.get('required', False),
                        'label': field_config.get('label', field_name),
                        'widget': widget
                    }
                    
                    # پشتیبانی از choices برای فیلدهایی مثل MultipleChoiceField
                    if 'choices' in field_config:
                        field_kwargs['choices'] = field_config['choices']

                    self.fields[field_name] = field_config['type'](**field_kwargs)

        # مقداردهی فیلدهای داینامیک هنگام ویرایش
        if self.instance and self.instance.pk:
            
            # فیلد patient
            if 'patient' in self.fields and self.instance.patient:
                self.fields['patient'].initial = self.instance.patient.pk

            # بقیه فیلدها از extra_data
            extra = self.instance.extra_data or {}
            for field_name, value in extra.items():
                if field_name in self.fields:
                    self.fields[field_name].initial = value

            # فیلدهای native که مستقیم روی مدل هستند
            native_fields = {'first_name', 'last_name', 'phone_number_1', 'phone_number_2', 'referrer'}
            for field_name in native_fields:
                if field_name in self.fields:
                    self.fields[field_name].initial = getattr(self.instance, field_name, '') or ''
                    
        if self.instance and self.instance.pk and self.instance.date and not self.is_bound:
            self.initial['date'] = self.instance.date.strftime('%Y-%m-%d')
            
        if 'referrer' in self.fields:
            self._set_referrer_choice()
    @property
    def dynamic_field_names(self):
        """لیست نام فیلدهای داینامیک فعلی فرم"""
        base_fields = {'date', 'start_time', 'end_time', 'appointment_type', 'status'}
        return [name for name in self.fields if name not in base_fields]

    def save(self, commit=True):
        appointment = super().save(commit=False)
        extra_data_dict = {}

        native_model_fields = {
            'first_name', 'last_name', 'phone_number_1',
            'phone_number_2', 'referrer', 'patient'
        }

        # فقط فیلدهایی که در اسکمای فرم ثبت شده‌اند پردازش و ذخیره می‌شوند
        schema = EXTRA_FIELDS_SCHEMA.get(appointment.appointment_type, {})
        for field_name in schema.keys():
            if field_name in self.cleaned_data:
                value = self.cleaned_data[field_name]

                # اگر فیلد مدل باشد، روی خود کلاس تنظیم می‌شود
                if field_name in native_model_fields:
                    setattr(appointment, field_name, value)
                # در غیر این صورت به عنوان دیتای JSON در extra_data ذخیره می‌شود
                else:
                    extra_data_dict[field_name] = value
                    
            if field_name == 'referrer':
                    text, ref_patient, ref_person = resolve_referrer(value)
                    appointment.referrer = text or None
                    appointment.referrer_patient = ref_patient
                    appointment.referrer_person = ref_person
                    continue

        appointment.extra_data = extra_data_dict

        if commit:
            appointment.save()
        return appointment

    def clean_date(self):
        value = self.cleaned_data.get('date')
        return value

    def _set_referrer_choice(self):
        field = self.fields['referrer']
        choice = None

        if self.is_bound:
            raw = self.data.get('referrer', '')
            if raw:
                from ...reception.utils import referrer_initial_from_raw
                choice = referrer_initial_from_raw(raw)
        elif self.instance and self.instance.pk:
            choice = referrer_initial(self.instance)

        if choice:
            field.widget.choices = [('', ''), (choice['id'], choice['text'])]
            field.initial = choice['id']