# reception/models/orders.py
from django.db import models, transaction, IntegrityError
from .patient import TimeStampedModel, Patient
from .services import Design, ServiceSizePrice, Services, ServiceVariant
from .examination import Examination
from django.db.models import Sum, F
from django.contrib.auth.models import User
from django.core.serializers.json import DjangoJSONEncoder
from decimal import Decimal, InvalidOperation
from django.shortcuts import  get_object_or_404
from django.utils import timezone
import jdatetime
from datetime import datetime, date
from ..utils import normalize_digits

def normalize_delivery_date(value):
    """Convert Gregorian/Jalali delivery-date values to datetime.date."""
    if not value:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if not isinstance(value, str):
        return None

    value = value.strip()
    if not value:
        return None

    # Normalize Persian and Arabic digits.
    value = value.translate(
        str.maketrans(
            '۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩',
            '01234567890123456789',
        )
    )

    normalized_value = value.replace('-', '/')

    try:
        year, month, day = map(int, normalized_value.split('/'))
    except (TypeError, ValueError):
        return None

    try:
        # Years in this range are expected to be Jalali.
        if 1200 <= year <= 1600:
            return jdatetime.date(year, month, day).togregorian()

        return date(year, month, day)
    except (TypeError, ValueError, OverflowError):
        return None


def extract_foot_length(measurements):
    """طول پا از JSON اندازه‌گیری (در حالت چپ/راست، پای راست مرجع است)."""
    measurements = measurements or {}
    if measurements.get('different_sizes'):
        raw = (measurements.get('right') or {}).get('foot_length')
    else:
        raw = measurements.get('foot_length')
    if raw in (None, ''):
        return None
    try:
        return Decimal(normalize_digits(raw).replace('٫', '.'))
    except (InvalidOperation, ValueError, TypeError):
        return None
# =============================
# Order
# =============================

