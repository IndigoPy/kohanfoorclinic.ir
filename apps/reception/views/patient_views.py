# reception/views/patient_views
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Prefetch, Sum, Value
from django.core.paginator import Paginator
from ..models import Patient, Document, Order
from apps.core.decorators import group_required
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.utils import timezone
import jdatetime
from ..utils import standardize_persian_date
from django.db.models.functions import Concat
from django.db import models
from ..models.orders import PaymentMethod,PaymentAccount,Payment,OrderInvoice
from decimal import Decimal
from ..models.patient import PatientAttachment, PatientInsuranceInfo,UnderlyingDisease,OrthoticHistoryType
from django.views.decorators.http import require_POST

from apps.appointments.models import Appointment
from apps.appointments.models.choices import AppointmentType, AppointmentStatus
from ..utils import standardize_persian_date, resolve_referrer, referrer_initial, referrer_initial_from_raw

def is_manager(user):
    """فقط سوپریوزر یا عضو گروه Manager اجازه ویرایش/حذف تراکنش دارد"""
    return user.is_superuser or user.groups.filter(name='Examiner').exists()

@group_required('Reception')
@login_required
def reception_dashboard(request):
    search_query = request.GET.get('q', '').strip()
    today_jalali = jdatetime.date.today()

    # =========================================================
    # 1) باکس‌های بالای داشبورد
    # =========================================================

    # الف) بیماران جدید که واقعاً منتظر معاینه هستند
    waiting_exam_new_patients = Patient.objects.filter(
        stage='waiting_exam'
    ).order_by('-created_at')[:12]

    # ب) نوبت‌های فالوآپ/تماس کلینیک که امروز حضور خورده‌اند
    waiting_exam_appointments = Appointment.objects.filter(
        date=today_jalali,
        status=AppointmentStatus.WAITING,
        appointment_type__in=[
            AppointmentType.FOLLOW_UP,
            AppointmentType.CLINIC_CALL,
        ]
    ).select_related('patient').order_by('start_time', '-created_at')[:12]

    # ج) نوبت‌های تحویل که امروز حضور خورده‌اند
    in_delivery_appointments = Appointment.objects.filter(
        date=today_jalali,
        status=AppointmentStatus.WAITING,
        appointment_type=AppointmentType.DELIVERY,
    ).select_related('patient').order_by('start_time', '-created_at')[:10]

    # د) نوبت‌های بررسی کار که امروز حضور خورده‌اند
    waiting_qc_appointments = Appointment.objects.filter(
        date=today_jalali,
        status=AppointmentStatus.WAITING,
        appointment_type=AppointmentType.CHECKUP,
    ).select_related('patient').order_by('start_time', '-created_at')[:10]

    # ────── ۲. لیست کامل بیماران (برای جدول پایین) ──────
    patients_qs = Patient.objects.all().order_by('-created_at').prefetch_related(
        Prefetch(
            'orders',                                      # ← related_name درست
            queryset=Order.objects.order_by('-created_at'),
            to_attr='all_orders'
        )
    )

    if search_query:
        patients_qs = patients_qs.annotate(
            search_name=Concat('first_name', Value(' '), 'last_name', output_field=models.CharField())).filter(
            Q(search_name__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(case_number__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(alternative_phone__icontains=search_query) |
            Q(national_id__icontains=search_query) |
            Q(reception_notes__icontains=search_query)
        )

    patients = list(patients_qs)

    # پردازش اطلاعات هر بیمار برای جدول
    for patient in patients:
        patient.admission_date = getattr(
            patient, 'admission_date', None) or patient.created_at

        last_order = patient.all_orders[0] if hasattr(
            patient, 'all_orders') and patient.all_orders else None

        if last_order:
            patient.has_order = True
            patient.last_visit_date = last_order.created_at
            patient.last_order_date = last_order.created_at

            first_item = last_order.orderitem_set.first() if hasattr(
                last_order, 'orderitem_set') else None
            patient.last_order_summary = first_item.service if first_item else (
                'سفارش جدید')  #last_order.orders_note
        else:
            patient.has_order = False
            patient.last_visit_date = None
            patient.last_order_date = None
            patient.last_order_summary = 'بدون سفارش'

    # ────── ۳. Pagination (انتقال به پیش از شرط AJAX) ──────
    paginator = Paginator(patients, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    # ────── ۴. AJAX جستجو ──────
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        html = render_to_string('reception/partials/patients_list.html', {
            'patients': page_obj,  # ← تغییر مهم: ارسال لیست صفحه‌بندی شده به جای کل بیماران
            'search_query': search_query,
        }, request=request)
        return JsonResponse({'html': html})

    # ────── ۵. رندر نهایی در حالت عادی ──────
    context = {
        # برای کارت‌های بالا
        'waiting_exam_new_patients': waiting_exam_new_patients,
        'waiting_exam_appointments': waiting_exam_appointments,
        'in_delivery_appointments': in_delivery_appointments,
        'waiting_qc_appointments': waiting_qc_appointments,

        # لیست کامل برای جدول
        'patients': page_obj,
        'search_query': search_query,
    }
    return render(request, 'reception/dashboard.html', context)


@group_required('Reception')
@login_required
def create_patient(request):
    if request.method == 'POST':
        case_number = request.POST.get('case_number')
        if Patient.objects.filter(case_number=case_number).exists():
            messages.error(request, 'شماره پرونده تکراری است.')
            return render(request, 'reception/create_patient.html', {'suggested_case_number': case_number})
      
        # --- پردازش تاریخ ---
        raw_birth_date = request.POST.get('birth_date')
        clean_birth_date = standardize_persian_date(raw_birth_date)
        formatted_birthdate = None
        try:
            if clean_birth_date:
                # یکسان‌سازی جداکننده‌ها: تبدیل تمام خط تیره‌ها به اسلش
                normalized_date = clean_birth_date.replace('-', '/')
                
                # اکنون با خیال راحت می‌توانیم بر اساس اسلش جداسازی کنیم
                year, month, day = map(int, normalized_date.split('/'))
                
                j_date = jdatetime.date(year, month, day)
                formatted_birthdate = j_date.togregorian()
        except Exception as e:
            print(f"error {e}")

        
        for disease_name in request.POST.getlist('underlying_diseases'):
            disease_name = disease_name.strip()
            if disease_name:
                UnderlyingDisease.objects.get_or_create(name=disease_name)

        for orthotic_name in request.POST.getlist('orthotic_history'):
            orthotic_name = orthotic_name.strip()
            if orthotic_name:
                OrthoticHistoryType.objects.get_or_create(name=orthotic_name)
        
        ref_text, ref_patient, ref_person = resolve_referrer(request.POST.get('referrer')),
                
        # --- ایجاد بیمار (بدون attached_to) ---
                # --- ایجاد بیمار (بدون attached_to) ---
        patient = Patient.objects.create(
            case_number=case_number,
            first_name=request.POST.get('first_name'),
            last_name=request.POST.get('last_name'),
            phone=request.POST.get('phone'),
            alternative_phone=request.POST.get('alternative_phone'),
            national_id=request.POST.get('national_id'),
            gender=request.POST.get('gender'),
            foot_size=request.POST.get('foot_size'),
            height=request.POST.get('height'),
            weight=request.POST.get('weight'),
            referrer=ref_text or None,
            referrer_patient=ref_patient,
            referrer_person=ref_person,
            visit_reason='، '.join(request.POST.getlist('visit_reason')),
            underlying_diseases=','.join(request.POST.getlist('underlying_diseases')),
            orthotic_history=','.join(request.POST.getlist('orthotic_history')),
            city=request.POST.get('city'),
            neighborhood=request.POST.get('neighborhood'),
            reception_notes=request.POST.get('reception_notes'),
            photo=request.FILES.get('photo'),
            birth_date=formatted_birthdate,
            created_by=request.user,
            admission_date=timezone.now(),
            created_at=timezone.now(),
            stage='waiting_exam'
        )
        
        save_patient_insurance_info(patient, request)
       # --- پردازش پیوست‌های چندگانه پس از ایجاد بیمار ---
        attached_patient_ids = request.POST.getlist('attached_patients')
        sync_patient_attachments(patient, attached_patient_ids, user=request.user)
       
        # ذخیره مدارک
        for doc in request.FILES.getlist('documents'):
            Document.objects.create(
                patient=patient,
                file=doc,
                description=doc.name,
                uploaded_by=request.user
            )
        messages.success(request, 'بیمار با موفقیت ثبت شد.')

        action = request.POST.get('action')
        if action == 'save_print':
            # ریدایرکت به صفحه چاپ پرونده
            # مطمئن شوید که در urls.py نام 'print-patient' را برای print_patient تعریف کرده‌اید
            return redirect('reception:print-patient', patient_id=patient.id)
        else:
            # ریدایرکت به صفحه جزئیات بیمار (ذخیره و بازگشت)
            return redirect('reception:patient-detail', patient_id=patient.id)

    # GET - محاسبه شماره پیشنهادی
    today = jdatetime.date.today()
    prefix = f"{today.year}-{today.month:02d}"

    last_patient = Patient.objects.filter(
        case_number__startswith=prefix).order_by('-case_number').first()
    if last_patient:
        try:
            last_num = int(last_patient.case_number.split('-')[-1])
            next_num = last_num + 1
        except:
            next_num = 1000
    else:
        next_num = 1000

    suggested_case_number = f"{prefix}-{next_num:04d}"

    
     # دریافت اطلاعات اولیه از URL (اگر از صفحه نوبت‌ها آمده باشد)
    prefill_data = {
        'first_name': request.GET.get('first_name', ''),
        'last_name': request.GET.get('last_name', ''),
        'phone': request.GET.get('phone', ''),
        'phone2': request.GET.get('phone2', ''),
        'referrer': request.GET.get('referrer', ''),
        'insurance_info': None,
        'persian_primary_insurance_expiry_date': '',
    }

    context = {
        'suggested_case_number': suggested_case_number,
        'prefill_data': prefill_data,
        'selected_attached_patients': Patient.objects.none(), 
        'all_diseases': UnderlyingDisease.objects.all(),
        'all_orthotics': OrthoticHistoryType.objects.all(),
        'referrer_initial': referrer_initial_from_raw(
        request.GET.get('referrer_ref') or request.GET.get('referrer', '')
        ),
    }
    
    return render(request, 'reception/create_patient.html', context)



@group_required('Reception')
@login_required
def edit_patient(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)

    if request.method == 'POST':
        case_number = request.POST.get('case_number')

        # بررسی تکراری نبودن شماره پرونده
        if Patient.objects.filter(case_number=case_number).exclude(id=patient.id).exists():
            messages.error(request, 'شماره پرونده تکراری است.')
            return redirect('reception:edit-patient', patient_id=patient.id)

        # پردازش تاریخ تولد
        raw_birth_date = request.POST.get('birth_date')
        clean_birth_date = standardize_persian_date(raw_birth_date)

        # پردازش تاریخ پذیرش (Admission Date)
        raw_admission_date = request.POST.get('admission_date')
        if raw_admission_date:
            try:
                # پاکسازی و تبدیل
                clean_date = raw_admission_date.strip().replace('-', '/')
                year, month, day = map(int, clean_date.split('/'))
                patient.admission_date = jdatetime.date(year, month, day).togregorian()
            except Exception as e:
                # اگر فرمت اشتباه بود، می‌توانید پیامی نمایش دهید یا نادیده بگیرید
                print(f"Error parsing admission date: {e}")
                
        if clean_birth_date:
            try:
                normalized_date = clean_birth_date.replace('-', '/')
                year, month, day = map(int, normalized_date.split('/'))
                patient.birth_date = jdatetime.date(year, month, day).togregorian()
            except Exception as e:
                print(f"error parsing date: {e}")

        # به‌روزرسانی فیلدها
        patient.case_number = case_number
        patient.first_name = request.POST.get('first_name')
        patient.last_name = request.POST.get('last_name')
        patient.phone = request.POST.get('phone')
        patient.alternative_phone = request.POST.get('alternative_phone')
        patient.national_id = request.POST.get('national_id')
        patient.gender = request.POST.get('gender')
        patient.foot_size = request.POST.get('foot_size')
        patient.height = request.POST.get('height')
        patient.weight = request.POST.get('weight')
        ref_text, ref_patient, ref_person = resolve_referrer(request.POST.get('referrer'))
        if ref_patient and ref_patient.pk == patient.pk:
            ref_patient = None  # بیمار نمی‌تواند معرف خودش باشد
        patient.referrer = ref_text or None
        patient.referrer_patient = ref_patient
        patient.referrer_person = ref_person
        patient.visit_reason = '، '.join(request.POST.getlist('visit_reason'))
        patient.underlying_diseases = ','.join([
            item.strip() for item in request.POST.getlist('underlying_diseases') if item.strip()
        ])

        patient.orthotic_history = ','.join([
            item.strip() for item in request.POST.getlist('orthotic_history') if item.strip()
        ])
        patient.city = request.POST.get('city')
        patient.neighborhood = request.POST.get('neighborhood')
        patient.reception_notes = request.POST.get('reception_notes')
        patient.stage = request.POST.get('stage', patient.stage)
        patient.patient_class = request.POST.get('patient_class', patient.patient_class)

        # اگر عکس جدیدی آپلود شد
        if request.FILES.get('photo'):
            patient.photo = request.FILES.get('photo')

        
        for disease_name in request.POST.getlist('underlying_diseases'):
            disease_name = disease_name.strip()
            if disease_name:
                UnderlyingDisease.objects.get_or_create(name=disease_name)

        for orthotic_name in request.POST.getlist('orthotic_history'):
            orthotic_name = orthotic_name.strip()
            if orthotic_name:
                OrthoticHistoryType.objects.get_or_create(name=orthotic_name)
        patient.save()
        save_patient_insurance_info(patient, request)

        # همگام‌سازی پیوست‌ها
        attached_patient_ids = request.POST.getlist('attached_patients')
        sync_patient_attachments(
            patient=patient,
            attached_patient_ids=attached_patient_ids,
            user=request.user
        )

        # ذخیره مدارک جدید
        for doc in request.FILES.getlist('documents'):
            Document.objects.create(
                patient=patient,
                file=doc,
                description=doc.name,
                uploaded_by=request.user
            )

        messages.success(request, 'اطلاعات بیمار با موفقیت ویرایش شد.')

        action = request.POST.get('action')
        if action == 'save_print':
            return redirect('reception:print-patient', patient_id=patient.id)
        return redirect('reception:patient-detail', patient_id=patient.id)

    # GET
    persian_birth_date = ""
    if patient.birth_date:
        j_date = jdatetime.date.fromgregorian(date=patient.birth_date)
        persian_birth_date = f"{j_date.year}/{j_date.month:02d}/{j_date.day:02d}"

    diseases_list = [
    item.strip()
    for item in (patient.underlying_diseases or '').split(',')
    if item.strip()
]

    orthotic_list = [
        item.strip()
        for item in (patient.orthotic_history or '').split(',')
        if item.strip()
    ]


    referrers = Patient.objects.exclude(
        referrer__isnull=True
    ).exclude(
        referrer__exact=''
    ).values_list(
        'referrer', flat=True
    ).distinct()

    visit_reasons_list = []
    if patient.visit_reason:
        visit_reasons_list = [r.strip() for r in patient.visit_reason.split('،')]

    selected_attached_patients = patient.get_related_patients()

    insurance_info = getattr(patient, 'insurance_info', None)

    persian_primary_insurance_expiry_date = ""
    if insurance_info and insurance_info.primary_insurance_expiry_date:
        j_date = jdatetime.date.fromgregorian(
            date=insurance_info.primary_insurance_expiry_date
        )
        persian_primary_insurance_expiry_date = f"{j_date.year}/{j_date.month:02d}/{j_date.day:02d}"

    # تبدیل تاریخ پذیرش به شمسی
    persian_admission_date = ""
    if patient.admission_date:
        j_date = jdatetime.date.fromgregorian(date=patient.admission_date)
        persian_admission_date = f"{j_date.year}/{j_date.month:02d}/{j_date.day:02d}"
    
    context = {
        'patient': patient,
        'persian_birth_date': persian_birth_date,
        'diseases_list': diseases_list,
        'orthotic_list': orthotic_list,
        'referrers': referrers,
        'visit_reasons_list': visit_reasons_list,
        'selected_attached_patients': selected_attached_patients,
        'insurance_info': insurance_info,
        'persian_primary_insurance_expiry_date': persian_primary_insurance_expiry_date,
        'all_diseases': UnderlyingDisease.objects.all(),
        'all_orthotics': OrthoticHistoryType.objects.all(),
        'persian_admission_date': persian_admission_date,
        'referrer_initial': referrer_initial(patient),
    }

    return render(request, 'reception/create_patient.html', context)


@login_required
def print_patient(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)
    context = {
        'patient': patient,
    }
    return render(request, 'reception/print_patient.html', context)




@login_required
def patient_detail(request, patient_id):
    patient = get_object_or_404(
        Patient.objects.select_related('insurance_info'),
        id=patient_id,
    )

    orders_qs = (
        Order.objects.filter(patient=patient)
        .select_related('invoice')
        .prefetch_related('items__service', 'items__designs__design')
        .order_by('-created_at')
    )

    invoices = (
        OrderInvoice.objects
        .filter(order__patient=patient)
        .select_related('order', 'order__patient', 'issued_by')
        .order_by('-issued_at')
    )

    orders = list(orders_qs)

    for order in orders:
        is_final = order.status != 'draft'
        order.pending_workshop_items = [
            item for item in order.items.all()
            if is_final and item.status == 'pending' and item.send_to == 'workshop'
        ]
        order.pending_supplier_items = [
            item for item in order.items.all()
            if is_final and item.status == 'pending' and item.send_to == 'manufacturer'
        ]

    examinations_qs = (
        patient.examinations
        .all()
        .prefetch_related(
            Prefetch(
                'orders',
                queryset=Order.objects.order_by('-created_at').prefetch_related(
                    'items__service',
                    'items__designs__design',
                )
            )
        )
        .order_by('-created_at')
    )

    examinations = list(examinations_qs)
    for exam in examinations:
        exam_orders = list(exam.orders.all())
        exam.measurement_order = next(
            (o for o in exam_orders
             if o.status == 'draft' and o.measurement_status != 'none'), None)
        exam.can_request_measurement = (
            bool(exam.prescription_services)
            and exam.measurement_order is None
            and all(o.status in ('draft', 'cancelled') for o in exam_orders)
        )

    latest_exam = examinations[0] if examinations else None

    related_patients = patient.get_related_patients()
    insurance_info = getattr(patient, 'insurance_info', None)
    documents = patient.documents.all().order_by('-uploaded_at')

    # --- بخش مالی ---
    all_payments = (
        Payment.objects.filter(order__patient=patient)
        .select_related(
            'order',
            'account',
            'received_by',
        )
        .order_by('-paid_at')
    )

    total_orders_price = (
        orders_qs.aggregate(total=Sum('total_price'))['total']
        or Decimal('0')
    )

    total_paid = (
        all_payments.aggregate(total=Sum('amount'))['total']
        or Decimal('0')
    )

    total_remaining = total_orders_price - total_paid

    if total_remaining < 0:
        total_remaining = Decimal('0')

    total_overdue = Decimal('0')

    for order in orders_qs.filter(
        status='delivered'
    ).exclude(
        payment_status='paid'
    ):
        total_overdue += order.remaining_amount

    def fmt(value):
        try:
            return '{:,}'.format(int(float(value)))
        except (ValueError, TypeError):
            return '0'

    context = {
        'patient': patient,
        'orders': orders,
        'invoices': invoices,
        'examinations': examinations,
        'latest_exam': latest_exam,
        'related_patients': related_patients,
        'documents': documents,
        'payment_methods': PaymentMethod.choices,
        'payment_accounts': PaymentAccount.objects.filter(is_active=True),
        'payments': all_payments,
        'total_paid_formatted': fmt(total_paid),
        'total_remaining_formatted': fmt(total_remaining),
        'total_overdue_formatted': fmt(total_overdue),
        'is_manager': is_manager(request.user),
        'insurance_info': insurance_info,
    }

    return render(
        request,
        'reception/patient_detail.html',
        context,
    )

@login_required
@group_required('Reception')
@require_POST   
def delete_patient(request, patient_id):
    # دریافت بیمار با استفاده از شناسه یا بازگرداندن خطای 404 در صورت عدم وجود
    patient = get_object_or_404(Patient, id=patient_id)
    
    # ذخیره نام بیمار برای نمایش در پیام (اختیاری)
    patient_name = f"{patient.first_name} {patient.last_name}"
    
    # حذف بیمار
    patient.delete()
    
    # ارسال پیام موفقیت به قالب
    messages.success(request, f'پرونده بیمار "{patient_name}" با موفقیت حذف شد.')
    
    # هدایت کاربر به صفحه داشبورد یا لیست بیماران
    return redirect('reception:dashboard')

@group_required('Reception')
@login_required
def upload_patient_document(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)

    if request.method == 'POST':
        documents = request.FILES.getlist('documents')
        description = request.POST.get('description', '').strip()

        if not documents:
            messages.error(request, 'لطفاً حداقل یک فایل برای آپلود انتخاب کنید.')
            return redirect('reception:patient-detail', patient_id=patient.id)

        for doc in documents:
            Document.objects.create(
                patient=patient,
                file=doc,
                description=description if description else doc.name,
                uploaded_by=request.user
            )

        messages.success(request, 'مدارک جدید با موفقیت بارگذاری شد.')
        return redirect('reception:patient-detail', patient_id=patient.id)

    return redirect('reception:patient-detail', patient_id=patient.id)


def sync_patient_attachments(patient, attached_patient_ids, user=None):
    cleaned_ids = []

    for item_id in attached_patient_ids:
        try:
            item_id = int(item_id)
        except (TypeError, ValueError):
            continue

        if item_id == patient.id:
            continue

        cleaned_ids.append(item_id)

    cleaned_ids = list(set(cleaned_ids))

    valid_patients = Patient.objects.filter(
        id__in=cleaned_ids,
        is_active=True,
    ).exclude(
        id=patient.id,
    )

    valid_ids = set(valid_patients.values_list('id', flat=True))

    # حذف پیوست‌هایی که قبلاً بوده‌اند اما حالا از select برداشته شده‌اند
    current_attachments = PatientAttachment.objects.filter(
        Q(from_patient=patient) | Q(to_patient=patient)
    )

    for attachment in current_attachments:
        other_patient_id = (
            attachment.to_patient_id
            if attachment.from_patient_id == patient.id
            else attachment.from_patient_id
        )

        if other_patient_id not in valid_ids:
            attachment.delete()

    # ایجاد پیوست‌های جدید
    for related_patient_id in valid_ids:
        exists_direct = PatientAttachment.objects.filter(
            from_patient_id=patient.id,
            to_patient_id=related_patient_id,
        ).exists()

        exists_reverse = PatientAttachment.objects.filter(
            from_patient_id=related_patient_id,
            to_patient_id=patient.id,
        ).exists()

        if not exists_direct and not exists_reverse:
            PatientAttachment.objects.create(
                from_patient_id=patient.id,
                to_patient_id=related_patient_id,
                created_by=user if user and user.is_authenticated else None,
            )



def parse_jalali_date_or_none(raw_date):
    if not raw_date:
        return None

    clean_date = standardize_persian_date(raw_date)

    if not clean_date:
        return None

    try:
        normalized_date = clean_date.replace('-', '/')
        year, month, day = map(int, normalized_date.split('/'))
        return jdatetime.date(year, month, day).togregorian()
    except Exception as e:
        print(f"error parsing jalali date: {e}")
        return None



def save_patient_insurance_info(patient, request):
    insurance_fields = [
        'primary_insurance_type',
        'primary_insurance_provider',
        'insurance_number',
        'insurance_tracking_code',
        'has_supplementary_insurance',
        'supplementary_insurance_provider',
        'supplementary_insurance_number',
        'policy_holder_name',
        'policy_holder_relation',
        'insurance_notes',
    ]

    has_any_insurance_data = any(
        request.POST.get(field) for field in insurance_fields
    ) or request.POST.get('primary_insurance_expiry_date') \
      or request.POST.get('supplementary_coverage_limit') \
      or request.POST.get('insurance_deductible_percent')

    # اگر هیچ چیزی وارد نشده، در ایجاد بیمار مدل بیمه نساز
    # اما در ویرایش، اگر قبلاً وجود دارد می‌توانیم آن را خالی‌سازی کنیم یا نگه داریم.
    if not has_any_insurance_data and not hasattr(patient, 'insurance_info'):
        return None

    insurance_info, created = PatientInsuranceInfo.objects.get_or_create(
        patient=patient
    )

    insurance_info.primary_insurance_type = request.POST.get('primary_insurance_type') or None
    insurance_info.primary_insurance_provider = request.POST.get('primary_insurance_provider') or None
    insurance_info.insurance_number = request.POST.get('insurance_number') or None
    insurance_info.insurance_tracking_code = request.POST.get('insurance_tracking_code') or None

    insurance_info.primary_insurance_expiry_date = parse_jalali_date_or_none(
        request.POST.get('primary_insurance_expiry_date')
    )

    insurance_info.has_supplementary_insurance = request.POST.get('has_supplementary_insurance') or None
    insurance_info.supplementary_insurance_provider = request.POST.get('supplementary_insurance_provider') or None
    insurance_info.supplementary_insurance_number = request.POST.get('supplementary_insurance_number') or None

    insurance_info.policy_holder_name = request.POST.get('policy_holder_name') or None
    insurance_info.policy_holder_relation = request.POST.get('policy_holder_relation') or None

    coverage_limit = request.POST.get('supplementary_coverage_limit')
    if coverage_limit:
        try:
            coverage_limit = coverage_limit.replace(',', '').strip()
            insurance_info.supplementary_coverage_limit = Decimal(coverage_limit)
        except Exception:
            insurance_info.supplementary_coverage_limit = None
    else:
        insurance_info.supplementary_coverage_limit = None

    deductible_percent = request.POST.get('insurance_deductible_percent')
    if deductible_percent:
        try:
            insurance_info.insurance_deductible_percent = int(deductible_percent)
        except Exception:
            insurance_info.insurance_deductible_percent = None
    else:
        insurance_info.insurance_deductible_percent = None

    insurance_info.insurance_notes = request.POST.get('insurance_notes') or None

    insurance_info.save()
    return insurance_info





def process_dynamic_tags(request):
    # پردازش بیماری‌های زمینه‌ای
    new_diseases = request.POST.getlist('underlying_diseases')
    for disease_name in new_diseases:
        if disease_name:
            UnderlyingDisease.objects.get_or_create(name=disease_name)
    
    # پردازش سوابق ارتوتیک
    new_orthotics = request.POST.getlist('orthotic_history')
    for orthotic_name in new_orthotics:
        if orthotic_name:
            OrthoticHistoryType.objects.get_or_create(name=orthotic_name)