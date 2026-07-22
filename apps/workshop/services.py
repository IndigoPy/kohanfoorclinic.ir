from django.utils import timezone


from .logging import create_workshop_log
from .models import WorkshopStatusLog


def sync_order_status(order, updated_by=None, create_log=True):
    """
    وضعیت کلی سفارش را از روی وضعیت آیتم‌های ارسالی به کارگاه محاسبه می‌کند.
    """

    if order.status in ('draft', 'cancelled', 'delivered'):
        return order.status

    old_order_status = order.status

    workshop_items = list(
        order.items.filter(send_to='workshop')
        .values_list('status', flat=True)
    )

    if not workshop_items:
        return order.status

    active_statuses = [
        status for status in workshop_items
        if status != 'cancelled'
    ]

    if not active_statuses:
        return order.status

    new_order_status = order.status

    if all(status == 'ready' for status in active_statuses):
        new_order_status = 'ready'

    elif any(status == 'manufacturing' for status in active_statuses):
        new_order_status = 'manufacturing'

    elif any(status in ('pending', 'draft') for status in active_statuses):
        new_order_status = 'confirmed'

    if new_order_status != old_order_status:
        order.status = new_order_status

        update_fields = [
            'status',
            'ready_by',
            'updated_at',
        ]

        if new_order_status == 'ready':
            order.ready_by = updated_by
        else:
            order.ready_by = None

        order.save(update_fields=update_fields)

        if create_log:
            create_workshop_log(
                order=order,
                action=WorkshopStatusLog.ACTION_AUTO_ORDER_SYNC,
                created_by=updated_by,
                old_order_status=old_order_status,
                new_order_status=new_order_status,
                description='وضعیت کلی سفارش به‌صورت خودکار بر اساس وضعیت آیتم‌های کارگاهی به‌روزرسانی شد.',
            )

    return order.status