class Order(TimeStampedModel):
    PRIORITY_CHOICES = [
        ('normal', 'عادی'),
        ('fast', 'فوری'),
        ('urgent', 'اورژانسی'),
    ]
    
    STATUS_CHOICES = (
        ("draft", "پیش‌نویس"),
        ("awaiting", "در انتظار پرداخت"),
        ("confirmed", "تایید شده"),
        ("manufacturing", "در حال ساخت"),
        ("ready", "آماده تحویل"),
        ("delivered", "تحویل داده شده"),
        ("cancelled", "لغو شده"),
    )

    PAYMENT_STATUS_CHOICES = (
        ("unpaid", "پرداخت نشده"),
        ("paid", "پرداخت شده"),
        ("partial", "جزئی پرداخت شده"),
    )
    
    
    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT, related_name="orders"
    )

    order_date = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name="تاریخ ثبت سفارش"
    )
    
    examination = models.ForeignKey(
        Examination, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="orders"
    )

    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    
    # وضعیت پرداخت
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default="unpaid", db_index=True
    )

    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    delivered_at = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_orders')
    ready_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ready_orders')
    delivered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='delivered_orders')

    # یادداشت‌ها
    notes = models.TextField(blank=True, verbose_name="یادداشت سفارش")           # یادداشت عمومی
    workshop_notes = models.TextField(blank=True, verbose_name="یادداشت کارگاه")
    general_notes = models.TextField(blank=True, verbose_name="یادداشت کلی")     # از wizard

    def __str__(self):
        return f"Order #{self.id} - {self.patient}"

    def recalculate_total(self):
        items_total = sum(
            (i.price_at_order - i.discount) * i.quantity
            for i in self.items.all()
        )
        design_total = self.design_items.aggregate(
            total=Sum(F("price_at_order") * F("quantity"))
        )["total"] or Decimal('0')

        self.total_price = max(Decimal('0'), items_total + design_total - self.discount)
        self.save(update_fields=["total_price"])

    
    @property
    def formatted_total(self):
        try:
            # تبدیل به عدد صحیح برای حذف اعشار و استفاده از فرمت‌بندی پایتون برای جداکننده
            return "{:,}".format(int(float(self.total_price)))
        except (ValueError, TypeError):
            return self.total_price
        

    @property
    def total_paid(self):
        return self.payments.aggregate(total=Sum("amount"))["total"] or Decimal('0')

    @property
    def formatted_total_paid(self):
        try:
            return "{:,}".format(int(float(self.total_paid)))
        except (ValueError, TypeError):
            return "0"

    @property
    def remaining_amount(self):
        remaining = self.total_price - self.total_paid
        return remaining if remaining > 0 else Decimal('0')

    @property
    def formatted_remaining(self):
        try:
            return "{:,}".format(int(float(self.remaining_amount)))
        except (ValueError, TypeError):
            return "0"

    @property
    def suggested_deposit(self):
        """بیعانه پیشنهادی: ۷۰٪ مبلغ کل سفارش"""
        try:
            return (self.total_price * Decimal('0.7')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        except Exception:
            return Decimal('0')
    @property
    def formatted_suggested_deposit(self):
        try:
            return "{:,}".format(int(self.suggested_deposit))
        except (ValueError, TypeError):
            return "0"
        
    def update_payment_status(self):
        """محاسبه خودکار وضعیت پرداخت بر اساس مجموع پرداخت‌ها"""
        paid = self.total_paid
        if paid <= 0:
            self.payment_status = 'unpaid'
        elif paid >= self.total_price:
            self.payment_status = 'paid'
        else:
            self.payment_status = 'partial'
        self.save(update_fields=["payment_status"])
    
    def _delivery_badge_from_items(self, items):
        dated_items = []

        for item in items:
            if item.status in ('delivered', 'cancelled'):
                continue

            delivery_date = normalize_delivery_date(item.delivery_date)
            if delivery_date is None:
                continue

            dated_items.append((delivery_date, item))

        if not dated_items:
            return None

        _, nearest_item = min(
            dated_items,
            key=lambda pair: pair[0],
        )

        return nearest_item.delivery_badge


    @property
    def delivery_badge(self):
        items = getattr(self, 'workshop_items', None)

        if items is None:
            items = self.items.all()

        return self._delivery_badge_from_items(items)




    
# =============================
# Order Item
# =============================

class OrderItem(TimeStampedModel):

    ITEM_STATUS_CHOICES = (
        ("draft", "پیش‌نویس"),
        ("pending", "در انتظار"),

        ("workshop_queue", "در صف کارگاه"),
        ("manufacturing", "در حال ساخت"),

        ("pending_supplier_registration", "در انتظار ثبت برای تولیدکننده"),
        ("awaiting_supplier", "در انتظار دریافت از تولیدکننده"),
        ("received_from_supplier", "دریافت‌شده از تولیدکننده"),

        ("ready_for_fitting", "آماده پرو"),
        ("fitting_completed", "پرو انجام شد"),

        ("qc_pending", "در انتظار کنترل کیفیت"),
        ("needs_revision", "نیازمند اصلاح"),
        ("qc_approved", "تأیید کنترل کیفیت"),

        ("ready", "آماده تحویل"),
        ("delivered", "تحویل داده شده"),
        ("cancelled", "لغو شده"),
    )

    PRIORITY_CHOICES = (
        ("normal", "عادی"),
        ("fast", "فوری"),
        ("urgent", "اورژانسی"),
    )

    SEND_TO_CHOICES = (
        ('manufacturer', 'سفارش به تولیدکننده'),
        ('workshop', 'تولید یا تکمیل در کارگاه'),
    )

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    service = models.ForeignKey(Services, on_delete=models.PROTECT)
    variant = models.ForeignKey(ServiceVariant, on_delete=models.SET_NULL, null=True, blank=True)

    quantity = models.PositiveIntegerField(default=1)

    foot_length = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    measurements = models.JSONField(default=dict, blank=True, encoder=DjangoJSONEncoder)
    dynamic_fields = models.JSONField(default=dict, blank=True, encoder=DjangoJSONEncoder)

    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='normal',
        verbose_name="اولویت"
    )

    delivery_date = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        verbose_name="تاریخ تقریبی تحویل"
    )
    
    expected_delivery_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="تاریخ تقریبی آماده‌سازی"
    )

    delivered_at = models.DateField(
        null=True,
        blank=True,
        verbose_name="تاریخ تحویل واقعی آیتم"
    )

    delivered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivered_order_items",
        verbose_name="تحویل‌دهنده آیتم"
    )
    # delivered_at = models.DateField(
    #     null=True,
    #     blank=True,
    #     verbose_name="تاریخ تحویل واقعی آیتم"
    # )
    
    price_at_order = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_at_order = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    send_to = models.CharField(
        max_length=50,
        choices=SEND_TO_CHOICES,
        default='manufacturer',
        verbose_name='نوع سفارش'
    )

    status = models.CharField(max_length=40, choices=ITEM_STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)

    SPECS_STATUS_CHOICES = (
        ("pending", "در انتظار تکمیل مشخصات"),
        ("completed", "مشخصات تکمیل شد"),
    )
    specs_status = models.CharField(
        max_length=20, choices=SPECS_STATUS_CHOICES, default="pending",
        db_index=True, verbose_name="وضعیت مشخصات",
    )
    specs_completed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="specs_completed_items", verbose_name="تکمیل‌کننده مشخصات",
    )
    specs_completed_at = models.DateTimeField(null=True, blank=True)

    @property
    def suggested_size_price(self):
        """قیمت جدول سایز بر اساس طول پای ثبت‌شده؛ None اگر قابل محاسبه نباشد."""
        if not getattr(self.service, 'has_size', False) or not self.foot_length:
            return None
        size_price = ServiceSizePrice.find_price(
            service=self.service, foot_length=self.foot_length, variant=self.variant
        )
        return size_price.price if size_price else None
    
    def calculate_price(self):
        if not self.service or not getattr(self.service, 'has_size', False) or not self.foot_length:
            return

        size_price = ServiceSizePrice.find_price(
            service=self.service,
            foot_length=self.foot_length,
            variant=self.variant
        )

        if size_price:
            self.price_at_order = size_price.price
            self.cost_at_order = size_price.cost
        
            
        
    @property
    def formatted_discount(self):
        try:
            return "{:,}".format(int(float(self.discount)))
        except (ValueError, TypeError):
            return self.discount
        
        
    @property
    def designs_total_price(self):
        """محاسبه مجموع قیمت طراحی‌های مرتبط با همین آیتم (قیمت × تعداد)"""
        # با فرض اینکه related_name در مدل OrderItemDesign برابر 'designs' تنظیم شده باشد
        return sum(design.price_at_order * design.quantity for design in self.designs.all())

    @property
    def formatted_designs_total(self):
        """نمایش فرمت‌شده مجموع هزینه طراحی‌های این آیتم"""
        try:
            return "{:,}".format(int(float(self.designs_total_price)))
        except (ValueError, TypeError):
            return "0"

    @property
    def formatted_price(self):
        """نمایش فرمت‌شده قیمت واحد آیتم"""
        try:
            return "{:,}".format(int(float(self.price_at_order)))
        except (ValueError, TypeError):
            return self.price_at_order
        
    @property
    def formatted_item_total(self):
        """
        محاسبه قیمت کل این آیتم:
        (قیمت واحد × تعداد) + (مجموع قیمت طراحی‌های این آیتم)
        """
        try:
            base_total = self.price_at_order * self.quantity
            final_total = base_total + self.designs_total_price
            return "{:,}".format(int(float(final_total)))
        except (ValueError, TypeError):
            return "0"
        
    @property
    def delivery_badge(self):
        """
        Return a delivery badge based on this item's approximate delivery date.
        """
        if self.status in ('delivered', 'cancelled'):
            return None

        delivery_date = normalize_delivery_date(self.delivery_date)
        if delivery_date is None:
            return None

        delta = (delivery_date - timezone.localdate()).days

        if delta < 0:
            return {
                'label': f'{abs(delta)} روز تاخیر',
                'css_class': 'bg-danger',
            }

        if delta == 0:
            return {
                'label': 'موعد امروز',
                'css_class': 'bg-warning text-dark',
            }

        if delta == 1:
            return {
                'label': 'تحویل فردا',
                'css_class': 'bg-warning text-dark',
            }

        if delta <= 2:
            return {
                'label': f'{delta} روز مانده',
                'css_class': 'bg-info text-dark',
            }

        return {
            'label': f'{delta} روز مانده',
            'css_class': 'bg-secondary',
        }


