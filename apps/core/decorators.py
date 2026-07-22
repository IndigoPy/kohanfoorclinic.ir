# WorkShop/decorators.py

from django.http import HttpResponseForbidden
from functools import wraps

def group_required(group_name):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):

            if not request.user.is_authenticated:
                return HttpResponseForbidden('Authentication required')

            if request.user.groups.filter(name=group_name).exists():
                return view_func(request, *args, **kwargs)

            return HttpResponseForbidden('Permission denied')

        return wrapper
    return decorator
