# apps/workshop/views/actions.py

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from apps.reception.models import OrderItem
from apps.workshop.exceptions import WorkshopWorkflowError
from apps.workshop.services.workflow import WorkshopWorkflowService

from django.shortcuts import resolve_url
from django.utils.http import url_has_allowed_host_and_scheme

def _require_post(request):
    return request.method == "POST"


def _get_next_url(request, item):
    """
    Central redirect resolver for workshop actions.

    Priority:
    1. explicit next from form
    2. HTTP referer
    3. order detail fallback
    """

    next_url = request.POST.get("next") or request.GET.get("next")

    if next_url:
        return next_url

    referer = request.META.get("HTTP_REFERER")

    if referer:
        return referer

    return reverse("reception:order_detail", kwargs={"pk": item.order_id})


def _get_description(request, default=""):
    return request.POST.get("description") or default


def _handle_workflow_action(
    request,
    item_id,
    service_method_name,
    success_message,
    default_description="",
):
    if not _require_post(request):
        return HttpResponseNotAllowed(["POST"])

    item = get_object_or_404(
        OrderItem.objects.select_related("order"),
        pk=item_id,
    )

    service = WorkshopWorkflowService(user=request.user)
    service_method = getattr(service, service_method_name)
    description = _get_description(request, default=default_description)

    try:
        service_method(item=item, description=description)
        messages.success(request, success_message)

    except WorkshopWorkflowError as exc:
        messages.error(request, str(exc))

    return redirect(_get_next_url(request, item))


@login_required
def send_to_workshop_queue(request, item_id):
    return _handle_workflow_action(
        request=request,
        item_id=item_id,
        service_method_name="send_to_workshop_queue",
        success_message="آیتم به صف کارگاه منتقل شد.",
        default_description="انتقال آیتم به صف کارگاه",
    )


@login_required
def start_manufacturing(request, item_id):
    return _handle_workflow_action(
        request=request,
        item_id=item_id,
        service_method_name="start_manufacturing",
        success_message="ساخت آیتم شروع شد.",
        default_description="شروع ساخت آیتم در کارگاه",
    )


@login_required
def register_supplier_order(request, item_id):
    return _handle_workflow_action(
        request=request,
        item_id=item_id,
        service_method_name="register_supplier_order",
        success_message="آیتم برای ثبت سفارش تولیدکننده علامت‌گذاری شد.",
        default_description="ثبت اولیه سفارش تولیدکننده",
    )


@login_required
def mark_sent_to_supplier(request, item_id):
    return _handle_workflow_action(
        request=request,
        item_id=item_id,
        service_method_name="mark_sent_to_supplier",
        success_message="آیتم به وضعیت در انتظار تولیدکننده منتقل شد.",
        default_description="ارسال سفارش به تولیدکننده",
    )


@login_required
def mark_received_from_supplier(request, item_id):
    return _handle_workflow_action(
        request=request,
        item_id=item_id,
        service_method_name="mark_received_from_supplier",
        success_message="دریافت آیتم از تولیدکننده ثبت شد.",
        default_description="دریافت آیتم از تولیدکننده",
    )


@login_required
def mark_ready_for_fitting(request, item_id):
    return _handle_workflow_action(
        request=request,
        item_id=item_id,
        service_method_name="mark_ready_for_fitting",
        success_message="آیتم آماده پرو شد.",
        default_description="آماده‌سازی آیتم برای پرو",
    )


@login_required
def send_to_qc(request, item_id):
    return _handle_workflow_action(
        request=request,
        item_id=item_id,
        service_method_name="send_to_qc",
        success_message="آیتم به کنترل کیفیت ارسال شد.",
        default_description="ارسال آیتم به کنترل کیفیت",
    )


@login_required
def approve_qc(request, item_id):
    return _handle_workflow_action(
        request=request,
        item_id=item_id,
        service_method_name="approve_qc",
        success_message="کنترل کیفیت آیتم تأیید شد.",
        default_description="تأیید کنترل کیفیت آیتم",
    )


@login_required
def mark_ready(request, item_id):
    return _handle_workflow_action(
        request=request,
        item_id=item_id,
        service_method_name="mark_ready",
        success_message="آیتم آماده تحویل شد.",
        default_description="آماده تحویل شدن آیتم",
    )


@login_required
def deliver_item(request, item_id):
    return _handle_workflow_action(
        request=request,
        item_id=item_id,
        service_method_name="deliver_item",
        success_message="تحویل آیتم ثبت شد.",
        default_description="تحویل آیتم به بیمار",
    )


def _get_next_url(request, item):
    next_url = request.POST.get("next") or request.GET.get("next")

    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url

    referer = request.META.get("HTTP_REFERER")

    if referer and url_has_allowed_host_and_scheme(
        url=referer,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return referer

    return resolve_url("reception:order_detail", pk=item.order_id)