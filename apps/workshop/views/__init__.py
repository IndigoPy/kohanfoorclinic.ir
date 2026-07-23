# apps/workshop/views/__init__.py

from .dashboard import workshop_dashboard
from .orders import workshop_order_list, workshop_order_detail
from .items import update_item_status
from .notes import update_workshop_notes
from .items import update_item_status

__all__ = [
    'workshop_dashboard',
    'workshop_order_list',
    'workshop_order_detail',
    'update_item_status',
    'update_workshop_notes',
]
