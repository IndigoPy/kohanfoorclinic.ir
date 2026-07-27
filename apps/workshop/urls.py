from django.urls import path

from . import views
from .views import actions, notes


app_name = 'workshop'


urlpatterns = [
    path(
        '',
        views.workshop_dashboard,
        name='dashboard',
    ),
    path(
        'orders/',
        views.workshop_order_list,
        name='order-list',
    ),
    path(
        'orders/<int:order_id>/',
        views.workshop_order_detail,
        name='order-detail',
    ),
    path(
        'items/<int:item_id>/status/',
        views.update_item_status,
        name='update-item-status',
    ),
    path(
        'orders/<int:order_id>/notes/',
        views.update_workshop_notes,
        name='update-workshop-notes',
    ),
    
    # Workflow
        path(
        "items/<int:item_id>/send-to-workshop/",
        actions.send_to_workshop_queue,
        name="send_to_workshop_queue",
    ),
    path(
        "items/<int:item_id>/start-manufacturing/",
        actions.start_manufacturing,
        name="start_manufacturing",
    ),
    path(
        "items/<int:item_id>/register-supplier-order/",
        actions.register_supplier_order,
        name="register_supplier_order",
    ),
    path(
        "items/<int:item_id>/mark-sent-to-supplier/",
        actions.mark_sent_to_supplier,
        name="mark_sent_to_supplier",
    ),
    path(
        "items/<int:item_id>/received-from-supplier/",
        actions.mark_received_from_supplier,
        name="mark_received_from_supplier",
    ),
    path(
        "items/<int:item_id>/ready-for-fitting/",
        actions.mark_ready_for_fitting,
        name="mark_ready_for_fitting",
    ),
    path(
        "items/<int:item_id>/send-to-qc/",
        actions.send_to_qc,
        name="send_to_qc",
    ),
    path(
        "items/<int:item_id>/approve-qc/",
        actions.approve_qc,
        name="approve_qc",
    ),
    path(
        "items/<int:item_id>/mark-ready/",
        actions.mark_ready,
        name="mark_ready",
    ),
    path(
        "items/<int:item_id>/deliver/",
        actions.deliver_item,
        name="deliver_item",
    ),
        path(
        "items/<int:item_id>/resume-manufacturing/",
        actions.resume_manufacturing,
        name="resume_manufacturing",
    ),
    
    # actions
    path(
    "items/<int:item_id>/notes/",
    notes.update_item_notes,
    name="update_item_notes",
),
]
