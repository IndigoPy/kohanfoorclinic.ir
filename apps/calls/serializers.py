from rest_framework import serializers
from .models import CallLog, SmsLog

class CallLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallLog
        fields = ['name', 'number', 'call_type', 'date', 'duration', 'device_id']


class SmsLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmsLog
        fields = ['name', 'number', 'sms_type', 'body', 'date', 'device_id']