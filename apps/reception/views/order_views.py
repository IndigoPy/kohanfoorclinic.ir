# reception/views/order_views
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import *
from apps.core.decorators import group_required
from django.http import JsonResponse
from decimal import Decimal
import json
from django.db import transaction
from collections import defaultdict
from ..models.orders import OrderService
from django.views.decorators.http import require_POST
from decimal import Decimal, InvalidOperation
import jdatetime
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
import logging
from django.http import Http404
from ..utils import to_persian_date_str
from apps.workshop.services.specs import get_spec_context
from django.db import transaction
from django.http import JsonResponse
import json

logger = logging.getLogger(__name__)

def is_manager(user):
    """فقط سوپریوزر یا عضو گروه Manager اجازه ویرایش/حذف تراکنش دارد"""
    return user.is_superuser or user.groups.filter(name='Examiner').exists()

# =====================================================================
# ویزارد ثبت سفارش: توابع مشترک
# =====================================================================

LOCKED_FOR_FULL_EDIT = ('delivered', 'cancelled', 'manufacturing', 'ready')
EDITABLE_ITEM_STATUSES = ('draft', 'pending')


def _fmt_spec_rows(rows):
    out = []
    for r in rows:
        value = r['value']
        if r['type'] == 'checkbox':
            value = 'دارد' if value else 'ندارد'
        elif value in ('', None):
            continue
        out.append({'label': r['label'], 'value': str(value)})
    return out


def _specs_summary(item):
    """خلاصه‌ی فقط‌خواندنی مشخصات/اندازه‌های ثبت‌شده توسط کارگاه."""
    ctx = get_spec_context(item)
    return {
        'different': ctx['different'],
        'dynamic': _fmt_spec_rows(ctx['dynamic_fields']),
        'same': _fmt_spec_rows(ctx['same_fields']),
        'right': _fmt_spec_rows(ctx['right_fields']),
        'left': _fmt_spec_rows(ctx['left_fields']),
    }


def _item_payload(**kw):
    data = {
        'item_id': None, 'service_id': None, 'service_name': '',
        'quantity': 1, 'unit_price': 0, 'discount': 0,
        'send_to': 'manufacturer', 'priority': 'normal',
        'delivery_date': '', 'notes': '', 'status': 'pending',
        'locked': False, 'has_size': False, 'has_schema': False,
        'specs_status': 'pending', 'specs': None, 'suggested_price': None,
        'designs': [], 'source': 'manual',
        'send_to_confirmed': False,
    }
    data.update(kw)
    return data


def _items_from_order(order):
    items = (order.items
             .select_related('service')
             .prefetch_related('designs__design',
                               'service__measurements', 'service__dynamic_fields')
             .order_by('id'))
    payload = []
    for item in items:
        svc = item.service
        has_schema = bool(svc.measurements.all()) or bool(svc.dynamic_fields.all())
        suggested = item.suggested_size_price
        payload.append(_item_payload(
            item_id=item.id, service_id=svc.id, service_name=svc.name,
            quantity=item.quantity,
            unit_price=float(item.price_at_order), discount=float(item.discount),
            send_to=item.send_to, priority=item.priority,
            delivery_date=item.delivery_date or '', notes=item.notes,
            status=item.status,
            locked=item.status not in EDITABLE_ITEM_STATUSES,
            has_size=svc.has_size, has_schema=has_schema,
            specs_status=item.specs_status,
            specs=_specs_summary(item) if has_schema else None,
            suggested_price=float(suggested) if suggested is not None else None,
            send_to_confirmed=item.send_to_confirmed,
            
            designs=[{
                'design_id': d.design_id, 'name': d.design.name,
                'price': float(d.price_at_order), 'side': d.side or '',
            } for d in item.designs.all()],
            source='order',
        ))
    return payload


def _items_from_exam(exam):
    """سفارش جدید بدون اندازه‌گیری: اقلام از تجویز معاینه پیش‌پر می‌شوند."""
    data = exam.prescription_services or {}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError:
            data = {}

    payload = []
    for entry in data.values():
        if not isinstance(entry, dict):
            continue
        try:
            svc = Services.objects.prefetch_related(
                'measurements', 'dynamic_fields').get(pk=int(entry.get('type_id')))
        except (TypeError, ValueError, Services.DoesNotExist):
            continue

        designs = []
        for side, key in (('', 'designs'), ('left', 'designs_left'), ('right', 'designs_right')):
            for d in Design.objects.filter(id__in=entry.get(key) or []):
                designs.append({'design_id': d.id, 'name': d.name,
                                'price': float(d.price), 'side': side})
        try:
            quantity = max(1, int(entry.get('quantity') or 1))
        except (TypeError, ValueError):
            quantity = 1

        payload.append(_item_payload(
            service_id=svc.id, service_name=svc.name, quantity=quantity,
            unit_price=0 if svc.has_size else float(svc.unit_price or 0),
            status='pending', has_size=svc.has_size,
            has_schema=bool(svc.measurements.all()) or bool(svc.dynamic_fields.all()),
            designs=designs, source='exam',
        ))
    return payload


