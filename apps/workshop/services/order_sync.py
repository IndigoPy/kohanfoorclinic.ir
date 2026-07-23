# apps/workshop/services/order_sync.py

from django.db import transaction
from django.utils import timezone

from apps.reception.models import OrderItem
from apps.workshop.constants import (
    ITEM_STATUS_AWAITING_SUPPLIER,
    ITEM_STATUS_CANCELLED,
    ITEM_STATUS_DELIVERED,
    ITEM_STATUS_DRAFT,
    ITEM_STATUS_FITTING_COMPLETED,
    ITEM_STATUS_MANUFACTURING,
    ITEM_STATUS_NEEDS_REVISION,
    ITEM_STATUS_PENDING,
    ITEM_STATUS_PENDING_SUPPLIER_REGISTRATION,
    ITEM_STATUS_QC_APPROVED,
    ITEM_STATUS_QC_PENDING,
    ITEM_STATUS_READY,
    ITEM_STATUS_READY_FOR_FITTING,
    ITEM_STATUS_RECEIVED_FROM_SUPPLIER,
    ITEM_STATUS_WORKSHOP_QUEUE,
    LOCKED_ORDER_STATUSES,
    ORDER_STATUS_CONFIRMED,
    ORDER_STATUS_DELIVERED,
    ORDER_STATUS_MANUFACTURING,
    ORDER_STATUS_READY,
    SEND_TO_WORKSHOP,
)


def sync_order_status(order, updated_by=None, create_log=True):
    """
    Sync parent order status based on workshop order items.

    OrderItem is the source of truth for production workflow.
    Order.status remains a summarized status for reception/dashboard.
    """

    if order.status in LOCKED_ORDER_STATUSES:
        return order.status

    old_order_status = order.status

    item_statuses = list(
        order.items.filter(send_to=SEND_TO_WORKSHOP)
        .values_list("status", flat=True)
    )

    if not item_statuses:
        return order.status

    active_statuses = [
        status for status in item_statuses
        if status != ITEM_STATUS_CANCELLED
    ]

    if not active_statuses:
        return order.status

    if all(status == ITEM_STATUS_DELIVERED for status in active_statuses):
        new_order_status = ORDER_STATUS_DELIVERED

    elif all(
        status in {
            ITEM_STATUS_READY,
            ITEM_STATUS_QC_APPROVED,
            ITEM_STATUS_DELIVERED,
        }
        for status in active_statuses
    ):
        new_order_status = ORDER_STATUS_READY

    elif any(
        status in {
            ITEM_STATUS_WORKSHOP_QUEUE,
            ITEM_STATUS_MANUFACTURING,
            ITEM_STATUS_READY_FOR_FITTING,
            ITEM_STATUS_FITTING_COMPLETED,
            ITEM_STATUS_QC_PENDING,
            ITEM_STATUS_NEEDS_REVISION,
            ITEM_STATUS_PENDING_SUPPLIER_REGISTRATION,
            ITEM_STATUS_AWAITING_SUPPLIER,
            ITEM_STATUS_RECEIVED_FROM_SUPPLIER,
        }
        for status in active_statuses
    ):
        new_order_status = ORDER_STATUS_MANUFACTURING

    elif any(
        status in {
            ITEM_STATUS_PENDING,
            ITEM_STATUS_DRAFT,
        }
        for status in active_statuses
    ):
        new_order_status = ORDER_STATUS_CONFIRMED

    else:
        new_order_status = order.status

    if new_order_status == old_order_status:
        return order.status

    update_fields = [
        "status",
        "ready_by",
        "delivered_at",
        "delivered_by",
        "updated_at",
    ]

    order.status = new_order_status

    if new_order_status == ORDER_STATUS_READY:
        order.ready_by = updated_by
        order.delivered_at = None
        order.delivered_by = None

    elif new_order_status == ORDER_STATUS_DELIVERED:
        order.delivered_at = timezone.localdate()
        order.delivered_by = updated_by

    else:
        order.ready_by = None
        order.delivered_at = None
        order.delivered_by = None

    with transaction.atomic():
        order.save(update_fields=update_fields)

        if create_log:
            create_order_sync_log(
                order=order,
                updated_by=updated_by,
                old_order_status=old_order_status,
                new_order_status=new_order_status,
            )

    return order.status


def create_order_sync_log(order, updated_by, old_order_status, new_order_status):
    """
    Adapter for current WorkshopStatusLog.

    If your current log model uses different field names, only change this
    function and keep workflow/order sync code untouched.
    """

    try:
        from apps.workshop.models import WorkshopStatusLog
    except ImportError:
        return None

    action = getattr(
        WorkshopStatusLog,
        "ACTION_AUTO_ORDER_SYNC",
        "auto_order_sync",
    )

    log_data = {
        "order": order,
        "action": action,
        "created_by": updated_by,
        "old_order_status": old_order_status,
        "new_order_status": new_order_status,
        "description": (
            "وضعیت کلی سفارش به صورت خودکار بر اساس وضعیت آیتم‌های "
            "کارگاهی به‌روزرسانی شد."
        ),
    }

    valid_fields = {
        field.name for field in WorkshopStatusLog._meta.get_fields()
        if hasattr(field, "name")
    }

    safe_log_data = {
        key: value for key, value in log_data.items()
        if key in valid_fields
    }

    if not safe_log_data:
        return None

    return WorkshopStatusLog.objects.create(**safe_log_data)
