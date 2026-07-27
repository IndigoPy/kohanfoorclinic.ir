# apps/workshop/services/workflow.py

from django.db import transaction
from django.utils import timezone

from apps.reception.models import OrderItem
from apps.workshop.constants import (
    ITEM_STATUS_AWAITING_SUPPLIER,
    ITEM_STATUS_DELIVERED,
    ITEM_STATUS_MANUFACTURING,
    ITEM_STATUS_PENDING_SUPPLIER_REGISTRATION,
    ITEM_STATUS_QC_APPROVED,
    ITEM_STATUS_QC_PENDING,
    ITEM_STATUS_READY,
    ITEM_STATUS_READY_FOR_FITTING,
    ITEM_STATUS_RECEIVED_FROM_SUPPLIER,
    ITEM_STATUS_TRANSITIONS,
    ITEM_STATUS_WORKSHOP_QUEUE,
    LOCKED_ORDER_STATUSES,
    SEND_TO_MANUFACTURER,
    SEND_TO_WORKSHOP,
)
from apps.workshop.exceptions import (
    InvalidItemTransitionError,
    InvalidWorkshopActionError,
    LockedOrderError,
)
from apps.workshop.services.order_sync import sync_order_status


class WorkshopWorkflowService:
    """
    Central service for changing OrderItem production status.

    Views should not change item.status directly. All workflow changes should
    pass through this service to keep validation, logging, and order sync
    consistent.
    """

    def __init__(self, user):
        self.user = user

    @transaction.atomic
    def transition_item(self, item, new_status, description="", force=False):
        item = self._lock_item(item)
        self._validate_parent_order(item)

        old_status = item.status

        if old_status == new_status:
            return item

        if not force:
            self._validate_transition(
                old_status=old_status,
                new_status=new_status,
            )

        self._validate_status_matches_route(
            item=item,
            new_status=new_status,
        )

        update_fields = ["status", "updated_at"]

        item.status = new_status

        if new_status == ITEM_STATUS_DELIVERED:
            item.delivered_at = timezone.localdate()
            item.delivered_by = self.user
            update_fields.extend(["delivered_at", "delivered_by"])

        elif old_status == ITEM_STATUS_DELIVERED and new_status != ITEM_STATUS_DELIVERED:
            item.delivered_at = None
            item.delivered_by = None
            update_fields.extend(["delivered_at", "delivered_by"])

        item.save(update_fields=update_fields)

        self._create_item_status_log(
            item=item,
            old_status=old_status,
            new_status=new_status,
            description=description,
        )

        sync_order_status(
            order=item.order,
            updated_by=self.user,
            create_log=True,
        )

        return item

    def send_to_workshop_queue(self, item, description=""):
        return self.transition_item(
            item=item,
            new_status=ITEM_STATUS_WORKSHOP_QUEUE,
            description=description,
        )

    def start_manufacturing(self, item, description=""):
        return self.transition_item(
            item=item,
            new_status=ITEM_STATUS_MANUFACTURING,
            description=description,
        )

    def register_supplier_order(self, item, description=""):
        return self.transition_item(
            item=item,
            new_status=ITEM_STATUS_PENDING_SUPPLIER_REGISTRATION,
            description=description,
        )

    def mark_sent_to_supplier(self, item, description=""):
        return self.transition_item(
            item=item,
            new_status=ITEM_STATUS_AWAITING_SUPPLIER,
            description=description,
        )
    
    def mark_received_from_supplier(self, item, description=""):
        return self.transition_item(
            item=item,
            new_status=ITEM_STATUS_RECEIVED_FROM_SUPPLIER,
            description=description,
        )

    def mark_ready_for_fitting(self, item, description=""):
        return self.transition_item(
            item=item,
            new_status=ITEM_STATUS_READY_FOR_FITTING,
            description=description,
        )

    def send_to_qc(self, item, description=""):
        return self.transition_item(
            item=item,
            new_status=ITEM_STATUS_QC_PENDING,
            description=description,
        )

    def approve_qc(self, item, description=""):
        return self.transition_item(
            item=item,
            new_status=ITEM_STATUS_QC_APPROVED,
            description=description,
        )

    def mark_ready(self, item, description=""):
        return self.transition_item(
            item=item,
            new_status=ITEM_STATUS_READY,
            description=description,
        )

    def deliver_item(self, item, description=""):
        return self.transition_item(
            item=item,
            new_status=ITEM_STATUS_DELIVERED,
            description=description,
        )

    def resume_manufacturing(self, item, description=""):
        return self.transition_item(
            item=item,
            new_status=ITEM_STATUS_MANUFACTURING,
            description=description,
        )
    
    def _lock_item(self, item):
        return (
            OrderItem.objects.select_for_update()
            .select_related("order")
            .get(pk=item.pk)
        )

    def _validate_parent_order(self, item):
        if item.order.status in LOCKED_ORDER_STATUSES:
            raise LockedOrderError(
                "امکان تغییر وضعیت آیتم برای سفارش قفل‌شده وجود ندارد."
            )

    def _validate_transition(self, old_status, new_status):
        allowed_statuses = ITEM_STATUS_TRANSITIONS.get(old_status, set())

        if new_status not in allowed_statuses:
            raise InvalidItemTransitionError(
                f"تغییر وضعیت از {old_status} به {new_status} مجاز نیست."
            )

    def _validate_status_matches_route(self, item, new_status):
        supplier_statuses = {
            ITEM_STATUS_PENDING_SUPPLIER_REGISTRATION,
            ITEM_STATUS_AWAITING_SUPPLIER,
            ITEM_STATUS_RECEIVED_FROM_SUPPLIER,
        }
        
        workshop_only_statuses = {
            ITEM_STATUS_WORKSHOP_QUEUE,
        }

        if new_status in supplier_statuses and item.send_to != SEND_TO_MANUFACTURER:
            raise InvalidWorkshopActionError(
                "این وضعیت فقط برای آیتم‌های ارسالی به تولیدکننده مجاز است."
            )

        if new_status in workshop_only_statuses and item.send_to != SEND_TO_WORKSHOP:
            raise InvalidWorkshopActionError(
                "این وضعیت فقط برای آیتم‌های کارگاهی مجاز است."
            )

    def _create_item_status_log(self, item, old_status, new_status, description):
        """
        Adapter for current WorkshopStatusLog.

        Keep this method as the only place that knows the current log model
        fields. Later we can replace it with WorkshopActivity.
        """

        try:
            from apps.workshop.models import WorkshopStatusLog
        except ImportError:
            return None

        action = getattr(
            WorkshopStatusLog,
            "ACTION_ITEM_STATUS_CHANGED",
            "item_status_changed",
        )

        log_data = {
            "order": item.order,
            "order_item": item,
            "item": item,
            "action": action,
            "created_by": self.user,
            "old_item_status": old_status,
            "new_item_status": new_status,
            "old_status": old_status,
            "new_status": new_status,
            "description": description or "وضعیت آیتم سفارش تغییر کرد.",
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
