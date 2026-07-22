from .models import WorkshopStatusLog


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
    """
    ثبت لاگ تخصصی کارگاه.
    """

    patient = order.patient

    return WorkshopStatusLog.objects.create(
        patient=patient,
        order=order,
        item=item,
        action=action,
        old_status=old_status,
        new_status=new_status,
        old_order_status=old_order_status,
        new_order_status=new_order_status,
        old_notes=old_notes,
        new_notes=new_notes,
        description=description,
        created_by=created_by,
    )
