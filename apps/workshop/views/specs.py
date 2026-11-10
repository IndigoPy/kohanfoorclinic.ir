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

    if item.order.status in LOCKED_ORDER_STATUSES or item.status not in ACTIVE_ITEM_STATUSES:
        messages.error(request, 'در وضعیت فعلی امکان ثبت مشخصات برای این محصول وجود ندارد.')
        return redirect(_get_next_url(request, item))

    complete = request.POST.get('action') == 'complete'
    try:
        changed = save_item_specs(item=item, post=request.POST, user=request.user, complete=complete)
        if complete:
            messages.success(request, 'مشخصات محصول تکمیل و تایید شد.')
        elif changed:
            messages.success(request, 'مشخصات ذخیره شد.')
        else:
            messages.info(request, 'تغییری در مشخصات ایجاد نشده است.')
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect(_get_next_url(request, item))