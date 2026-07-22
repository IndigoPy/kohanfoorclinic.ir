from django.contrib import admin

from .models import WorkshopStatusLog


@admin.register(WorkshopStatusLog)
class WorkshopStatusLogAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'patient',
        'order',
        'item',
        'action',
        'old_status',
        'new_status',
        'created_by',
        'created_at',
    ]

    list_filter = [
        'action',
        'old_status',
        'new_status',
        'created_at',
    ]

    search_fields = [
        'patient__first_name',
        'patient__last_name',
        'patient__case_number',
        'order__id',
        'item__service__name',
        'description',
    ]

    readonly_fields = [
        'patient',
        'order',
        'item',
        'action',
        'old_status',
        'new_status',
        'old_order_status',
        'new_order_status',
        'old_notes',
        'new_notes',
        'description',
        'created_by',
        'created_at',
    ]

    ordering = [
        '-created_at',
    ]
