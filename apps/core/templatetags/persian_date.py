from django import template

register = template.Library()

MONTHS = {
    'Farvardin': 'فروردین', 'Ordibehesht': 'اردیبهشت', 'Khordad': 'خرداد',
    'Tir': 'تیر', 'Mordad': 'مرداد', 'Shahrivar': 'شهریور',
    'Mehr': 'مهر', 'Aban': 'آبان', 'Azar': 'آذر',
    'Dey': 'دی', 'Bahman': 'بهمن', 'Esfand': 'اسفند'
}

@register.filter
def persian_month(date_str):
    if not date_str:
        return ""
    for eng, per in MONTHS.items():
        date_str = date_str.replace(eng, per)
    return date_str
