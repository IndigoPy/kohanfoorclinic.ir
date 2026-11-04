from django.contrib import admin
from .models import CallLog, SmsLog

@admin.register(CallLog)
class CallLogAdmin(admin.ModelAdmin):
    list_display = ('name', 'number', 'call_type', 'date', 'duration', 'created_at')
    list_filter = ('call_type', 'date')
    search_fields = ('name', 'number')
    ordering = ('-date',)
    readonly_fields = ('created_at',)


@admin.register(SmsLog)
class SmsLogAdmin(admin.ModelAdmin):
    list_display = ('name', 'number', 'sms_type', 'date', 'short_body', 'created_at')
    list_filter = ('sms_type', 'date')
    search_fields = ('name', 'number', 'body')
    ordering = ('-date',)
    readonly_fields = ('created_at',)

    def short_body(self, obj):
        return obj.body[:60] + "..." if len(obj.body) > 60 else obj.body
    short_body.short_description = "متن پیامک"