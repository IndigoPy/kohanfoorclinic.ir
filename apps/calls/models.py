from django.db import models
import hashlib

class CallLog(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    number = models.CharField(max_length=50)
    call_type = models.CharField(max_length=20)
    date = models.DateTimeField()
    duration = models.IntegerField(default=0)
    unique_hash = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    device_id = models.CharField(max_length=50, default='main-phone', db_index=True)
    def save(self, *args, **kwargs):
        if not self.unique_hash:
            raw = f"{self.number}|{self.date.isoformat()}|{self.call_type}|{self.duration}"
            self.unique_hash = hashlib.sha256(raw.encode()).hexdigest()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} - {self.call_type}"


class SmsLog(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    number = models.CharField(max_length=50)
    sms_type = models.CharField(max_length=20)
    body = models.TextField()
    date = models.DateTimeField()
    unique_hash = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    device_id = models.CharField(max_length=50, default='main-phone', db_index=True)
    
    def save(self, *args, **kwargs):
        if not self.unique_hash:
            # فقط ۱۰۰ کاراکتر اول متن را در هش استفاده می‌کنیم
            body_part = (self.body or "")[:100]
            raw = f"{self.number}|{self.date.isoformat()}|{self.sms_type}|{body_part}"
            self.unique_hash = hashlib.sha256(raw.encode()).hexdigest()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} - {self.sms_type}"
    
class PendingCommand(models.Model):
    COMMAND_CALL = 'call'
    COMMAND_SMS = 'sms'
    COMMAND_CHOICES = [
        (COMMAND_CALL, 'تماس'),
        (COMMAND_SMS, 'پیامک'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_DONE = 'done'
    STATUS_FAILED = 'failed'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'در انتظار'),
        (STATUS_DONE, 'انجام‌شده'),
        (STATUS_FAILED, 'ناموفق'),
        (STATUS_REJECTED, 'رد شده توسط کاربر'),
    ]

    command_type = models.CharField(max_length=10, choices=COMMAND_CHOICES)
    number = models.CharField(max_length=50)
    body = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    is_done = models.BooleanField(default=False)  # برای سازگاری با کد قبلی
    created_at = models.DateTimeField(auto_now_add=True)
    done_at = models.DateTimeField(blank=True, null=True)
    device_id = models.CharField(max_length=50, default='main-phone', db_index=True)

    def __str__(self):
        return f"{self.command_type} -> {self.number} ({self.status})"
    
class ContactTag(models.Model):
    TAG_CHOICES = [
        ('customer', 'مشتری'),
        ('personal', 'شخصی'),
        ('spam', 'اسپم'),
        ('work', 'کاری'),
        ('other', 'سایر'),
    ]
    number = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255, blank=True)
    tag = models.CharField(max_length=20, choices=TAG_CHOICES, default='other')
    note = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.number} - {self.tag}"