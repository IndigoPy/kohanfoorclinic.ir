from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from apps.core.decorators import group_required
from apps.reception.models import OrderItem
from apps.workshop.constants import (
    LOCKED_ORDER_STATUSES, RELEASED_ITEM_STATUSES, TERMINAL_ITEM_STATUSES,
)
from apps.workshop.services.specs import save_item_specs
from apps.workshop.views.actions import _get_next_url
from apps.workshop.services.measurement import sync_measurement_status

ACTIVE_ITEM_STATUSES = RELEASED_ITEM_STATUSES - TERMINAL_ITEM_STATUSES


@login_required
@group_required('Workshop')
@require_POST
@transaction.atomic
def update_item_specs(request, item_id):
    item = get_object_or_404(
        OrderItem.objects.select_for_update(of=('self',)).select_related(
            'order', 'order__patient', 'service'),
        pk=item_id,
    )

    if not _can_edit_specs(item):
        messages.error(request, 'در وضعیت فعلی امکان ثبت مشخصات برای این محصول وجود ندارد.')
        return redirect(_get_next_url(request, item))

    complete = request.POST.get('action') == 'complete'
    try:
        changed = save_item_specs(item=item, post=request.POST, user=request.user, complete=complete)
        if complete and sync_measurement_status(item.order, user=request.user):
            messages.success(request, 'همهٔ مشخصات تکمیل شد؛ پرونده به پذیرش بازگشت.')
        elif complete:
            messages.success(request, 'مشخصات محصول تکمیل و تایید شد.')
        else:
            messages.info(request, 'تغییری در مشخصات ایجاد نشده است.')
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect(_get_next_url(request, item))


def _can_edit_specs(item):
    order = item.order
    if order.status == 'draft':      # فاز اندازه‌گیری قبل از ثبت نهایی
        return (order.measurement_status in ('requested', 'completed')
                and item.status in ('draft', 'pending'))
    return order.status not in LOCKED_ORDER_STATUSES and item.status in ACTIVE_ITEM_STATUSES