from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import group_required
from apps.reception.models import Order, OrderItem

from .services import sync_order_status

from .logging import create_workshop_log
from .models import WorkshopStatusLog

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
    }

    latest_orders = active_orders.order_by(
        '-created_at'
    )[:12]

    context = {
        'stats': stats,
        'latest_orders': latest_orders,
    }

    return render(request, 'workshop/dashboard.html', context)



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

    # سفارش فوری و اورژانسی بالاتر نمایش داده می‌شود.
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


@login_required
@group_required('workshop')
@transaction.atomic
def update_item_status(request, item_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    item = get_object_or_404(
        OrderItem.objects.select_for_update().select_related(
            'order',
            'order__patient',
            'service',
        ),
        id=item_id,
        send_to='workshop',
    )

    order = Order.objects.select_for_update().get(id=item.order_id)

    if order.status in ('draft', 'cancelled', 'delivered'):
        messages.error(
            request,
            'امکان تغییر این سفارش در وضعیت فعلی وجود ندارد.'
        )
        return redirect(
            'workshop:order-detail',
            order_id=order.id,
        )

    new_status = request.POST.get('status', '').strip()
    new_notes = request.POST.get('notes', '').strip()

    valid_statuses = {
        value for value, _ in OrderItem.ITEM_STATUS_CHOICES
    }

    if new_status not in valid_statuses:
        messages.error(request, 'وضعیت انتخاب‌شده معتبر نیست.')
        return redirect(
            'workshop:order-detail',
            order_id=order.id,
        )

    old_status = item.status
    old_notes = item.notes or ''

    status_changed = old_status != new_status
    notes_changed = old_notes != new_notes

    if not status_changed and not notes_changed:
        messages.info(
            request,
            'تغییری برای ذخیره وجود ندارد.'
        )
        return redirect(
            'workshop:order-detail',
            order_id=order.id,
        )

    item.status = new_status
    item.notes = new_notes

    item.save(
        update_fields=[
            'status',
            'notes',
            'updated_at',
        ]
    )

    if status_changed:
        create_workshop_log(
            order=order,
            item=item,
            action=WorkshopStatusLog.ACTION_STATUS_CHANGE,
            created_by=request.user,
            old_status=old_status,
            new_status=new_status,
            old_notes=old_notes,
            new_notes=new_notes,
            description=f'وضعیت آیتم «{item.service}» تغییر کرد.',
        )

    elif notes_changed:
        create_workshop_log(
            order=order,
            item=item,
            action=WorkshopStatusLog.ACTION_ITEM_NOTE_UPDATE,
            created_by=request.user,
            old_notes=old_notes,
            new_notes=new_notes,
            description=f'یادداشت آیتم «{item.service}» تغییر کرد.',
        )

    sync_order_status(
        order=order,
        updated_by=request.user,
    )

    messages.success(
        request,
        f'اطلاعات «{item.service}» با موفقیت به‌روزرسانی شد.'
    )

    return redirect(
        'workshop:order-detail',
        order_id=order.id,
    )



@login_required
@group_required('workshop')
@transaction.atomic
def update_workshop_notes(request, order_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    order = get_object_or_404(
        Order.objects.select_for_update().select_related('patient'),
        id=order_id,
        items__send_to='workshop',
    )

    if order.status in ('draft', 'cancelled', 'delivered'):
        messages.error(
            request,
            'امکان ویرایش یادداشت این سفارش وجود ندارد.'
        )
        return redirect(
            'workshop:order-detail',
            order_id=order.id,
        )

    old_notes = order.workshop_notes or ''
    new_notes = request.POST.get(
        'workshop_notes',
        ''
    ).strip()

    if old_notes == new_notes:
        messages.info(
            request,
            'تغییری در یادداشت کارگاه ایجاد نشده است.'
        )
        return redirect(
            'workshop:order-detail',
            order_id=order.id,
        )

    order.workshop_notes = new_notes

    order.save(
        update_fields=[
            'workshop_notes',
            'updated_at',
        ]
    )

    create_workshop_log(
        order=order,
        action=WorkshopStatusLog.ACTION_NOTE_UPDATE,
        created_by=request.user,
        old_notes=old_notes,
        new_notes=new_notes,
        description='یادداشت کلی کارگاه ویرایش شد.',
    )

    messages.success(
        request,
        'یادداشت کارگاه با موفقیت ذخیره شد.'
    )

    return redirect(
        'workshop:order-detail',
        order_id=order.id,
    )



@login_required
@group_required('workshop')
@transaction.atomic
def update_all_items_status(request, order_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    order = get_object_or_404(
        Order.objects.select_for_update().select_related('patient'),
        id=order_id,
    )

    if order.status in ('draft', 'cancelled', 'delivered'):
        messages.error(
            request,
            'امکان تغییر این سفارش در وضعیت فعلی وجود ندارد.'
        )
        return redirect(
            'workshop:order-detail',
            order_id=order.id,
        )

    new_status = request.POST.get('status', '').strip()

    valid_statuses = {
        value for value, _ in OrderItem.ITEM_STATUS_CHOICES
    }

    if new_status not in valid_statuses:
        messages.error(request, 'وضعیت انتخاب‌شده معتبر نیست.')
        return redirect(
            'workshop:order-detail',
            order_id=order.id,
        )

    workshop_items = list(
        order.items.select_for_update().filter(
            send_to='workshop'
        ).exclude(
            status='cancelled'
        )
    )

    if not workshop_items:
        messages.error(
            request,
            'این سفارش آیتم فعالی برای کارگاه ندارد.'
        )
        return redirect(
            'workshop:order-detail',
            order_id=order.id,
        )

    changed_count = 0

    for item in workshop_items:
        old_status = item.status

        if old_status == new_status:
            continue

        item.status = new_status
        item.save(
            update_fields=[
                'status',
                'updated_at',
            ]
        )

        changed_count += 1

        create_workshop_log(
            order=order,
            item=item,
            action=WorkshopStatusLog.ACTION_BULK_STATUS_CHANGE,
            created_by=request.user,
            old_status=old_status,
            new_status=new_status,
            description=f'وضعیت آیتم «{item.service}» در تغییر گروهی به‌روزرسانی شد.',
        )

    if changed_count == 0:
        messages.info(
            request,
            'همه آیتم‌ها از قبل در همین وضعیت بودند.'
        )
        return redirect(
            'workshop:order-detail',
            order_id=order.id,
        )

    sync_order_status(
        order=order,
        updated_by=request.user,
    )

    messages.success(
        request,
        f'وضعیت {changed_count} آیتم کارگاه با موفقیت به‌روزرسانی شد.'
    )

    return redirect(
        'workshop:order-detail',
        order_id=order.id,
    )



