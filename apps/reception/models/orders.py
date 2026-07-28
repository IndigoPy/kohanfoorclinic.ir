# reception/models/orders.py
from django.db import models, transaction
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
        items_total = self.items.aggregate(
            total=Sum(F("price_at_order") * F("quantity"))
        )["total"] or 0

        design_total = self.design_items.aggregate(
            total=Sum(F("price_at_order") * F("quantity"))
        )["total"] or 0

        self.total_price = items_total + design_total - self.discount
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

    @staticmethod
    @transaction.atomic
    def create_or_update_from_wizard(order_data, is_draft=True):
        patient = order_data['patient']
        exam = order_data.get('examination')
        items_data = order_data.get('items', [])

        raw_order_date = (order_data.get('order_date') or '').strip()
        order_datetime = timezone.now()

        if raw_order_date:
            try:
                # پشتیبانی از اعداد فارسی/عربی
                translation_table = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
                raw_order_date = raw_order_date.translate(translation_table)

                year, month, day = map(int, raw_order_date.split('/'))

                # اگر فقط تاریخ مهم است، ساعت فعلی را می‌گذاریم
                now_time = timezone.localtime()
                gregorian_dt = jdatetime.datetime(
                    year,
                    month,
                    day,
                    now_time.hour,
                    now_time.minute,
                    now_time.second
                ).togregorian()

                order_datetime = timezone.make_aware(gregorian_dt) if timezone.is_naive(gregorian_dt) else gregorian_dt

            except Exception:
                order_datetime = timezone.now()

        
        # Order
        existing_order_id = order_data.get('order_id') or order_data.get('draft_order_id')

        if existing_order_id:
            order = Order.objects.get(id=existing_order_id)
            order.priority = order_data.get('priority', 'normal')
            order.general_notes = order_data.get('general_notes', '')
            order.order_date = order_datetime
            
            # مدیریت وضعیت: فقط اگر سفارش هنوز پیش‌نویس بود تغییر می‌کند
            # (سفارش تایید‌شده/در حال ساخت/آماده با ذخیره پیش‌نویس یا اتوسیو به عقب برنمی‌گردد)
            if order.status == 'draft':
                order.status = 'draft' if is_draft else 'awaiting'

            order.save()
            order.items.all().delete()
            order.design_items.all().delete()
        else:
            order = Order.objects.create(
                patient=patient,
                examination=exam,
                order_date=order_datetime,
                priority=order_data.get('priority', 'normal'),
                general_notes=order_data.get('general_notes', ''),
                status='draft' if is_draft else 'awaiting',
                payment_status='unpaid',
                created_by=order_data.get('created_by')
            )

        for item in items_data:
            service = get_object_or_404(Services, id=item['service_id'])
            measurements = item.get('measurements', {}) or {}

            # استخراج foot_length: در صورت متفاوت بودن اندازه چپ/راست، پای راست به عنوان مرجع قیمت‌گذاری استفاده می‌شود
            if measurements.get('different_sizes'):
                foot_length_val = (measurements.get('right') or {}).get('foot_length')
            else:
                foot_length_val = measurements.get('foot_length')

            try:
                foot_length = Decimal(str(foot_length_val)) if foot_length_val not in (None, '') else None
            except (InvalidOperation, ValueError, TypeError):
                foot_length = None
                
            order_item = OrderItem.objects.create(
                order=order,
                service=service,
                quantity=item.get('quantity', 1),
                foot_length=foot_length,
                measurements=measurements,
                dynamic_fields=item.get('dynamic_fields', {}),
                price_at_order=Decimal(str(item.get('unit_price', 0) or 0)),
                discount=Decimal(str(item.get('discount', 0) or 0)),
                send_to=item.get('send_to', 'manufacturer'),
                priority=item.get('priority', 'normal'),
                delivery_date=item.get('delivery_date') or None,
                status=item.get('status', 'pending'),
                notes=item.get('notes', '')
            )

            order_item.calculate_price()  # اگر service.has_size و foot_length موجود باشد، قیمت واقعی از ServiceSizePrice جایگزین می‌شود
            order_item.save()


            # طراحی‌ها
            for d in item.get('designs', []):
                if d.get('design_id'):
                    try:
                        design = Design.objects.get(id=d['design_id'])
                        OrderItemDesign.objects.create(
                            order=order,
                            order_item=order_item,
                            design=design,
                            quantity=item.get('quantity', 1),
                            price_at_order=Decimal(d.get('price', 0)),
                            side=d.get('side')
                        )
                    except Design.DoesNotExist:
                        pass

        order.recalculate_total()
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