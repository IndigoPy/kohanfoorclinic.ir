# apps/workshop/views/items.py

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect

from apps.core.decorators import group_required
from apps.reception.models import OrderItem
# from apps.workshop.exceptions import WorkshopError
from apps.workshop.services.workflow import WorkshopWorkflowService


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

    new_status = request.POST.get('status', '').strip()
    new_notes = request.POST.get('notes', '').strip()

    try:
        result = WorkshopWorkflowService.update_item_status(
            item=item,
            new_status=new_status,
            notes=new_notes,
            user=request.user,
        )

    except WorkshopError as exc:
        messages.error(request, str(exc))
        return redirect(
            'workshop:order-detail',
            order_id=item.order_id,
        )

    if result['changed']:
        messages.success(request, result['message'])
    else:
        messages.info(request, result['message'])

    return redirect(
        'workshop:order-detail',
        order_id=item.order_id,
    )


