import json
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.reception.models import Design, Order, OrderItem, OrderItemDesign, Services
from apps.workshop.models import WorkshopStatusLog
from apps.workshop.services.logging import create_workshop_log


def service_needs_specs(service):
    return service.measurements.exists() or service.dynamic_fields.exists()


def _safe_int(value, default=1):
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def _mark_requested(order, user, description):
    order.measurement_status = 'requested'
    order.measurement_requested_at = timezone.now()
    order.measurement_requested_by = user
    order.measurement_note = ''
    order.save(update_fields=[
        'measurement_status', 'measurement_requested_at',
        'measurement_requested_by', 'measurement_note', 'updated_at',
    ])
    create_workshop_log(
        order=order, created_by=user,
        action=WorkshopStatusLog.ACTION_MEASUREMENT_REQUEST,
        description=description,
    )


@transaction.atomic
def request_measurement(*, exam, user):
    """
    از روی تجویز معاینه یک سفارش پیش‌نویس می‌سازد و برای اندازه‌گیری به کارگاه می‌فرستد.
    خروجی: (order, created)  ← created=False یعنی قبلاً ارسال شده بود.
    """
    if (Order.objects.filter(examination=exam)
            .exclude(status__in=('draft', 'cancelled')).exists()):
        raise ValueError('برای این معاینه قبلاً سفارش ثبت شده است.')

    drafts = (Order.objects.select_for_update()
              .filter(examination=exam, status='draft').order_by('-id'))

    # قبلاً وارد فرایند اندازه‌گیری شده؟
    in_flow = drafts.exclude(measurement_status='none').first()
    if in_flow:
        if in_flow.measurement_status == 'returned':
            _mark_requested(in_flow, user, 'ارسال مجدد پرونده برای اندازه‌گیری')
            return in_flow, True
        return in_flow, False

    prescription = exam.prescription_services or {}
    if isinstance(prescription, str):
        try:
            prescription = json.loads(prescription)
        except ValueError:
            prescription = {}

    # پیش‌نویس ویزارد (بدون اندازه‌گیری) را دوباره استفاده می‌کنیم
    order = drafts.first() or Order.objects.create(
        patient=exam.patient, examination=exam, status='draft',
        payment_status='unpaid', created_by=user,
    )
    present = set(order.items.values_list('service_id', flat=True))

    for entry in prescription.values():
        if not isinstance(entry, dict):
            continue
        try:
            service = Services.objects.get(pk=int(entry.get('type_id')))
        except (TypeError, ValueError, Services.DoesNotExist):
            continue
        if service.id in present:
            continue

        quantity = _safe_int(entry.get('quantity'))
        price = Decimal('0') if service.has_size else (service.unit_price or Decimal('0'))
        item = OrderItem.objects.create(
            order=order, service=service, quantity=quantity,
            dynamic_fields=entry.get('dynamic_fields') or {},
            status='draft', price_at_order=price,
            specs_status='pending',
        )
        for side, key in ((None, 'designs'), ('left', 'designs_left'), ('right', 'designs_right')):
            for design in Design.objects.filter(id__in=entry.get(key) or []):
                OrderItemDesign.objects.create(
                    order=order, order_item=item, design=design, quantity=quantity,
                    price_at_order=design.price, cost_at_order=design.cost, side=side,
                )

    if not order.items.exists():
        raise ValueError('در این معاینه خدمتی تجویز نشده است.')
    

    order.recalculate_total()
    _mark_requested(order, user, 'ارسال پرونده از پذیرش برای اندازه‌گیری')
    return order, True


@transaction.atomic
def sync_measurement_status(order, user=None):
    """اگر مشخصات همه‌ی اقلام تایید شده باشد، سفارش به پذیرش برمی‌گردد."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.measurement_status != 'requested':
        return False
    
    items = list(order.items.exclude(status='cancelled'))
    if not items or any(i.specs_status != 'completed' or not i.send_to_confirmed for i in items):
        return False

    for item in items:                      # قیمت پیشنهادی از جدول سایز
        if item.price_at_order == 0:
            item.calculate_price()
            item.save(update_fields=['price_at_order', 'cost_at_order', 'updated_at'])

    order.measurement_status = 'completed'
    order.measurement_completed_at = timezone.now()
    order.save(update_fields=['measurement_status', 'measurement_completed_at', 'updated_at'])
    order.recalculate_total()
    create_workshop_log(
        order=order, created_by=user,
        action=WorkshopStatusLog.ACTION_MEASUREMENT_COMPLETE,
        description='اندازه‌گیری تکمیل و پرونده به پذیرش بازگشت.',
    )
    return True


@transaction.atomic
def return_measurement(*, order, user, note):
    """کارگاه پرونده را بدون تکمیل (با دلیل) به پذیرش برمی‌گرداند."""
    note = (note or '').strip()
    if not note:
        raise ValueError('برای برگرداندن پرونده باید دلیل را بنویسید.')

    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != 'draft' or order.measurement_status != 'requested':
        raise ValueError('این پرونده در صف اندازه‌گیری نیست.')

    order.measurement_status = 'returned'
    order.measurement_note = note
    order.save(update_fields=['measurement_status', 'measurement_note', 'updated_at'])
    create_workshop_log(
        order=order, created_by=user,
        action=WorkshopStatusLog.ACTION_MEASUREMENT_RETURN,
        description=note,
    )
    return order