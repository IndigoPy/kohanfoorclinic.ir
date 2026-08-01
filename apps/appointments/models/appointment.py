from django.db import models
from django.conf import settings
from .choices import AppointmentType, AppointmentStatus
from ...reception.models import Patient
from django_jalali.db import models as jmodels

class Appointment(models.Model):
    # ارتباط با پرونده بیمار (در صورت وجود)
    # فرض بر این است که یک اپلیکیشن به نام patients و مدلی به نام Patient دارید
    patient = models.ForeignKey(
        Patient, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='appointments',
        verbose_name='پرونده بیمار'
    )

    # اطلاعات پایه (برای بیماران جدید که هنوز پرونده ندارند ضروری است)
    first_name = models.CharField(max_length=100, verbose_name='نام', blank=True)
    last_name = models.CharField(max_length=100, verbose_name='نام خانوادگی', blank=True)
    phone_number_1 = models.CharField(max_length=15, verbose_name='شماره تماس اصلی', blank=True)
    phone_number_2 = models.CharField(max_length=15, verbose_name='شماره تماس دوم', blank=True, null=True)
    referrer = models.CharField(max_length=255, verbose_name='معرف', blank=True, null=True)

    # اطلاعات زمان‌بندی
    date = jmodels.jDateField(verbose_name='تاریخ مراجعه')  # ← تغییر
    start_time = models.TimeField(verbose_name='ساعت شروع')
    end_time = models.TimeField(verbose_name='ساعت پایان', null=True, blank=True) # برای نمایش دقیق در تقویم

    # دسته‌بندی و وضعیت
    appointment_type = models.CharField(
        max_length=20, 
        choices=AppointmentType.choices, 
        default=AppointmentType.NEW,
        verbose_name='نوع نوبت'
    )
    
    status = models.CharField(
        max_length=20, 
        choices=AppointmentStatus.choices, 
        default='scheduled',
        verbose_name='وضعیت'
    )

    # اطلاعات متغیر (داینامیک) - JSONField
    # مواردی مثل: علت مراجعه، خدمات تحویلی، آیا پیامک آدرس رفت و ... در اینجا ذخیره می‌شوند
    extra_data = models.JSONField(default=dict, blank=True, verbose_name='اطلاعات تکمیلی')

    # متادیتا
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # اگر کلینیک چند درمانگر دارد (اختیاری)
    # provider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = 'نوبت'
        verbose_name_plural = 'نوبت‌ها'
        ordering = ['-date', '-start_time']

    def __str__(self):
        patient_name = f"{self.first_name} {self.last_name}".strip()
        if self.patient:
            patient_name = str(self.patient)
        return f"{patient_name} - {self.date} {self.start_time}"

    @property
    def is_new_patient(self):
        return self.patient is None

class AppointmentLog(models.Model):
    ACTION_CHOICES = (
        ('create', 'ایجاد'),
        ('update', 'ویرایش'),
        ('status_change', 'تغییر وضعیت'),
        ('delete', 'حذف'),
    )

    appointment = models.ForeignKey(
        'Appointment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs',
        verbose_name='نوبت'
    )
    appointment_snapshot_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        verbose_name='شناسه نوبت'
    )

    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        verbose_name='نوع عملیات'
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='کاربر'
    )

    field_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='نام فیلد'
    )

    old_value = models.TextField(
        null=True,
        blank=True,
        verbose_name='مقدار قبلی'
    )

    new_value = models.TextField(
        null=True,
        blank=True,
        verbose_name='مقدار جدید'
    )

    changes = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='جزئیات تغییرات'
    )

    description = models.TextField(
        null=True,
        blank=True,
        verbose_name='توضیحات'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='زمان ثبت'
    )

    class Meta:
        verbose_name = 'لاگ نوبت'
        verbose_name_plural = 'لاگ نوبت‌ها'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_action_display()} - {self.appointment_snapshot_id or self.appointment_id}"

    ACTION_CHOICES = (
        ('create', 'ایجاد'),
        ('update', 'ویرایش'),
        ('status_change', 'تغییر وضعیت'),
        ('delete', 'حذف'),
    )

    appointment = models.ForeignKey(
        'Appointment',
        on_delete=models.CASCADE,
        related_name='logs',
        verbose_name='نوبت'
    )

    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        verbose_name='نوع عملیات'
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='کاربر'
    )

    field_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='نام فیلد'
    )

    old_value = models.TextField(
        blank=True,
        null=True,
        verbose_name='مقدار قبلی'
    )

    new_value = models.TextField(
        blank=True,
        null=True,
        verbose_name='مقدار جدید'
    )

    changes = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='جزئیات تغییرات'
    )

    description = models.TextField(
        blank=True,
        null=True,
        verbose_name='توضیحات'
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='زمان ثبت')

    class Meta:
        verbose_name = 'لاگ نوبت'
        verbose_name_plural = 'لاگ‌های نوبت'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_action_display()} | نوبت #{self.appointment_id} | {self.created_at}"