# =============================
# Order Item Designs
# =============================

class OrderItemDesign(TimeStampedModel):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="design_items",
        null=True,
        blank=True
    )

    order_item = models.ForeignKey(
        'OrderItem',
        on_delete=models.CASCADE,
        related_name="designs",
        null=True,
        blank=True
    )

    design = models.ForeignKey(
        Design,
        on_delete=models.PROTECT
    )

    quantity = models.PositiveIntegerField(default=1)

    price_at_order = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_at_order = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    side = models.CharField(max_length=10, blank=True, null=True, choices=[('left', 'چپ'), ('right', 'راست')])

    def __str__(self):
        return f"{self.design} x {self.quantity}"

# =============================
# OrderService (نسخه نهایی)
# =============================
class OrderService:
    PRIORITY_RANK = {'normal': 0, 'fast': 1, 'urgent': 2}
    # فقط آیتم‌هایی که هنوز به کارگاه/تامین‌کننده نرفته‌اند قابل تغییر کامل/حذف‌اند
    REMOVABLE_STATUSES = ('draft', 'pending')

    @staticmethod
    def _dec(value):
        if value in (None, ''):
            return Decimal('0')
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError('مقدار عددی نامعتبر است.')

    @staticmethod
    def _parse_order_datetime(raw_order_date):
        order_datetime = timezone.now()
        raw_order_date = (raw_order_date or '').strip()
        if not raw_order_date:
            return order_datetime
        try:
            table = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
            year, month, day = map(int, raw_order_date.translate(table).replace('-', '/').split('/'))
            now_time = timezone.localtime()
            gregorian_dt = jdatetime.datetime(
                year, month, day, now_time.hour, now_time.minute, now_time.second
            ).togregorian()
            return timezone.make_aware(gregorian_dt) if timezone.is_naive(gregorian_dt) else gregorian_dt
        except Exception:
            return order_datetime

    @classmethod
    @transaction.atomic
    def create_or_update_from_wizard(cls, order_data, is_draft=True):
        patient = order_data['patient']
        exam = order_data.get('examination')
        items_data = order_data.get('items', []) or []
        order_datetime = cls._parse_order_datetime(order_data.get('order_date'))

        # آیتم بدون سرویس: در پیش‌نویس نادیده گرفته می‌شود، در ثبت نهایی خطا
        valid_items = []
        for idx, item in enumerate(items_data, start=1):
            if item.get('service_id'):
                valid_items.append(item)
            elif not is_draft:
                raise ValueError(f'برای قلم شماره {idx} سرویس انتخاب نشده است.')

        # اولویت سفارش = بالاترین اولویت آیتم‌ها
        priority = max(
            (i.get('priority') or 'normal' for i in valid_items),
            key=lambda p: cls.PRIORITY_RANK.get(p, 0),
            default='normal',
        )

        existing_order_id = order_data.get('order_id') or order_data.get('draft_order_id')

        if existing_order_id:
            order = Order.objects.select_for_update().get(id=existing_order_id)
            order.priority = priority
            order.general_notes = order_data.get('general_notes', '')
            order.order_date = order_datetime
            if order.status == 'draft':
                order.status = 'draft' if is_draft else 'awaiting'
            order.save()
            existing_items = {i.id: i for i in order.items.select_related('service')}
            old_total = order.total_price
            invoiced = OrderInvoice.objects.filter(order=order).exists()
        else:
            order = Order.objects.create(
                patient=patient,
                examination=exam,
                order_date=order_datetime,
                priority=priority,
                general_notes=order_data.get('general_notes', ''),
                status='draft' if is_draft else 'awaiting',
                payment_status='unpaid',
                created_by=order_data.get('created_by'),
            )
            existing_items = {}
            old_total, invoiced = None, False
        kept_ids = set()

        for item in valid_items:
            service = get_object_or_404(Services, id=item['service_id'])

            quantity = max(1, int(item.get('quantity') or 1))
            unit_price = cls._dec(item.get('unit_price'))
            discount = cls._dec(item.get('discount'))
            designs = [d for d in (item.get('designs') or []) if d.get('design_id')]
            designs_unit_total = sum((cls._dec(d.get('price')) for d in designs), Decimal('0'))

            if unit_price < 0 or discount < 0:
                raise ValueError('قیمت و تخفیف نمی‌توانند منفی باشند.')
            if discount > unit_price + designs_unit_total:
                raise ValueError(f'تخفیف قلم «{service.name}» از قیمت آن بیشتر است.')

            raw_id = str(item.get('item_id') or '')
            order_item = existing_items.get(int(raw_id)) if raw_id.isdigit() else None

            # آیتمی که به کارگاه/تامین‌کننده رفته: پذیرش فقط بخش مالی را می‌تواند تغییر دهد
            if order_item and order_item.status not in cls.REMOVABLE_STATUSES:
                order_item.price_at_order = unit_price
                order_item.discount = discount
                order_item.save(update_fields=['price_at_order', 'discount', 'updated_at'])
                kept_ids.add(order_item.id)
                continue

            measurements = item.get('measurements', {}) or {}
            foot_length = extract_foot_length(measurements)

            if order_item and order_item.specs_status == 'completed':
                if order_item.service_id != service.id:
                    raise ValueError(
                        f'مشخصات قلم «{order_item.service.name}» تایید شده و سرویس آن قابل تغییر نیست.'
                    )
                # پذیرش نمی‌تواند مشخصات تاییدشده توسط کارگاه را عوض کند
                fields['measurements'] = order_item.measurements
                fields['dynamic_fields'] = order_item.dynamic_fields
                fields['foot_length'] = order_item.foot_length
                
            delivery_date = item.get('delivery_date') or None
            fields = dict(
                service=service,
                quantity=quantity,
                foot_length=foot_length,
                measurements=measurements,
                dynamic_fields=item.get('dynamic_fields', {}) or {},
                price_at_order=unit_price,
                discount=discount,
                send_to=item.get('send_to', 'manufacturer'),
                priority=item.get('priority', 'normal'),
                delivery_date=delivery_date,
                expected_delivery_date=normalize_delivery_date(delivery_date),
                notes=item.get('notes', ''),
            )

            if order_item:
                for key, value in fields.items():
                    setattr(order_item, key, value)
                order_item.save()
                order_item.designs.all().delete()
            else:
                has_schema = service.measurements.exists() or service.dynamic_fields.exists()
                order_item = OrderItem.objects.create(
                    order=order, status='pending',
                    specs_status='pending' if has_schema else 'completed',
                    **fields,
                )

            # قیمت جدول سایز فقط وقتی اعمال می‌شود که پذیرش قیمتی وارد نکرده باشد
            if order_item.price_at_order == 0:
                order_item.calculate_price()
                order_item.save(update_fields=['price_at_order', 'cost_at_order', 'updated_at'])

            for d in designs:
                design = Design.objects.filter(id=d['design_id']).first()
                if design:
                    OrderItemDesign.objects.create(
                        order=order,
                        order_item=order_item,
                        design=design,
                        quantity=quantity,
                        price_at_order=cls._dec(d.get('price')),
                        side=d.get('side'),
                    )

            kept_ids.add(order_item.id)

        # آیتم‌هایی که از ویزارد حذف شده‌اند
        for item_id, old in existing_items.items():
            if item_id in kept_ids:
                continue
            if old.status in cls.REMOVABLE_STATUSES:
                old.delete()
            else:
                raise ValueError(
                    f'قلم «{old.service.name}» به کارگاه/تامین‌کننده ارسال شده و قابل حذف نیست.'
                )

        order.recalculate_total()
        if invoiced and order.total_price != old_total:
            raise ValueError(
                'برای این سفارش فاکتور صادر شده و تغییر مبلغ آن مجاز نیست.'
            )
        order.update_payment_status()
        return order