def _wizard_context(*, patient, exam=None, order=None):
    if order is not None:
        items = _items_from_order(order)
    elif exam is not None:
        items = _items_from_exam(exam)
    else:
        items = []

    services = (Services.objects.filter(is_active=True)
                .prefetch_related('measurements', 'dynamic_fields').order_by('name'))
    designs = (Design.objects.filter(is_active=True)
               .prefetch_related('services').order_by('priority', 'name'))

    today = to_persian_date_str(timezone.now())
    return {
        'patient': patient,
        'exam': exam,
        'order': order,
        'is_edit': order is not None and order.status != 'draft',
        'can_autosave': order is None or order.status == 'draft',
        'has_invoice': bool(order and OrderInvoice.objects.filter(order=order).exists()),
        'total_paid': order.total_paid if order else 0,
        'persian_order_date': to_persian_date_str(order.order_date) if order else today,
        'wizard_items': items,
        'services_data': [{
            'id': s.id, 'name': s.name, 'price': float(s.unit_price or 0),
            'has_size': s.has_size,
            'has_schema': bool(s.measurements.all()) or bool(s.dynamic_fields.all()),
        } for s in services],
        'designs_data': [{
            'id': d.id, 'name': d.name, 'price': float(d.price or 0),
            'service_ids': [s.id for s in d.services.all()],
        } for d in designs],
    }


def _resume_draft(patient, exam, user):
    return (Order.objects
            .filter(patient=patient, examination=exam, status='draft',
                    measurement_status='none', created_by=user)
            .order_by('-id').first())


def _json_error(message, status=400):
    return JsonResponse({'status': 'error', 'message': message}, status=status)


def _wizard_post(request, *, patient, exam, order=None):
    """
    ذخیره‌ی پیش‌نویس یا ثبت نهایی (همیشه AJAX).
    order: سفارش موجود در مسیر ویرایش؛ None یعنی ایجاد یا ادامه‌ی پیش‌نویس.
    """
    is_draft = request.POST.get('is_draft') == '1'
    raw = request.POST.get('order_data')
    if not raw:
        return _json_error('داده‌های سفارش دریافت نشد.')
    try:
        order_data = json.loads(raw)
    except json.JSONDecodeError:
        return _json_error('ساختار اطلاعات سفارش معتبر نیست.')
    if not isinstance(order_data, dict):
        return _json_error('ساختار اطلاعات سفارش معتبر نیست.')

    try:
        with transaction.atomic():
            target = order
            if target is None:
                requested_id = order_data.get('order_id')
                if requested_id:
                    target = (Order.objects.select_for_update()
                              .filter(id=requested_id, patient=patient, examination=exam)
                              .first())
                    if target is None:
                        return _json_error(
                            'پیش‌نویس موردنظر پیدا نشد یا متعلق به این پرونده نیست.', 404)
                    if target.status != 'draft':
                        raise ValueError(
                            'این سفارش قبلاً ثبت نهایی شده است؛ از «ویرایش کلی» استفاده کنید.')

            if (target is not None and target.status == 'draft'
                    and target.measurement_status == 'requested'):
                raise ValueError(
                    'پرونده در مرحله‌ی اندازه‌گیری کارگاه است و تا بازگشت آن قابل ثبت نیست.')

            order_data.update(
                order_id=target.id if target else None,
                patient=patient,
                examination=exam,
                created_by=(target.created_by if target and target.created_by else request.user),
            )
            saved = OrderService.create_or_update_from_wizard(
                order_data=order_data, is_draft=is_draft)
    except ValueError as exc:
        return _json_error(str(exc))
    except Http404:
        return _json_error('خدمت یا طراحی انتخاب‌شده معتبر نیست.', 404)
    except Exception:
        logger.exception('wizard order save failed')
        return _json_error('خطای غیرمنتظره در ذخیره‌ی سفارش. لطفاً دوباره تلاش کنید.', 500)

    return JsonResponse({'status': 'saved' if is_draft else 'success', 'order_id': saved.id})


# =====================================================================
# ویوهای ویزارد
# =====================================================================

@login_required
@group_required('Reception')
def create_order_from_exam(request, exam_id):
    exam = get_object_or_404(Examination.objects.select_related('patient'), id=exam_id)
    patient = exam.patient

    if request.method == 'POST':
        return _wizard_post(request, patient=patient, exam=exam)

    measured = (Order.objects.filter(examination=exam, status='draft')
                .exclude(measurement_status='none').order_by('-id').first())
    if measured:
        if measured.measurement_status == 'requested':
            messages.warning(
                request, 'این معاینه برای اندازه‌گیری به کارگاه ارسال شده و هنوز برنگشته است.')
            return redirect('reception:patient-detail', patient_id=patient.id)
        return redirect('reception:edit-order', order_id=measured.id)

    draft = None if request.GET.get('new') else _resume_draft(patient, exam, request.user)
    return render(request, 'reception/create_order_from_exam.html',
                  _wizard_context(patient=patient, exam=exam, order=draft))


