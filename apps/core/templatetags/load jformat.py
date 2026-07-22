import jdatetime
import datetime
from django import template

register = template.Library()

@register.filter(name='to_jalali')
def to_jalali_filter(value, date_format="%Y/%m/%d"):
    if not value:
        return ""
        
    try:
        # ۱. بررسی نوع ورودی و تبدیل استاندارد آن به آبجکت jdatetime
        if isinstance(value, datetime.datetime):
            j_date = jdatetime.datetime.fromgregorian(datetime=value)
        elif isinstance(value, datetime.date):
            j_date = jdatetime.date.fromgregorian(date=value)
        elif isinstance(value, (jdatetime.datetime, jdatetime.date)):
            j_date = value
        else:
            return str(value)
            
        # ۲. تنظیم زبان روی فارسی (تبدیل خودکار نام ماه‌ها و روزهای هفته به فارسی)
        j_date.locale = 'fa_IR'
        
        # ۳. فرمت کردن تاریخ بر اساس ورودی
        formatted_date = j_date.strftime(date_format)
        
        # ۴. تبدیل اعداد انگلیسی به فارسی (برای اطمینان کامل)
        persian_map = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
        return formatted_date.translate(persian_map)
        
    except Exception as e:
        # در محیط توسعه (Development) این پرینت به شما کمک می‌کند خطاهای احتمالی را پیدا کنید
        print(f"Jalali Translation Error: {e}") 
        return str(value)
