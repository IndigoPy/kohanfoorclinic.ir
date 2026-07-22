import json
from django import template

register = template.Library()


@register.filter(name='split')
def split(value, delimiter=','):
    """
    رشته رو بر اساس جداکننده تقسیم می‌کنه
    مثال: {{ "چپ|راست"|split:"|" }}
    """
    if not value:
        return []
    return str(value).split(delimiter)


@register.filter(name='strip')
def strip_filter(value):
    """
    فاصله‌های اضافه رو حذف می‌کنه
    """
    if not value:
        return ''
    return str(value).strip()


@register.filter(name='contains')
def contains(value, substring):
    """
    بررسی می‌کنه که آیا value حاوی substring هست
    استفاده: {{ value|contains:"چپ:" }}
    """
    if not value:
        return False
    return substring in str(value)

@register.filter(name='parse_prescription')
def parse_prescription(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


@register.filter(name='is_dict')
def is_dict(value):
    return isinstance(value, dict)


@register.filter(name='is_list')
def is_list(value):
    return isinstance(value, list)


@register.filter(name='dict_items')
def dict_items(value):
    if isinstance(value, dict):
        return value.items()
    return []


@register.filter(name='get_item')
def get_item(dictionary, key):
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    return ''
