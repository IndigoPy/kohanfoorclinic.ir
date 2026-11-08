from django.db import models
from .patient import TimeStampedModel, SoftDeleteModel


class Referrer(TimeStampedModel, SoftDeleteModel):
    CATEGORY_CHOICES = (
        ('doctor', 'پزشک'),
        ('physiotherapist', 'فیزیوتراپ'),
        ('orthopedist', 'ارتوپد'),
        ('shoe_store', 'فروشگاه کفش'),
        ('other', 'سایر'),
    )

    code = models.CharField('شناسه', max_length=20, unique=True, null=True, blank=True)
    full_name = models.CharField('نام و نام خانوادگی', max_length=200)
    category = models.CharField('نوع', max_length=20, choices=CATEGORY_CHOICES, default='doctor')
    phone = models.CharField('تلفن', max_length=20, blank=True)
    workplace = models.CharField('محل کار', max_length=200, blank=True)
    notes = models.TextField('توضیحات', blank=True)

    class Meta:
        verbose_name = 'معرف'
        verbose_name_plural = 'معرفین'
        ordering = ['full_name']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            self.code = f'R-{self.pk:04d}'
            Referrer.objects.filter(pk=self.pk).update(code=self.code)

    def __str__(self):
        return f'{self.full_name} ({self.code})'