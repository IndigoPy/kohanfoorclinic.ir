# apps/workshop/exceptions.py


class WorkshopWorkflowError(Exception):
    """Base exception for workshop workflow errors."""


class InvalidItemTransitionError(WorkshopWorkflowError):
    """Raised when an order item status transition is not allowed."""


class LockedOrderError(WorkshopWorkflowError):
    """Raised when workflow action is blocked by the parent order status."""


class InvalidWorkshopActionError(WorkshopWorkflowError):
    """Raised when a workflow action cannot be applied to the selected item."""