# =============================
# Technician
# =============================

class Technician(TimeStampedModel):

    name = models.CharField(max_length=200)

    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    specialization = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


# =============================
# Casting / 3D Scan
# =============================

class PatientScan(TimeStampedModel):

    SCAN_TYPE_CHOICES = (
        ("casting", "Casting"),
        ("3d_scan", "3D Scan"),
        ("foam_box", "Foam Box"),
    )

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="scans"
    )

    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scans"
    )

    scan_type = models.CharField(
        max_length=20,
        choices=SCAN_TYPE_CHOICES
    )

    file = models.FileField(
        upload_to="patient_scans/",
        blank=True,
        null=True
    )

    notes = models.TextField(
        blank=True,
        null=True
    )

    technician = models.ForeignKey(
        Technician,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.patient} - {self.scan_type}"


from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP

class PaymentMethod(models.TextChoices):
    CASH = 'cash', 'نقدی'
    POS = 'pos', 'کارتخوان (POS)'
    CARD_TO_CARD = 'card_to_card', 'کارت به کارت'
    ONLINE = 'online', 'پرداخت آنلاین (درگاه)'
    SNAPP_PAY = 'snapp_pay', 'اسنپ‌پی'
    DIGI_PAY = 'digi_pay', 'دیجی‌پی'
    INSURANCE = 'insurance', 'بیمه (کسر از بیمه)'
    OTHER = 'other', 'سایر'


