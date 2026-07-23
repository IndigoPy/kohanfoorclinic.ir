# apps/workshop/views/notes.py

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect

from apps.core.decorators import group_required
from apps.reception.models import Order,OrderItem
from apps.workshop.models import WorkshopStatusLog
from apps.workshop.services.logging import create_workshop_log

from apps.workshop.views.actions import _get_next_url


# create_workshop_note_log


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
def update_item_notes(request, item_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    item = get_object_or_404(
        OrderItem.objects.select_related("order"),
        pk=item_id,
    )

    old_notes = item.notes or ""
    new_notes = request.POST.get("notes", "")

    if old_notes != new_notes:
        item.notes = new_notes
        item.save(update_fields=["notes", "updated_at"])

        # create_workshop_note_log(
        #     item=item,
        #     old_notes=old_notes,
        #     new_notes=new_notes,
        #     created_by=request.user,
        # )

    messages.success(request, "توضیحات محصول ذخیره شد.")
    return redirect(_get_next_url(request, item))
