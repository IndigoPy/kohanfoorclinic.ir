# apps/workshop/selectors/orders.py

from django.db.models import Prefetch

from apps.reception.models import Order, OrderItem


def workshop_orders_queryset():
    workshop_items = OrderItem.objects.filter(
        send_to='workshop'
    ).select_related(
        'service',
        'variant',
    ).prefetch_related(
        'designs__design',
    ).order_by(
        'delivery_date',
        'created_at',
    )

    return Order.objects.filter(
        items__send_to='workshop',
    ).exclude(
        status='draft',
    ).select_related(
        'patient',
        'examination',
        'created_by',
        'ready_by',
    ).prefetch_related(
        Prefetch(
            'items',
            queryset=workshop_items,
            to_attr='workshop_items',
        ),
        'scans__technician',
    ).distinct()