class PaymentAccount(TimeStampedModel):
    """حساب‌های مرتبط با هر روش پرداخت (مثلاً چند دستگاه POS یا چند شماره‌کارت)"""
    name = models.CharField(max_length=100, verbose_name="نام حساب/دستگاه")
    method = models.CharField(max_length=20, choices=PaymentMethod.choices, verbose_name="روش پرداخت مرتبط")
    account_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="شماره حساب/کارت/ترمینال")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['method', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_method_display()})"


class Payment(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    account = models.ForeignKey(PaymentAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    reference_number = models.CharField(max_length=100, blank=True, null=True, verbose_name="شماره پیگیری/مرجع")
    paid_at = models.DateTimeField(default=timezone.now, verbose_name="تاریخ پرداخت")
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_payments')
    edited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='edited_payments')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-paid_at']

    def __str__(self):
        return f"پرداخت {self.amount} - سفارش #{self.order_id}"

    @property
    def formatted_amount(self):
        try:
            return "{:,}".format(int(float(self.amount)))
        except (ValueError, TypeError):
            return self.amount
        
        
class OrderInvoice(TimeStampedModel):
    order = models.OneToOneField(
        Order,
        on_delete=models.PROTECT,
        related_name='invoice',
        verbose_name='سفارش',
    )

    invoice_number = models.CharField(
        max_length=12,
        unique=True,
        db_index=True,
        verbose_name='شماره فاکتور',
    )

    jalali_date = models.CharField(
        max_length=8,
        db_index=True,
        verbose_name='تاریخ شمسی صدور',
    )

    daily_sequence = models.PositiveIntegerField(
        verbose_name='شماره روزانه',
    )

    issued_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issued_order_invoices',
        verbose_name='صادرکننده',
    )

    issued_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name='زمان صدور',
    )

    class Meta:
        verbose_name = 'فاکتور سفارش'
        verbose_name_plural = 'فاکتورهای سفارش'
        constraints = [
            models.UniqueConstraint(
                fields=['jalali_date', 'daily_sequence'],
                name='unique_order_invoice_daily_sequence',
            ),
        ]

    def __str__(self):
        return self.invoice_number

    @classmethod
    def issue_for_order(cls, order, user=None):
        existing = getattr(order, 'invoice', None)
        if existing:
            return existing, False

        now = timezone.localtime()
        jalali_now = jdatetime.datetime.fromgregorian(datetime=now)
        jalali_date = jalali_now.strftime('%Y%m%d')

        for _ in range(3):
            try:
                with transaction.atomic():
                    last_invoice = (
                        cls.objects
                        .select_for_update()
                        .filter(jalali_date=jalali_date)
                        .order_by('-daily_sequence')
                        .first()
                    )

                    next_sequence = (
                        last_invoice.daily_sequence + 1
                        if last_invoice
                        else 1
                    )

                    invoice = cls.objects.create(
                        order=order,
                        invoice_number=f'{jalali_date}{next_sequence:04d}',
                        jalali_date=jalali_date,
                        daily_sequence=next_sequence,
                        issued_by=user if user and user.is_authenticated else None,
                        issued_at=now,
                    )

                    return invoice, True

            except IntegrityError:
                continue

        return cls.objects.get(order=order), False