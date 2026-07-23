# apps/workshop/views/orders.py

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import group_required
from apps.reception.models import Order, OrderItem
from apps.workshop.selectors.orders import workshop_orders_queryset


@login_required
@group_required('workshop')
def workshop_order_list(request):
    search_query = request.GET.get('q', '').strip()
    selected_status = request.GET.get('status', '').strip()
    selected_priority = request.GET.get('priority', '').strip()

    orders = workshop_orders_queryset().exclude(
        status='cancelled'
    )

    valid_statuses = {
        value for value, _ in Order.STATUS_CHOICES
    }

    valid_priorities = {
        value for value, _ in Order.PRIORITY_CHOICES
    }

    if selected_status in valid_statuses:
        orders = orders.filter(status=selected_status)

    if selected_priority in valid_priorities:
        orders = orders.filter(priority=selected_priority)

    if search_query:
        search_filter = (
            Q(patient__first_name__icontains=search_query) |
            Q(patient__last_name__icontains=search_query) |
            Q(patient__case_number__icontains=search_query) |
            Q(patient__phone__icontains=search_query) |
            Q(items__service__name__icontains=search_query)
        )

        if search_query.isdigit():
            search_filter |= Q(id=int(search_query))

        orders = orders.filter(search_filter).distinct()

    priority_order = {
        'urgent': 0,
        'fast': 1,
        'normal': 2,
    }

    orders = list(orders)

    orders.sort(
        key=lambda order: (
            priority_order.get(order.priority, 3),
            -order.id,
        )
    )

    paginator = Paginator(orders, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'orders': page_obj,
        'search_query': search_query,
        'selected_status': selected_status,
        'selected_priority': selected_priority,
        'status_choices': Order.STATUS_CHOICES,
        'priority_choices': Order.PRIORITY_CHOICES,
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

    context = {
        'order': order,
        'patient': order.patient,
        'workshop_items': order.workshop_items,
        'item_status_choices': OrderItem.ITEM_STATUS_CHOICES,
        'workshop_logs': logs,
    }

    return render(request, 'workshop/order_detail.html', context)
