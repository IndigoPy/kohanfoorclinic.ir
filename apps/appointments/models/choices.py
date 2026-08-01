from django.db import models
from django.utils.translation import gettext_lazy as _

class AppointmentType(models.TextChoices):
    NEW = 'new', _('بیمار جدید')
    DELIVERY = 'delivery', _('بیمار تحویلی')
    FOLLOW_UP = 'follow_up', _('فالوآپ')
    CLINIC_CALL = 'clinic_call', _('فالوآپ (تماس از کلینیک)')
    CHECKUP = 'checkup', _('بررسی کار')

class AppointmentStatus(models.TextChoices):
    SCHEDULED = 'scheduled', _('رزرو شده')
    CONFIRMED = 'confirmed', _('تایید شده (یادآوری انجام شد)')
    WAITING = 'waiting', _('در انتظار')
    COMPLETED = 'completed', _('انجام شده')
    CANCELED = 'canceled', _('لغو شده')
    NO_SHOW = 'no_show', _('عدم حضور')

