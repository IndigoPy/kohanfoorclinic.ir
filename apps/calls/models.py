from django.db import models

class CallLog(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    number = models.CharField(max_length=50)
    call_type = models.CharField(max_length=20)  # incoming, outgoing, missed, rejected
    date = models.DateTimeField()
    duration = models.IntegerField(default=0)  # seconds
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.number} - {self.call_type}"


class SmsLog(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    number = models.CharField(max_length=50)
    sms_type = models.CharField(max_length=20)  # inbox, sent
    body = models.TextField()
    date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.number} - {self.sms_type}"