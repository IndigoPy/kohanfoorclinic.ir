from django.db.models import Count, Prefetch, Q

from apps.reception.models import Order, OrderItem


def measurement_orders_queryset():
    items = (
        OrderItem.objects.exclude(status='cancelled')
        .select_related('service', 'specs_completed_by')
        .prefetch_related('designs__design', 'service__measurements', 'service__dynamic_fields')
        .order_by('id')
    )
    return (
        Order.objects
        .filter(status='draft', measurement_status__in=('requested', 'completed'))
        .select_related('patient', 'examination', 'measurement_requested_by')
        .prefetch_related(
            Prefetch('items', queryset=items, to_attr='measurement_items'),
            'examination__observations',
            'examination__observations_left',
            'examination__observations_right',
        )
        .annotate(
            total_specs=Count('items', filter=~Q(items__status='cancelled'), distinct=True),
            pending_specs=Count(
                'items',
                filter=(Q(items__specs_status='pending') | Q(items__send_to_confirmed=False))
                       & ~Q(items__status='cancelled'),
                distinct=True,
            ),
        )
    )