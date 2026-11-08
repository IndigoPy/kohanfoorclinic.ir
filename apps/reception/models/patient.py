# reception/models/patients.py
from django.db import models
from django.db.models import Index
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db.models import Q

# =============================
# Base mixins
# =============================

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


# =============================
# Patient
# =============================

class Patient(TimeStampedModel, SoftDeleteModel):

    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
    )

    STAGE_CHOICES = (
        ('waiting_exam', 'Waiting Examination'),
        ('examined', 'Examined'),
        ('in_delivery', 'In Delivery'),
        ('waiting_qc', 'Waiting QC'),
        ('completed', 'Completed'),
    )

    CLASS_CHOICES = (
        ('good', 'خوش‌رفتار / عالی (سبز)'),
        ('average', 'متوسط (زرد)'),
        ('bad', 'سخت‌گیر / بدقلق (قرمز)'),
    )
    
    case_number = models.CharField(max_length=50, unique=True)

    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)

    national_id = models.CharField(
        max_length=20, blank=True, null=True, db_index=True)

    birth_date = models.DateField(blank=True, null=True)
    height = models.CharField(max_length=10, blank=True, null=True)
    weight = models.CharField(max_length=10, blank=True, null=True)

    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)

    phone = models.CharField(max_length=20, db_index=True)
    alternative_phone = models.CharField(max_length=20, blank=True, null=True)

    city = models.CharField(max_length=120, blank=True, null=True)
    neighborhood = models.CharField(max_length=120, blank=True, null=True)

    visit_reason = models.TextField(blank=True, null=True)
    
    foot_size = models.PositiveIntegerField(null=True, blank=True, verbose_name="سایز پا")
    reception_notes = models.TextField(null=True, blank=True, verbose_name="یادداشت پذیرش")
    referrer = models.CharField(max_length=255, null=True, blank=True, verbose_name="معرف")
    referrer_person = models.ForeignKey(
        'Referrer', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='referred_patients', verbose_name='معرف ثبت‌شده'
    )
    referrer_patient = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='referred_patients', verbose_name='معرف (بیمار)'
    )
    underlying_diseases = models.TextField(blank=True, null=True)

    orthotic_history = models.TextField(blank=True, null=True)

    admission_date = models.DateField(default=timezone.now)

    
    photo = models.ImageField(upload_to='patients/photos/', null=True, blank=True, verbose_name="عکس بیمار")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="ثبت کننده")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ثبت")
    
    stage = models.CharField(
        max_length=30,
        choices=STAGE_CHOICES,
        default='waiting_exam',
        db_index=True
    )

    attached_to = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='attached_patients'
    )

    patient_class = models.CharField(
        max_length=20,
        choices=CLASS_CHOICES,
        default='good',
        verbose_name="رده‌بندی رفتاری",
        db_index=True
    )
    
    class Meta:
        indexes = [
            Index(fields=["phone"]),
            Index(fields=["stage"]),
        ]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def get_age(self):
        if not self.birth_date:
            return None
        today = timezone.now().date()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (
                self.birth_date.month, self.birth_date.day)
        )

    def get_gender(self):
        if self.gender == 'male':
            return 'مرد'
        else:
            return 'زن'
        
    def get_related_patients(self):
        from_ids = PatientAttachment.objects.filter(
            from_patient=self
        ).values_list('to_patient_id', flat=True)

        to_ids = PatientAttachment.objects.filter(
            to_patient=self
        ).values_list('from_patient_id', flat=True)

        related_ids = set(from_ids) | set(to_ids)

        return Patient.objects.filter(id__in=related_ids, is_active=True)


    def __str__(self):
        return f"{self.full_name} ({self.case_number})"


# =============================
# Documents
# =============================

class Document(TimeStampedModel):

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="documents"
    )

    file = models.FileField(upload_to="documents/")

    description = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="آپلود کننده") # اضافه شد
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ آپلود")
    def __str__(self):
        return f"Document for {self.patient}"


# =============================
# Notification
# =============================

class Notification(TimeStampedModel):

    title = models.CharField(max_length=200)
    message = models.TextField()

    is_read = models.BooleanField(default=False)

    user_id = models.IntegerField()

    def __str__(self):
        return self.title


