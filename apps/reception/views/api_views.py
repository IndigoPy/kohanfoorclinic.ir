# reception/views/api_views
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Prefetch
from django.core.paginator import Paginator

from apps.reception.utils import normalize_digits

from ..models import Patient, Services, ServiceSizePrice, Referrer
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
from django.views.decorators.http import require_POST



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


# def get_price_by_size(request):
#     service_id = request.GET.get('service_id')
#     size_value = request.GET.get('size')
#     variant_id = request.GET.get('variant_id') # اختیاری، اگر واریانت دارید

#     if not service_id or not size_value:
#         return JsonResponse({'error': 'پارامترهای سرویس یا سایز ارسال نشده است.'}, status=400)

#     try:
#         service = Services.objects.get(id=service_id)
#         size_decimal = Decimal(size_value)

#         # اگر سرویس قیمت‌گذاری بر اساس سایز ندارد، قیمت پایه/واحد را برگردان
#         if not service.has_size:
#             return JsonResponse({'price': service.unit_price or 0})

#         # استفاده از متد کمکی که در مدل خود نوشته‌اید
#         price_record = ServiceSizePrice.find_price(
#             service=service, 
#             foot_length=size_decimal, 
#             variant=variant_id
#         )

#         if price_record:
#             return JsonResponse({'price': price_record.price})
#         else:
#             return JsonResponse({'error': 'قیمتی برای این سایز در دیتابیس یافت نشد.'}, status=404)

#     except Services.DoesNotExist:
#         return JsonResponse({'error': 'سرویس یافت نشد.'}, status=404)
#     except Exception as e:
#         return JsonResponse({'error': str(e)}, status=500)
    
@login_required
def search_referrers_ajax(request):
    q = normalize_digits(request.GET.get('q', '')).strip()
    if not q:
        return JsonResponse({'results': []})

    refs = Referrer.objects.filter(is_active=True)
    pats = Patient.objects.filter(is_active=True)

    exclude_id = request.GET.get('exclude', '')
    if exclude_id.isdigit():
        pats = pats.exclude(pk=int(exclude_id))

    # هر کلمه باید در یکی از فیلدها باشد (مثلاً «علی رضا»)
    for term in q.split():
        refs = refs.filter(
            Q(full_name__icontains=term) | Q(code__icontains=term) |
            Q(phone__icontains=term) | Q(workplace__icontains=term)
        )
        pats = pats.filter(
            Q(first_name__icontains=term) | Q(last_name__icontains=term) |
            Q(case_number__icontains=term) | Q(phone__icontains=term)
        )

    groups = []
    refs = list(refs[:10])
    pats = list(pats[:10])

    if refs:
        groups.append({'text': 'معرفین ثبت‌شده', 'children': [{
            'id': f'ref:{r.pk}',
            'text': f'{r.full_name} ({r.code})',
            'meta': ' · '.join(x for x in (r.get_category_display(), r.workplace, r.phone) if x),
        } for r in refs]})

    if pats:
        groups.append({'text': 'بیماران', 'children': [{
            'id': f'pat:{p.pk}',
            'text': f'{p.full_name} ({p.case_number})',
            'meta': p.phone or '',
        } for p in pats]})

    return JsonResponse({'results': groups})


@require_POST
@login_required
def quick_create_referrer(request):
    name = request.POST.get('full_name', '').strip()
    if not name:
        return JsonResponse({'success': False, 'error': 'نام معرف الزامی است.'}, status=400)

    category = request.POST.get('category', 'other')
    if category not in dict(Referrer.CATEGORY_CHOICES):
        category = 'other'

    obj = Referrer.objects.create(
        full_name=name[:200],
        category=category,
        phone=normalize_digits(request.POST.get('phone', '')).strip()[:20],
        workplace=request.POST.get('workplace', '').strip()[:200],
    )
    return JsonResponse({'success': True, 'id': f'ref:{obj.pk}', 'text': f'{obj.full_name} ({obj.code})'})