@login_required
@group_required('Reception')
def create_direct_order(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)

    if request.method == 'POST':
        return _wizard_post(request, patient=patient, exam=None)

    draft = None if request.GET.get('new') else _resume_draft(patient, None, request.user)
    return render(request, 'reception/create_order_from_exam.html',
                  _wizard_context(patient=patient, exam=None, order=draft))


@login_required
@group_required('Reception')
def edit_order(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related('patient', 'examination'), id=order_id)

    if order.status in LOCKED_FOR_FULL_EDIT:
        messages.error(
            request,
            'این سفارش وارد مرحله ساخت یا تحویل شده و دیگر قابل ویرایش کامل نیست.')
        return redirect('reception:patient-detail', patient_id=order.patient_id)

    if order.status == 'draft' and order.measurement_status == 'requested':
        messages.warning(
            request,
            'این سفارش در مرحله اندازه‌گیری کارگاه است؛ بعد از بازگشت پرونده می‌توانید ادامه دهید.')
        return redirect('reception:patient-detail', patient_id=order.patient_id)

    if request.method == 'POST':
        return _wizard_post(request, patient=order.patient,
                            exam=order.examination, order=order)

    return render(request, 'reception/create_order_from_exam.html',
                  _wizard_context(patient=order.patient, exam=order.examination, order=order))
# def _json_for_script(data):
#     """JSON امن برای قرار گرفتن داخل <script>."""
#     return json.dumps(data, cls=DjangoJSONEncoder).replace('</', '<\\/')


# def _wizard_static_data():
#     services_data = {
#         sp.id: {
#             'name': sp.name,
#             'price': float(sp.unit_price or 0),
#             'has_size': bool(sp.has_size),
#         }
#         for sp in Services.objects.all()
#     }

#     designs_data = {
#         dp.id: {
#             'name': dp.name,
#             'price': float(dp.price or 0),
#             'priority': dp.priority,
#             'service_ids': [s.id for s in dp.services.all()],
#         }
#         for dp in Design.objects.prefetch_related('services')
#     }

#     dynamic_fields = defaultdict(list)
#     for df in ServiceDynamicField.objects.all():
#         dynamic_fields[df.service_id].append({
#             'name': df.name,
#             'label': df.label,
#             'field_type': df.field_type,
#             'choices': [c.strip() for c in (df.dropdown_options or '').split(',') if c.strip()],
#             'is_required': df.is_required,
#         })

#     measurement_schema = defaultdict(list)
#     for m in ServiceMeasurements.objects.all():
#         measurement_schema[str(m.service_id)].append({
#             'name': m.name,
#             'label': m.label,
#             'type': m.field_type,
#             'required': m.is_required,
#             'options': [o.strip() for o in (m.dropdown_options or '').split(',') if o.strip()],
#         })

#     return {
#         'services_data': _json_for_script(services_data),
#         'designs_data': _json_for_script(designs_data),
#         'dynamic_fields_schema': dict(dynamic_fields),
#         'measurement_schema': _json_for_script(measurement_schema),
#     }

# @group_required('Reception')
# @login_required
# def create_order_from_exam(request, exam_id):
#     exam = get_object_or_404(
#         Examination.objects.select_related('patient'),
#         id=exam_id
#     )
#     patient = exam.patient
#     if request.method == 'GET':
#         measured = (Order.objects
#                     .filter(examination=exam, status='draft')
#                     .exclude(measurement_status='none')
#                     .order_by('-id').first())
#         if measured:
#             if measured.measurement_status == 'requested':
#                 messages.warning(
#                     request,
#                     'این معاینه برای اندازه‌گیری به کارگاه ارسال شده و هنوز برنگشته است.')
#                 return redirect('reception:patient-detail', patient_id=patient.id)
#             return redirect('reception:edit-order', order_id=measured.id)
#     # ==================== داده‌های اولیه برای فرانت ====================
#     services_data = {
#         sp.id: {
#             'name': getattr(sp, 'name', getattr(sp, 'title', 'نامشخص')),
#             'price': float(getattr(sp, 'unit_price', 0) or 0)
#         }
#         for sp in Services.objects.all()
#     }

#     designs_data = {
#         dp.id: {
#             'name': getattr(dp, 'name', 'نامشخص'),
#             'price': float(getattr(dp, 'price', 0) or 0)
#         }
#         for dp in Design.objects.all()
#     }

#     dynamic_fields_dict = defaultdict(list)

#     for df in ServiceDynamicField.objects.all():
#         choices_list = [
#             c.strip()
#             for c in (df.dropdown_options or '').split(',')
#             if c.strip()
#         ]

#         dynamic_fields_dict[df.service_id].append({
#             'name': df.name,
#             'label': df.label,
#             'field_type': df.field_type,
#             'choices': choices_list,
#             'is_required': df.is_required
#         })

#     measurements = (
#         ServiceMeasurements.objects
#         .all()
#         .select_related('service')
#     )

#     measurement_schema = {}

#     for m in measurements:
#         srv_id = str(m.service.id)

#         if srv_id not in measurement_schema:
#             measurement_schema[srv_id] = []

#         options = [
#             opt.strip()
#             for opt in (m.dropdown_options or '').split(',')
#             if opt.strip()
#         ]