class PatientAttachment(models.Model):
    from_patient = models.ForeignKey(
        'Patient',
        on_delete=models.CASCADE,
        related_name='outgoing_attachments',
        verbose_name='پرونده مبدا'
    )

    to_patient = models.ForeignKey(
        'Patient',
        on_delete=models.CASCADE,
        related_name='incoming_attachments',
        verbose_name='پرونده مقصد'
    )

    note = models.TextField(
        blank=True,
        null=True,
        verbose_name='توضیح پیوست'
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='created_patient_attachments',
        verbose_name='ثبت‌کننده'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='زمان ثبت'
    )

    class Meta:
        verbose_name = 'پیوست پرونده بیمار'
        verbose_name_plural = 'پیوست‌های پرونده بیماران'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['from_patient', 'to_patient'],
                name='unique_patient_attachment_direction'
            ),
        ]

    def clean(self):
        if self.from_patient_id and self.to_patient_id:
            if self.from_patient_id == self.to_patient_id:
                raise ValidationError(
                    'یک پرونده را نمی‌توان به خودش پیوست کرد.'
                )

            reverse_exists = PatientAttachment.objects.filter(
                from_patient_id=self.to_patient_id,
                to_patient_id=self.from_patient_id,
            )

            if self.pk:
                reverse_exists = reverse_exists.exclude(pk=self.pk)

            if reverse_exists.exists():
                raise ValidationError(
                    'این دو پرونده قبلاً به هم پیوست شده‌اند.'
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.from_patient} ↔ {self.to_patient}'
    
    
    
class PatientInsuranceInfo(TimeStampedModel):
    PRIMARY_INSURANCE_CHOICES = (
        ('social_security', 'تأمین اجتماعی'),
        ('health_insurance', 'بیمه سلامت'),
        ('armed_forces', 'نیروهای مسلح'),
        ('imam_khomeini', 'کمیته امداد'),
        ('other', 'سایر'),
    )

    YES_NO_CHOICES = (
        ('yes', 'بله'),
        ('no', 'خیر'),
    )

    POLICY_HOLDER_RELATION_CHOICES = (
        ('self', 'خود بیمار'),
        ('spouse', 'همسر'),
        ('child', 'فرزند'),
        ('parent', 'والدین'),
        ('other', 'سایر'),
    )

    patient = models.OneToOneField(
        Patient,
        on_delete=models.CASCADE,
        related_name='insurance_info',
        verbose_name='بیمار'
    )

    # بیمه پایه
    primary_insurance_type = models.CharField(
        max_length=50,
        choices=PRIMARY_INSURANCE_CHOICES,
        blank=True,
        null=True,
        verbose_name='نوع بیمه پایه'
    )

    primary_insurance_provider = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='نام بیمه پایه / سازمان بیمه‌گر'
    )

    insurance_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        verbose_name='شماره بیمه / شماره دفترچه'
    )

    insurance_tracking_code = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='کد رهگیری / کد اعتبارسنجی بیمه'
    )

    primary_insurance_expiry_date = models.DateField(
        blank=True,
        null=True,
        verbose_name='تاریخ اعتبار بیمه پایه'
    )

    # بیمه تکمیلی
    has_supplementary_insurance = models.CharField(
        max_length=10,
        choices=YES_NO_CHOICES,
        blank=True,
        null=True,
        verbose_name='آیا بیمه تکمیلی دارد؟'
    )

    supplementary_insurance_provider = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='نام بیمه تکمیلی'
    )

    supplementary_insurance_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='شماره بیمه تکمیلی / شماره عضویت'
    )

    supplementary_coverage_limit = models.DecimalField(
        max_digits=14,
        decimal_places=0,
        blank=True,
        null=True,
        verbose_name='سقف پوشش بیمه تکمیلی'
    )

    insurance_deductible_percent = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        verbose_name='درصد فرانشیز'
    )

    # بیمه‌گذار
    policy_holder_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='نام بیمه‌گذار اصلی'
    )

    policy_holder_relation = models.CharField(
        max_length=50,
        choices=POLICY_HOLDER_RELATION_CHOICES,
        blank=True,
        null=True,
        verbose_name='نسبت بیمار با بیمه‌گذار'
    )

    insurance_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name='توضیحات بیمه'
    )

    class Meta:
        verbose_name = 'اطلاعات بیمه بیمار'
        verbose_name_plural = 'اطلاعات بیمه بیماران'
        indexes = [
            Index(fields=['insurance_number']),
            Index(fields=['supplementary_insurance_number']),
        ]

    def __str__(self):
        return f'اطلاعات بیمه {self.patient.full_name}'


class UnderlyingDisease(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="نام بیماری")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "بیماری زمینه‌ای"
        verbose_name_plural = "لیست بیماری‌های زمینه‌ای"

class OrthoticHistoryType(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="نوع ارتوتیک")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "سوابق ارتوتیک"
        verbose_name_plural = "لیست سوابق ارتوتیک"
