from functools import wraps
from django.http import HttpResponseForbidden


def user_in_groups(user, *group_names):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    wanted = {n.lower() for n in group_names}
    return any(n.lower() in wanted for n in user.groups.values_list('name', flat=True))


def group_required(*group_names):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseForbidden('Authentication required')
            if user_in_groups(request.user, *group_names):
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden('Permission denied')
        return wrapper
    return decorator