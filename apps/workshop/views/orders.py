# apps/workshop/views/orders.py

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import group_required
from apps.reception.models import Order, OrderItem
from apps.workshop.selectors.orders import workshop_orders_queryset
from apps.workshop.selectors.actions import get_available_item_actions

from django.utils import timezone
from apps.workshop.constants import (
    ITEM_STATUS_PENDING_SUPPLIER_REGISTRATION,
    ITEM_STATUS_AWAITING_SUPPLIER,
    ITEM_STATUS_READY,
)

@login_required
@group_required('workshop')
def workshop_order_list(request):
    orders = workshop_orders_queryset()

    search = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    priority = request.GET.get('priority', '').strip()
    quick_filter = request.GET.get('quick', '').strip()

    if search:
        orders = orders.filter(
            Q(patient__first_name__icontains=search) |
            Q(patient__last_name__icontains=search) |
            Q(id__icontains=search)
        )

    if status:
        orders = orders.filter(status=status)

    if priority:
        orders = orders.filter(priority=priority)

    today = timezone.localdate()

    if quick_filter == 'today':
        orders = orders.filter(items__delivery_date=today).exclude(
            items__status__in=['delivered', 'cancelled']
        ).distinct()

    elif quick_filter == 'overdue':
        orders = orders.filter(items__delivery_date__lt=today).exclude(
            items__status__in=['delivered', 'cancelled']
        ).distinct()

    elif quick_filter == 'awaiting_supplier':
        orders = orders.filter(
            items__status__in=[
                ITEM_STATUS_PENDING_SUPPLIER_REGISTRATION,
                ITEM_STATUS_AWAITING_SUPPLIER,
            ]
        ).distinct()

    elif quick_filter == 'ready':
        orders = orders.filter(items__status=ITEM_STATUS_READY).distinct()

    context = {
        'orders': orders,
        'search': search,
        'status': status,
        'priority': priority,
        'quick_filter': quick_filter,
    }
    return render(request, 'workshop/order_list.html', context)


@login_required
@group_required('workshop')
def workshop_order_detail(request, order_id):
    order = get_object_or_404(
        workshop_orders_queryset(),
        id=order_id,
    )

    if order.status == 'draft':
        messages.error(
            request,
            'سفارش پیش‌نویس هنوز به کارگاه ارسال نشده است.'
        )
        return redirect('workshop:order-list')

    logs = order.workshop_logs.select_related(
        'created_by',
        'item',
        'item__service',
    ).order_by('-created_at')[:50]

    for item in order.workshop_items:
            item.available_actions = get_available_item_actions(item)
            
    patient_orders_count = Order.objects.filter(
        patient=order.patient
    ).exclude(status='draft').count()
        
    context = {
        'order': order,
        'patient': order.patient,
        'patient_orders_count': patient_orders_count,
        'workshop_items': order.workshop_items,
        'item_status_choices': OrderItem.ITEM_STATUS_CHOICES,
        'workshop_logs': logs,
    }

    return render(request, 'workshop/order_detail.html', context)
