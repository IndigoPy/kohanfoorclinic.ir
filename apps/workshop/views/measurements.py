from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import group_required
from apps.reception.models import Order
from apps.workshop.selectors.measurements import measurement_orders_queryset
from apps.workshop.services.measurement import return_measurement
from apps.workshop.services.specs import get_spec_context


@login_required
@group_required('workshop')
def measurement_list(request):
    state = request.GET.get('state', 'requested')
    if state not in ('requested', 'completed'):
        state = 'requested'
    search = request.GET.get('q', '').strip()

    orders = measurement_orders_queryset().filter(measurement_status=state)
    if search:
        orders = orders.filter(
            Q(patient__first_name__icontains=search) |
            Q(patient__last_name__icontains=search) |
            Q(patient__case_number__icontains=search) |
            Q(patient__phone__icontains=search) |
            Q(id__icontains=search)
        )
    orders = orders.order_by(
        'measurement_requested_at' if state == 'requested' else '-measurement_completed_at'
    )

    counts = {'requested': 0, 'completed': 0}
    for row in (Order.objects.filter(status='draft', measurement_status__in=counts)
                .values('measurement_status').annotate(c=Count('id'))):
        counts[row['measurement_status']] = row['c']

    page_obj = Paginator(orders, 20).get_page(request.GET.get('page'))

    return render(request, 'workshop/measurement_list.html', {
        'orders': page_obj,
        'state': state,
        'search': search,
        'counts': counts,
    })


@login_required
@group_required('workshop')
def measurement_detail(request, order_id):
    order = measurement_orders_queryset().filter(id=order_id).first()
    if order is None:
        messages.info(request, 'این پرونده در صف اندازه‌گیری نیست (برگشت خورده یا سفارش ثبت شده است).')
        return redirect('workshop:measurement-list')

    for item in order.measurement_items:
        item.spec = get_spec_context(item)

    logs = (order.workshop_logs
            .select_related('created_by', 'item', 'item__service')
            .order_by('-created_at')[:15])

    return render(request, 'workshop/measurement_detail.html', {
        'order': order,
        'patient': order.patient,
        'exam': order.examination,
        'items': order.measurement_items,
        'done_count': order.total_specs - order.pending_specs,
        'logs': logs,
    })


@login_required
@group_required('workshop')
@require_POST
def return_measurement_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    try:
        return_measurement(order=order, user=request.user, note=request.POST.get('note'))
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('workshop:measurement-detail', order_id=order.id)

    messages.success(request, 'پرونده همراه با یادداشت به پذیرش برگشت.')
    return redirect('workshop:measurement-list')