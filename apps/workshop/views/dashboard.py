# apps/workshop/views/dashboard.py

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.core.decorators import group_required
from apps.workshop.selectors.orders import workshop_orders_queryset
from apps.reception.models import Order


@login_required
@group_required('workshop')
def workshop_dashboard(request):
    active_orders = workshop_orders_queryset().exclude(
        status__in=['delivered', 'cancelled']
    )

    stats = {
        'confirmed': active_orders.filter(status='confirmed').count(),
        'manufacturing': active_orders.filter(status='manufacturing').count(),
        'ready': active_orders.filter(status='ready').count(),
        'urgent': active_orders.filter(priority='urgent').count(),
        'measurement': Order.objects.filter(
            status='draft', measurement_status='requested').count(),
    }

    latest_orders = active_orders.order_by(
        '-created_at'
    )[:12]

    context = {
        'stats': stats,
        'latest_orders': latest_orders,
    }

    return render(request, 'workshop/dashboard.html', context)
