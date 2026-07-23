from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.reception.models import Order, OrderItem, Patient

class WorkshopStatusLog(models.Model):
    ACTION_STATUS_CHANGE = 'status_change'
    ACTION_BULK_STATUS_CHANGE = 'bulk_status_change'
    ACTION_NOTE_UPDATE = 'note_update'
    ACTION_ITEM_NOTE_UPDATE = 'item_note_update'
    ACTION_AUTO_ORDER_SYNC = 'auto_order_sync'

    ACTION_CHOICES = [
        (ACTION_STATUS_CHANGE, 'تغییر وضعیت آیتم'),
        (ACTION_BULK_STATUS_CHANGE, 'تغییر گروهی وضعیت آیتم‌ها'),
        (ACTION_NOTE_UPDATE, 'ویرایش یادداشت کلی کارگاه'),
        (ACTION_ITEM_NOTE_UPDATE, 'ویرایش یادداشت آیتم'),
        (ACTION_AUTO_ORDER_SYNC, 'هماهنگ‌سازی خودکار وضعیت سفارش'),
    ]

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name='workshop_logs',
        verbose_name='بیمار',
    )

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='workshop_logs',
        verbose_name='سفارش',
    )

    item = models.ForeignKey(
        OrderItem,
        on_delete=models.CASCADE,
        related_name='workshop_logs',
        verbose_name='آیتم سفارش',
        null=True,
        blank=True,
    )

    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
        verbose_name='نوع عملیات',
    )

    old_status = models.CharField(
        max_length=50,
        verbose_name='وضعیت قبلی',
        null=True,
        blank=True,
    )

    new_status = models.CharField(
        max_length=50,
        verbose_name='وضعیت جدید',
        null=True,
        blank=True,
    )

    old_order_status = models.CharField(
        max_length=50,
        verbose_name='وضعیت قبلی سفارش',
        null=True,
        blank=True,
    )

    new_order_status = models.CharField(
        max_length=50,
        verbose_name='وضعیت جدید سفارش',
        null=True,
        blank=True,
    )

    old_notes = models.TextField(
        verbose_name='یادداشت قبلی',
        null=True,
        blank=True,
    )

    new_notes = models.TextField(
        verbose_name='یادداشت جدید',
        null=True,
        blank=True,
    )

    description = models.TextField(
        verbose_name='توضیحات',
        null=True,
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='workshop_status_logs',
        verbose_name='ثبت‌کننده',
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='زمان ثبت',
    )

    class Meta:
        verbose_name = 'لاگ کارگاه'
        verbose_name_plural = 'لاگ‌های کارگاه'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient', '-created_at']),
            models.Index(fields=['order', '-created_at']),
            models.Index(fields=['item', '-created_at']),
            models.Index(fields=['action', '-created_at']),
        ]

    def __str__(self):
        return f'{self.get_action_display()} - سفارش #{self.order_id}'
