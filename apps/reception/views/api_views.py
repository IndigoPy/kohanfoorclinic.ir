# reception/views/api_views
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Prefetch
from django.core.paginator import Paginator

from ..models import Patient, Services, ServiceSizePrice 
# from WorkShop.forms import OrderCreateForm
from apps.core.decorators import group_required
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.db import IntegrityError
from django.utils import timezone
import jdatetime 
from decimal import Decimal
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.safestring import mark_safe






def search_patients_ajax(request):
    query = request.GET.get('q', '').strip()
    source = request.GET.get('source', '')  # دریافت پارامتر تشخیص‌دهنده

    if not query:
        # هندل کردن حالت خالی برای هر دو فرانت‌اند
        if source == 'select2':
            return JsonResponse({'results': []})
        return JsonResponse({'html': ''})

    # فیلتر کردن بیماران
    patients = Patient.objects.filter(
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(case_number__icontains=query) |
        Q(phone__icontains=query)
    )[:20]
    
    # خروجی مخصوص Select2 (داده‌های خام)
    if source == 'select2':
        patients_data = [
            {
                'id': p.id,
                'full_name': p.full_name,  # اطمینان حاصل کنید full_name پراپرتی معتبر مدل است
                'case_number': p.case_number
            }
            for p in patients
        ]
        return JsonResponse({'results': patients_data})

    # خروجی مخصوص جدول (HTML رندر شده)
    html = render_to_string(
        'reception/partials/patients_list.html', 
        {'patients': patients}, 
        request=request
    )
    return JsonResponse({'html': html})


def get_price_by_size(request):
    service_id = request.GET.get('service_id')
    size_value = request.GET.get('size')
    variant_id = request.GET.get('variant_id') # اختیاری، اگر واریانت دارید

    if not service_id or not size_value:
        return JsonResponse({'error': 'پارامترهای سرویس یا سایز ارسال نشده است.'}, status=400)

    try:
        service = Services.objects.get(id=service_id)
        size_decimal = Decimal(size_value)

        # اگر سرویس قیمت‌گذاری بر اساس سایز ندارد، قیمت پایه/واحد را برگردان
        if not service.has_size:
            return JsonResponse({'price': service.unit_price or 0})

        # استفاده از متد کمکی که در مدل خود نوشته‌اید
        price_record = ServiceSizePrice.find_price(
            service=service, 
            foot_length=size_decimal, 
            variant=variant_id
        )

        if price_record:
            return JsonResponse({'price': price_record.price})
        else:
            return JsonResponse({'error': 'قیمتی برای این سایز در دیتابیس یافت نشد.'}, status=404)

    except Services.DoesNotExist:
        return JsonResponse({'error': 'سرویس یافت نشد.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)