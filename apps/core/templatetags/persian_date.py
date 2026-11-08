from django import template
import jdatetime
import datetime

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

WEEKDAYS = ['شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه']
JALALI_MONTHS = [
    'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
    'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند',
]
_EN_TO_FA = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')


def _to_jdate(value):
    # ترتیب مهم است: datetime زیرکلاس date است
    if isinstance(value, jdatetime.datetime):
        return value.date()
    if isinstance(value, jdatetime.date):
        return value
    if isinstance(value, datetime.datetime):
        return jdatetime.date.fromgregorian(date=value.date())
    if isinstance(value, datetime.date):
        return jdatetime.date.fromgregorian(date=value)
    return None


@register.filter
def jalali_long(value):
    """خروجی: پنجشنبه ۱۴ آبان ۱۴۰۵"""
    j = _to_jdate(value)
    if j is None:
        return ''
    text = f"{WEEKDAYS[j.weekday()]} {j.day} {JALALI_MONTHS[j.month - 1]} {j.year}"
    return text.translate(_EN_TO_FA)


@register.filter
def persian_digits(value):
    """تبدیل اعداد انگلیسی به فارسی، مثلاً برای ساعت"""
    return str(value).translate(_EN_TO_FA) if value not in (None, '') else ''