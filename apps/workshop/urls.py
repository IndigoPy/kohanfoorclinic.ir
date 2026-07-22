from django.urls import path

from . import views


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
        'orders/<int:order_id>/items/status/',
        views.update_all_items_status,
        name='update-all-items-status',
    ),
    path(
        'orders/<int:order_id>/notes/',
        views.update_workshop_notes,
        name='update-workshop-notes',
    ),
]