#         measurement_schema[srv_id].append({
#             'name': m.name,
#             'label': m.label,
#             'type': m.field_type,
#             'required': m.is_required,
#             'options': options
#         })

#     today_jalali = jdatetime.date.fromgregorian(
#         date=timezone.localdate()
#     )

#     current_persian_order_date = (
#         f"{today_jalali.year}/"
#         f"{today_jalali.month:02d}/"
#         f"{today_jalali.day:02d}"
#     )

#     context = {
#         'exam': exam,
#         'patient': patient,
#         'current_persian_order_date': current_persian_order_date,
#         'persian_order_date': current_persian_order_date,
#         **_wizard_static_data(),
#     }

#     # =========================== POST ===========================
#     if request.method == 'POST':
#         is_ajax = (
#             request.headers.get('X-Requested-With') ==
#             'XMLHttpRequest'
#         )

#         is_draft = request.POST.get('is_draft') == '1'

#         try:
#             order_data_json = request.POST.get('order_data')

#             if not order_data_json:
#                 return JsonResponse(
#                     {
#                         'status': 'error',
#                         'message': 'داده‌های سفارش دریافت نشد'
#                     },
#                     status=400
#                 )

#             order_data = json.loads(order_data_json)

#             requested_order_id = order_data.get('order_id')

#             with transaction.atomic():
#                 existing_order = None

#                 # -------------------------------------------------
#                 # اگر فرانت ID پیش‌نویس را فرستاده، همان را پیدا کن
#                 # -------------------------------------------------
#                 if requested_order_id:
#                     existing_order = (
#                         Order.objects
#                         .select_for_update()
#                         .filter(
#                             id=requested_order_id,
#                             patient=patient,
#                             examination=exam,
#                         )
#                         .first()
#                     )

#                     if existing_order is None:
#                         return JsonResponse(
#                             {
#                                 'status': 'error',
#                                 'message': (
#                                     'پیش‌نویس موردنظر پیدا نشد یا '
#                                     'به این بیمار و معاینه تعلق ندارد.'
#                                 )
#                             },
#                             status=404
#                         )

#                 # -------------------------------------------------
#                 # اگر ID ارسال نشده، Draft قبلی همین فرآیند را پیدا کن
#                 # -------------------------------------------------
#                 elif is_draft:
#                     existing_order = (
#                         Order.objects
#                         .select_for_update()
#                         .filter(
#                             patient=patient,
#                             examination=exam,
#                             created_by=request.user,
#                             status='draft',
#                         )
#                         .order_by('-id')
#                         .first()
#                     )

#                 # اگر Draft یا سفارش قبلی پیدا شد، ID آن را به Service بده
#                 if existing_order:
#                     order_data['order_id'] = existing_order.id
#                 else:
#                     order_data['order_id'] = None

#                 # اطلاعات حساس را از URL و View بگیر، نه از فرانت
#                 order_data['patient'] = patient
#                 order_data['examination'] = exam
#                 order_data['created_by'] = request.user

#                 order = OrderService.create_or_update_from_wizard(
#                     order_data=order_data,
#                     is_draft=is_draft
#                 )

#             if is_ajax:
#                 return JsonResponse({
#                     'status': 'saved' if is_draft else 'success',
#                     'order_id': order.id,
#                     'message': (
#                         f'{"پیش‌نویس" if is_draft else "سفارش"} '
#                         f'#{order.id} ذخیره شد.'
#                     )
#                 })

#             messages.success(
#                 request,
#                 f'سفارش #{order.id} ثبت شد.'
#             )

#             return redirect(
#                 'reception:patient-detail',
#                 patient_id=patient.id
#             )

#         except json.JSONDecodeError:
#             if is_ajax:
#                 return JsonResponse(
#                     {
#                         'status': 'error',
#                         'message': 'ساختار JSON سفارش معتبر نیست.'
#                     },
#                     status=400
#                 )

#             messages.error(
#                 request,
#                 'ساختار اطلاعات سفارش معتبر نیست.'
#             )

#             return redirect(
#                 'reception:patient-detail',
#                 patient_id=patient.id
#             )

#         except Exception as e:
#             import traceback
#             print(traceback.format_exc())

#             if is_ajax:
#                 return JsonResponse(
#                     {
#                         'status': 'error',
#                         'message': str(e)
#                     },
#                     status=400
#                 )

#             messages.error(request, f'خطا: {str(e)}')

#             return redirect(
#                 'reception:patient-detail',
#                 patient_id=patient.id
#             )

#     return render(
#         request,
#         'reception/create_order_from_exam.html',
#         context
#     )


def create_order():
    pass



@login_required
@group_required('Reception')
@require_POST
def delete_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    patient_id = order.patient_id

    if (order.status != 'draft'
            or order.measurement_status == 'requested'
            or order.payments.exists()
            or OrderInvoice.objects.filter(order=order).exists()):
        messages.error(
            request,
            'فقط سفارش پیش‌نویسِ بدون پرداخت، بدون فاکتور و خارج از صف اندازه‌گیری قابل حذف است.')
        return redirect('reception:patient-detail', patient_id=patient_id)

    order.delete()
    messages.success(request, f"سفارش شماره {order_id} با موفقیت حذف شد.")
    return redirect('reception:patient-detail', patient_id=patient_id)

