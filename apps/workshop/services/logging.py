# apps/workshop/services/logging.py

from apps.workshop.models import WorkshopStatusLog


def create_workshop_log(
    *,
    order,
    action,
    created_by=None,
    item=None,
    old_status=None,
    new_status=None,
    old_order_status=None,
    new_order_status=None,
    old_notes=None,
    new_notes=None,
    description=None,
):
    return WorkshopStatusLog.objects.create(
        patient=order.patient,
        order=order,
        item=item,
        action=action,
        created_by=created_by,
        old_status=old_status,
        new_status=new_status,
        old_order_status=old_order_status,
        new_order_status=new_order_status,
        old_notes=old_notes,
        new_notes=new_notes,
        description=description,
    )
