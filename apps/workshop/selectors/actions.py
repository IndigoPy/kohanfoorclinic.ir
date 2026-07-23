# apps/workshop/selectors/actions.py
from django.urls import reverse

from apps.workshop.constants import (
    ITEM_STATUS_AWAITING_SUPPLIER,
    ITEM_STATUS_DELIVERED,
    ITEM_STATUS_MANUFACTURING,
    ITEM_STATUS_PENDING,
    ITEM_STATUS_PENDING_SUPPLIER_REGISTRATION,
    ITEM_STATUS_QC_APPROVED,
    ITEM_STATUS_QC_PENDING,
    ITEM_STATUS_READY,
    ITEM_STATUS_READY_FOR_FITTING,
    ITEM_STATUS_RECEIVED_FROM_SUPPLIER,
    ITEM_STATUS_WORKSHOP_QUEUE,
    SEND_TO_MANUFACTURER,
    SEND_TO_WORKSHOP,
)


WORKSHOP_ITEM_ACTIONS = {
    ITEM_STATUS_PENDING: [
        {
            "name": "send_to_workshop_queue",
            "label": "ارسال به صف کارگاه",
            "icon": "fas fa-arrow-left",
            "class": "btn-outline-primary",
            "route": SEND_TO_WORKSHOP,
        },
        {
            "name": "register_supplier_order",
            "label": "ثبت برای تولیدکننده",
            "icon": "fas fa-industry",
            "class": "btn-outline-secondary",
            "route": SEND_TO_MANUFACTURER,
        },
    ],
    ITEM_STATUS_WORKSHOP_QUEUE: [
        {
            "name": "start_manufacturing",
            "label": "شروع ساخت",
            "icon": "fas fa-tools",
            "class": "btn-primary",
            "route": SEND_TO_WORKSHOP,
        },
    ],
    ITEM_STATUS_MANUFACTURING: [
        {
            "name": "mark_ready_for_fitting",
            "label": "آماده پرو",
            "icon": "fas fa-shoe-prints",
            "class": "btn-outline-info",
            "route": SEND_TO_WORKSHOP,
        },
        {
            "name": "send_to_qc",
            "label": "ارسال به کنترل کیفیت",
            "icon": "fas fa-clipboard-check",
            "class": "btn-warning",
            "route": SEND_TO_WORKSHOP,
        },
        {
            "name": "mark_ready",
            "label": "آماده تحویل",
            "icon": "fas fa-check-circle",
            "class": "btn-success",
            "route": SEND_TO_WORKSHOP,
        },
    ],
    ITEM_STATUS_PENDING_SUPPLIER_REGISTRATION: [
        {
            "name": "mark_sent_to_supplier",
            "label": "ارسال به تولیدکننده",
            "icon": "fas fa-paper-plane",
            "class": "btn-primary",
            "route": SEND_TO_MANUFACTURER,
        },
    ],
    ITEM_STATUS_AWAITING_SUPPLIER: [
        {
            "name": "mark_received_from_supplier",
            "label": "دریافت از تولیدکننده",
            "icon": "fas fa-box",
            "class": "btn-success",
            "route": SEND_TO_MANUFACTURER,
        },
    ],
    ITEM_STATUS_RECEIVED_FROM_SUPPLIER: [
        {
            "name": "mark_ready_for_fitting",
            "label": "آماده پرو",
            "icon": "fas fa-shoe-prints",
            "class": "btn-outline-info",
            "route": SEND_TO_MANUFACTURER,
        },
        {
            "name": "send_to_qc",
            "label": "ارسال به کنترل کیفیت",
            "icon": "fas fa-clipboard-check",
            "class": "btn-warning",
            "route": SEND_TO_MANUFACTURER,
        },
        {
            "name": "mark_ready",
            "label": "آماده تحویل",
            "icon": "fas fa-check-circle",
            "class": "btn-success",
            "route": SEND_TO_MANUFACTURER,
        },
    ],
    ITEM_STATUS_READY_FOR_FITTING: [
        {
            "name": "send_to_qc",
            "label": "ارسال به کنترل کیفیت",
            "icon": "fas fa-clipboard-check",
            "class": "btn-warning",
            "route": None,
        },
    ],
    ITEM_STATUS_QC_PENDING: [
        {
            "name": "approve_qc",
            "label": "تأیید کنترل کیفیت",
            "icon": "fas fa-check-double",
            "class": "btn-success",
            "route": None,
        },
    ],
    ITEM_STATUS_QC_APPROVED: [
        {
            "name": "mark_ready",
            "label": "آماده تحویل",
            "icon": "fas fa-check-circle",
            "class": "btn-success",
            "route": None,
        },
    ],
    ITEM_STATUS_READY: [
        {
            "name": "deliver_item",
            "label": "ثبت تحویل",
            "icon": "fas fa-box-open",
            "class": "btn-success",
            "route": None,
            "confirm": "آیا از ثبت تحویل این محصول اطمینان دارید؟",
        },
    ],
}


def get_available_item_actions(item):
    actions = WORKSHOP_ITEM_ACTIONS.get(item.status, [])
    available_actions = []

    for action in actions:
        if action["route"] is not None and action["route"] != item.send_to:
            continue

        available_actions.append({
            **action,
            "url": reverse(f"workshop:{action['name']}", kwargs={"item_id": item.id}),
        })

    return available_actions