# @group_required('Reception')
# @login_required
# def create_direct_order(request, patient_id):
#     """ثبت سفارش مستقیم (بدون معاینه) برای بیمار"""
#     patient = get_object_or_404(Patient, id=patient_id)
#     exam = None  # سفارش مستقیم - بدون معاینه

#     # ==================== داده‌های اولیه برای فرانت ====================
#     services_data = {
#         sp.id: {
#             'name': getattr(sp, 'name', getattr(sp, 'title', 'نامشخص')),
#             'price': float(getattr(sp, 'unit_price', 0) or 0)
#         }
#         for sp in Services.objects.all()
#     }

#     designs_data = {
#         dp.id: {
#             'name': getattr(dp, 'name', 'نامشخص'),
#             'price': float(getattr(dp, 'price', 0) or 0)
#         }
#         for dp in Design.objects.all()
#     }

#     dynamic_fields_dict = defaultdict(list)

#     for df in ServiceDynamicField.objects.all():
#         choices_list = [
#             c.strip()
#             for c in (df.dropdown_options or '').split(',')
#             if c.strip()
#         ]

#         dynamic_fields_dict[df.service_id].append({
#             'name': df.name,
#             'label': df.label,
#             'field_type': df.field_type,
#             'choices': choices_list,
#             'is_required': df.is_required
#         })

#     measurements = (
#         ServiceMeasurements.objects
#         .all()
#         .select_related('service')
#     )

#     measurement_schema = {}

#     for m in measurements:
#         srv_id = str(m.service.id)

#         if srv_id not in measurement_schema:
#             measurement_schema[srv_id] = []

#         options = [
#             opt.strip()
#             for opt in (m.dropdown_options or '').split(',')
#             if opt.strip()
#         ]

#         measurement_schema[srv_id].append({
#             'name': m.name,
#             'label': m.label,
#             'type': m.field_type,
#             'required': m.is_required,
#             'options': options
#         })

#     today_jalali = jdatetime.date.fromgregorian(
#         date=timezone.localdate()
#     )

#     current_persian_order_date = (
#         f"{today_jalali.year}/"
#         f"{today_jalali.month:02d}/"
#         f"{today_jalali.day:02d}"
#     )

#     context = {
#         'exam': None,
#         'patient': patient,
#         'current_persian_order_date': current_persian_order_date,
#         'persian_order_date': current_persian_order_date,
#         'is_edit': False,
#         **_wizard_static_data(),
#     }

#     # =========================== POST ===========================
#     if request.method == 'POST':
#         is_ajax = (
#             request.headers.get('X-Requested-With') ==
#             'XMLHttpRequest'
#         )

#         is_draft = request.POST.get('is_draft') == '1'

#         try:
#             order_data_json = request.POST.get('order_data')

#             if not order_data_json:
#                 return JsonResponse(
#                     {
#                         'status': 'error',
#                         'message': 'داده‌های سفارش دریافت نشد'
#                     },
#                     status=400
#                 )

#             order_data = json.loads(order_data_json)

#             requested_order_id = order_data.get('order_id')

#             with transaction.atomic():
#                 existing_order = None

#                 # -------------------------------------------------
#                 # اگر فرانت ID پیش‌نویس را فرستاده، همان را پیدا کن
#                 # -------------------------------------------------
#                 if requested_order_id:
#                     existing_order = (
#                         Order.objects
#                         .select_for_update()
#                         .filter(
#                             id=requested_order_id,
#                             patient=patient,
#                             examination__isnull=True,
#                         )
#                         .first()
#                     )

#                     if existing_order is None:
#                         return JsonResponse(
#                             {
#                                 'status': 'error',
#                                 'message': (
#                                     'پیش‌نویس موردنظر پیدا نشد یا '
#                                     'به این بیمار تعلق ندارد.'
#                                 )
#                             },
#                             status=404
#                         )

#                 # -------------------------------------------------
#                 # اگر ID ارسال نشده، Draft قبلی همین فرآیند را پیدا کن
#                 # -------------------------------------------------
#                 elif is_draft:
#                     existing_order = (
#                         Order.objects
#                         .select_for_update()
#                         .filter(
#                             patient=patient,
#                             examination__isnull=True,
#                             created_by=request.user,
#                             status='draft',
#                         )
#                         .order_by('-id')
#                         .first()
#                     )

#                 # اگر Draft یا سفارش قبلی پیدا شد، ID آن را به Service بده
#                 if existing_order:
#                     order_data['order_id'] = existing_order.id
#                 else:
#                     order_data['order_id'] = None

#                 # اطلاعات حساس را از URL و View بگیر، نه از فرانت
#                 order_data['patient'] = patient
#                 order_data['examination'] = None  # سفارش مستقیم
#                 order_data['created_by'] = request.user

#                 order = OrderService.create_or_update_from_wizard(
#                     order_data=order_data,
#                     is_draft=is_draft
#                 )

