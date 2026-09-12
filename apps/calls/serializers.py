from rest_framework import serializers
from .models import CallLog, SmsLog

class CallLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallLog
        fields = '__all__'


class SmsLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmsLog
        fields = '__all__'