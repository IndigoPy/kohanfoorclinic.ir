# apps/workshop/selectors/orders.py

from django.db.models import Prefetch

from apps.reception.models import Order, OrderItem
from apps.workshop.constants import RELEASED_ITEM_STATUSES


def workshop_orders_queryset():
    workshop_items = OrderItem.objects.filter(
        status__in=RELEASED_ITEM_STATUSES,
    ).select_related(
        'service',
        'variant',
    ).prefetch_related(
        'designs__design',
        'service__measurements', 'service__dynamic_fields', 'specs_completed_by'
    ).order_by('expected_delivery_date', 'created_at')

    return Order.objects.filter(
        items__status__in=RELEASED_ITEM_STATUSES,
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
        'service__measurements', 'service__dynamic_fields', 'specs_completed_by'
    ).distinct()