#             if is_ajax:
#                 return JsonResponse({
#                     'status': 'saved' if is_draft else 'success',
#                     'order_id': order.id,
#                     'message': (
#                         f'{"پیش‌نویس" if is_draft else "سفارش"} '
#                         f'#{order.id} ذخیره شد.'
#                     )
#                 })

#             messages.success(
#                 request,
#                 f'سفارش #{order.id} ثبت شد.'
#             )

#             return redirect(
#                 'reception:patient-detail',
#                 patient_id=patient.id
#             )

#         except json.JSONDecodeError:
#             if is_ajax:
#                 return JsonResponse(
#                     {
#                         'status': 'error',
#                         'message': 'ساختار JSON سفارش معتبر نیست.'
#                     },
#                     status=400
#                 )

#             messages.error(
#                 request,
#                 'ساختار اطلاعات سفارش معتبر نیست.'
#             )

#             return redirect(
#                 'reception:patient-detail',
#                 patient_id=patient.id
#             )

#         except Exception as e:
#             import traceback
#             print(traceback.format_exc())

#             if is_ajax:
#                 return JsonResponse(
#                     {
#                         'status': 'error',
#                         'message': str(e)
#                     },
#                     status=400
#                 )

#             messages.error(request, f'خطا: {str(e)}')

#             return redirect(
#                 'reception:patient-detail',
#                 patient_id=patient.id
#             )

#     return render(
#         request,
#         'reception/create_order_from_exam.html',
#         context
#     )
    
@require_POST
@login_required
def add_payment(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if order.status == 'draft':
        messages.error(request, 'سفارش پیش‌نویس هنوز ثبت نهایی نشده؛ پرداخت و فاکتور ممکن نیست.')
        return redirect('reception:patient-detail', patient_id=order.patient_id)
    try:
        amount = Decimal(request.POST.get('amount', '0'))
        if amount <= 0:
            raise ValueError('مبلغ پرداخت باید بزرگتر از صفر باشد')

        remaining = order.remaining_amount
        if amount > remaining:
            raise ValueError(
                f'مبلغ وارد شده ({amount:,.0f} تومان) از باقی‌مانده سفارش ({remaining:,.0f} تومان) بیشتر است'
            )

        account_id = request.POST.get('account')
        account = PaymentAccount.objects.filter(id=account_id).first() if account_id else None

        payment = Payment.objects.create(
            order=order,
            amount=amount,
            method=request.POST.get('method', 'cash'),
            account=account,
            reference_number=request.POST.get('reference_number', '').strip(),
            notes=request.POST.get('notes', '').strip(),
            received_by=request.user,
        )
        order.update_payment_status()
        messages.success(request, f"پرداخت به مبلغ {payment.formatted_amount} تومان ثبت شد.")

    except (ValueError, InvalidOperation, TypeError) as e:
        messages.error(request, f"خطا در ثبت پرداخت: {e}")

    return redirect('reception:patient-detail', patient_id=order.patient.id)


@require_POST
@login_required
def edit_payment(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    order = payment.order

    if not is_manager(request.user):
        messages.error(request, "شما اجازه ویرایش تراکنش‌های مالی را ندارید.")
        return redirect('reception:patient-detail', patient_id=order.patient.id)

    try:
        new_amount = Decimal(request.POST.get('amount', '0'))
        if new_amount <= 0:
            raise ValueError('مبلغ پرداخت باید بزرگتر از صفر باشد')

        other_total = order.payments.exclude(id=payment.id).aggregate(
            total=Sum('amount'))['total'] or Decimal('0')
        if other_total + new_amount > order.total_price:
            raise ValueError('مجموع پرداخت‌ها از مبلغ کل سفارش بیشتر می‌شود')

        account_id = request.POST.get('account')
        payment.amount = new_amount
        payment.method = request.POST.get('method', payment.method)
        payment.account = PaymentAccount.objects.filter(id=account_id).first() if account_id else None
        payment.reference_number = request.POST.get('reference_number', '').strip()
        payment.notes = request.POST.get('notes', '').strip()
        payment.edited_by = request.user
        payment.save()

        order.update_payment_status()
        messages.success(request, "تراکنش با موفقیت ویرایش شد.")

    except (ValueError, InvalidOperation, TypeError) as e:
        messages.error(request, f"خطا در ویرایش پرداخت: {e}")

    return redirect('reception:patient-detail', patient_id=order.patient.id)


@require_POST
@login_required
def delete_payment(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    order = payment.order
    patient_id = order.patient.id

    if not is_manager(request.user):
        messages.error(request, "شما اجازه حذف تراکنش‌های مالی را ندارید.")
        return redirect('reception:patient-detail', patient_id=patient_id)

    payment.delete()
    order.update_payment_status()
    messages.success(request, "پرداخت حذف شد.")
    return redirect('reception:patient-detail', patient_id=patient_id)



@require_POST
@login_required
def issue_order_invoice(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related('patient'),
        id=order_id,
    )
    if order.status == 'draft':
        messages.error(request, 'سفارش پیش‌نویس هنوز ثبت نهایی نشده؛ پرداخت و فاکتور ممکن نیست.')
        return redirect('reception:patient-detail', patient_id=order.patient_id)
    invoice, created = OrderInvoice.issue_for_order(order, request.user)

    if created:
        messages.success(
            request,
            f'فاکتور شماره {invoice.invoice_number} ثبت شد.'
        )
    else:
        messages.info(
            request,
            f'این سفارش قبلا با شماره {invoice.invoice_number} فاکتور شده است.'
        )

    return redirect('reception:patient-detail', patient_id=order.patient_id)


@login_required
def print_order_invoice(request, order_id, print_type):
    allowed_types = {
        'receipt': 'reception/partials/invoices/_order_receipt_print.html',
        'services': 'reception/partials/invoices/_order_services_invoice_print.html',
        'visit': 'reception/partials/invoices/_order_visit_invoice_print.html',
    }

    template_name = allowed_types.get(print_type)

    if not template_name:
        messages.error(request, 'نوع چاپ فاکتور معتبر نیست.')
        return redirect('reception:dashboard')

    order = get_object_or_404(
        Order.objects
        .select_related('patient', 'examination', 'invoice')
        .prefetch_related('items__service', 'items__designs__design', 'payments'),
        id=order_id,
    )
    if order.status == 'draft':
        messages.error(request, 'سفارش پیش‌نویس هنوز ثبت نهایی نشده؛ پرداخت و فاکتور ممکن نیست.')
        return redirect('reception:patient-detail', patient_id=order.patient_id)
    
    invoice, _ = OrderInvoice.issue_for_order(order, request.user)

    context = {
        'order': order,
        'invoice': invoice,
        'print_type': print_type,
    }

    return render(request, template_name, context)


# @group_required('Reception')
# @login_required
# def edit_order(request, order_id):
#     order = get_object_or_404(
#         Order.objects.select_related('patient', 'examination')
#         .prefetch_related('items__designs', 'items__service'),
#         id=order_id
#     )

#     LOCKED_FOR_FULL_EDIT = ['delivered', 'cancelled', 'manufacturing', 'ready']

#     if order.status == 'draft' and order.measurement_status == 'requested':
#         messages.warning(
#             request,
#             'این سفارش در مرحله اندازه‌گیری کارگاه است؛ بعد از بازگشت پرونده می‌توانید ادامه دهید.')
#         return redirect('reception:patient-detail', patient_id=order.patient_id)
    
#     if order.status in LOCKED_FOR_FULL_EDIT:
#         messages.error(
#             request,
#             'این سفارش وارد مرحله ساخت یا تحویل شده و دیگر قابل ویرایش کامل نیست. '
#             'فقط سفارش‌های پیش‌نویس یا تأیید‌نشده قابل ویرایش هستند.'
#         )
#         return redirect('reception:patient-detail', patient_id=order.patient.id)

#     exam = order.examination  # ممکن است None باشد (سفارش مستقیم)
#     patient = order.patient

#     persian_order_date = ""

#     if order.order_date:
#         local_order_date = timezone.localtime(order.order_date)
#         j_order_date = jdatetime.date.fromgregorian(date=local_order_date.date())
#         persian_order_date = f"{j_order_date.year}/{j_order_date.month:02d}/{j_order_date.day:02d}"
#     else:
#         today_jalali = jdatetime.date.fromgregorian(date=timezone.localdate())
#         persian_order_date = f"{today_jalali.year}/{today_jalali.month:02d}/{today_jalali.day:02d}"


#     # ==================== داده‌های اولیه برای فرانت (مشابه create) ====================
#     services_data = {
#         sp.id: {
#             'name': getattr(sp, 'name', getattr(sp, 'title', 'نامشخص')),
#             'price': float(getattr(sp, 'unit_price', 0) or 0)
#         } for sp in Services.objects.all()
#     }

#     designs_data = {
#         dp.id: {
#             'name': getattr(dp, 'name', 'نامشخص'),
#             'price': float(getattr(dp, 'price', 0) or 0)
#         } for dp in Design.objects.all()
#     }

#     dynamic_fields_dict = defaultdict(list)
#     for df in ServiceDynamicField.objects.all():
#         choices_list = [c.strip() for c in (df.dropdown_options or '').split(',') if c.strip()]
#         dynamic_fields_dict[df.service_id].append({
#             'name': df.name, 'label': df.label, 'field_type': df.field_type,
#             'choices': choices_list, 'is_required': df.is_required
#         })

#     measurements = ServiceMeasurements.objects.all().select_related('service')
#     measurement_schema = {}
#     for m in measurements:
#         srv_id = str(m.service.id)
#         if srv_id not in measurement_schema:
#             measurement_schema[srv_id] = []
#         options = [opt.strip() for opt in (m.dropdown_options or '').split(',') if opt.strip()]
#         measurement_schema[srv_id].append({
#             'name': m.name, 'label': m.label, 'type': m.field_type,
#             'required': m.is_required, 'options': options
#         })

#     # ==================== ساخت داده‌های اقلام موجود سفارش برای پیش‌پرکردن ویزارد ====================
#     order_items_payload = []
#     for item in order.items.all():
#         designs_payload = [
#             {
#                 'design_id': d.design_id,
#                 'price': float(d.price_at_order),
#                 'side': d.side,
#             }
#             for d in item.designs.all()
#         ]
#         order_items_payload.append({
#             'item_id': item.id,
#             'specs_status': item.specs_status, 
#             'service_id': item.service_id,
#             'service_name': item.service.name if item.service else '',
#             'quantity': item.quantity,
#             'unit_price': float(item.price_at_order),
#             'discount': float(item.discount),
#             'send_to': item.send_to,
#             'priority': item.priority,
#             'delivery_date': item.delivery_date,
#             'status': item.status,
#             'notes': item.notes,
#             'measurements': item.measurements or {},
#             'dynamic_fields': item.dynamic_fields or {},
#             'designs': designs_payload,
#         })

#     context = {
#         'exam': exam,
#         'patient': patient,
#         'order': order,
#         'is_edit': True,
#         'total_paid': order.total_paid,
#         'existing_order_items': _json_for_script(order_items_payload),
#         'persian_order_date': persian_order_date,
#         'current_persian_order_date': persian_order_date,
#         **_wizard_static_data(),
#     }

#     # =========================== POST ===========================
#     if request.method == 'POST':
#         is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
#         is_draft = request.POST.get('is_draft') == '1'

#         try:
#             order_data_json = request.POST.get('order_data')
#             if not order_data_json:
#                 return JsonResponse({'status': 'error', 'message': 'داده‌های سفارش دریافت نشد'}, status=400)

#             order_data = json.loads(order_data_json)
#             order_data['patient'] = patient
#             order_data['examination'] = exam
#             order_data['created_by'] = order.created_by or request.user
#             order_data['order_id'] = order.id  # همیشه همین سفارش آپدیت می‌شود

#             updated_order = OrderService.create_or_update_from_wizard(
#                 order_data=order_data, is_draft=is_draft
#             )

#             if is_ajax:
#                 return JsonResponse({
#                     'status': 'saved' if is_draft else 'success',
#                     'order_id': updated_order.id,
#                     'message': f'سفارش #{updated_order.id} به‌روزرسانی شد.'
#                 })

#             messages.success(request, f'سفارش #{updated_order.id} با موفقیت ویرایش شد.')
#             return redirect('reception:patient-detail', patient_id=patient.id)

#         except Exception as e:
#             import traceback
#             print(traceback.format_exc())
#             if is_ajax:
#                 return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
#             messages.error(request, f'خطا: {str(e)}')
#             return redirect('reception:patient-detail', patient_id=patient.id)

#     return render(request, 'reception/create_order_from_exam.html', context)


@login_required
def get_price_by_size(request):
    service_id = request.GET.get('service_id')
    size = request.GET.get('size')
    variant_id = request.GET.get('variant_id')

    if not service_id or size in (None, ''):
        return JsonResponse({'error': 'پارامترهای مورد نیاز ارسال نشده است.'}, status=400)

    try:
        foot_length = Decimal(str(size))
    except (InvalidOperation, ValueError, TypeError):
        return JsonResponse({'error': 'مقدار سایز نامعتبر است.'}, status=400)

    service = Services.objects.filter(id=service_id).first()
    if not service:
        return JsonResponse({'error': 'سرویس یافت نشد.'}, status=404)

    if not service.has_size:
        return JsonResponse({'error': 'این سرویس بر اساس سایز قیمت‌گذاری نمی‌شود.'}, status=400)

    variant = ServiceVariant.objects.filter(id=variant_id).first() if variant_id else None

    size_price = ServiceSizePrice.find_price(
        service=service, foot_length=foot_length, variant=variant
    )

    if not size_price:
        return JsonResponse({'error': f'قیمتی برای سایز {size} تعریف نشده است.'}, status=404)

    return JsonResponse({
        'price': float(size_price.price),
        'cost': float(size_price.cost),
    })
    
@login_required
@group_required('Reception')
@require_POST
@transaction.atomic
def apply_suggested_price(request, item_id):
    item = get_object_or_404(
        OrderItem.objects.select_for_update(of=('self',)).select_related('order', 'service'),
        id=item_id,
    )
    order = item.order
    back = redirect('reception:patient-detail', patient_id=order.patient_id)

    if OrderInvoice.objects.filter(order=order).exists():
        messages.error(request, 'برای این سفارش فاکتور صادر شده و تغییر قیمت مجاز نیست.')
        return back
    if order.status in ('delivered', 'cancelled'):
        messages.error(request, 'تغییر قیمت این سفارش مجاز نیست.')
        return back

    price = item.suggested_size_price
    if price is None or price == item.price_at_order:
        messages.info(request, 'قیمت پیشنهادی متفاوتی وجود ندارد.')
        return back

    old = item.price_at_order
    item.price_at_order = price
    item.save(update_fields=['price_at_order', 'updated_at'])
    order.recalculate_total()
    order.update_payment_status()
    messages.success(request, f'قیمت از {old:,.0f} به {price:,.0f} تومان تغییر کرد.')
    return back