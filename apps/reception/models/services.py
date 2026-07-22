# reception/models/services.py
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import UniqueConstraint, Index
from .patient import TimeStampedModel, SoftDeleteModel

# =============================
# Service Categories
# =============================


class ServicesCategory(TimeStampedModel, SoftDeleteModel):

    name = models.CharField(max_length=200)

    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class ServiceSubCategory(TimeStampedModel, SoftDeleteModel):

    category = models.ForeignKey(
        ServicesCategory,
        on_delete=models.CASCADE,
        related_name="subcategories"
    )

    name = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.category.name} - {self.name}"


# =============================
# Services
# =============================

class Services(TimeStampedModel, SoftDeleteModel):

    category = models.ForeignKey(
        ServicesCategory,
        on_delete=models.PROTECT,
        related_name="services"
    )

    subcategory = models.ForeignKey(
        ServiceSubCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="services"
    )

    name = models.CharField(max_length=200)

    description = models.TextField(blank=True)

    has_size = models.BooleanField(
        default=False,
        help_text="If true, price is determined by size table"
    )

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    base_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    def __str__(self):
        return self.name


# =============================
# Service Variant
# =============================

class ServiceVariant(TimeStampedModel, SoftDeleteModel):

    service = models.ForeignKey(
        Services,
        on_delete=models.CASCADE,
        related_name="variants"
    )

    name = models.CharField(max_length=200)

    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.service.name} - {self.name}"

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["service", "name"],
                name="unique_variant_per_service"
            )
        ]


# =============================
# Size Based Pricing
# =============================

class ServiceSizePrice(TimeStampedModel):

    service = models.ForeignKey(
        Services,
        on_delete=models.CASCADE,
        related_name="size_prices"
    )

    variant = models.ForeignKey(
        ServiceVariant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="size_prices"
    )

    foot_length_min = models.DecimalField(max_digits=5, decimal_places=2)

    foot_length_max = models.DecimalField(max_digits=5, decimal_places=2)

    price = models.DecimalField(max_digits=10, decimal_places=2)

    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        indexes = [
            Index(fields=["service"]),
        ]

    def clean(self):
        overlapping = ServiceSizePrice.objects.filter(
            service=self.service,
            variant=self.variant,
            foot_length_min__lt=self.foot_length_max,
            foot_length_max__gt=self.foot_length_min
        ).exclude(id=self.id)

        if overlapping.exists():
            raise ValidationError("Size price ranges overlap.")

    def __str__(self):
        return f"{self.service} ({self.foot_length_min}-{self.foot_length_max})"


# =============================
# Price Finder Helper
# =============================


    @classmethod
    def find_price(cls, service, foot_length, variant=None):

        qs = cls.objects.filter(service=service)

        if variant:
            qs = qs.filter(variant=variant)

        return qs.filter(
            foot_length_min__lte=foot_length,
            foot_length_max__gte=foot_length
        ).first()


# =============================
# Design Options
# =============================

class Design(TimeStampedModel, SoftDeleteModel):

    name = models.CharField(max_length=200)

    description = models.TextField(blank=True)

    priority = models.PositiveIntegerField(
        default=100,
        verbose_name="اولویت نمایش",
        help_text="عدد کمتر یعنی نمایش بالاتر در لیست"
    )
    
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    categories = models.ManyToManyField(
        ServicesCategory,
        blank=True,
        related_name="designs"
    )

    services = models.ManyToManyField(
        Services,
        blank=True,
        related_name="designs"
    )

    def __str__(self):
        return self.name


# =============================
# Dynamic Fields for Services
# =============================

class ServiceDynamicField(TimeStampedModel):
    FIELD_TYPES = (
        ('text', 'متن کوتاه'),
        ('number', 'عدد'),
        ('checkbox', 'چک‌باکس (بله/خیر)'),
        ('textarea', 'متن طولانی (توضیحات)'),
        ('select', 'دراپ‌داون (لیست کشویی)'),  # <--- آیتم جدید
    )

    service = models.ForeignKey(
        Services, # یا نام مدلی که سرویس‌های شما را نگه می‌دارد
        on_delete=models.CASCADE,
        related_name="dynamic_fields"
    )
    
    name = models.CharField(
        max_length=50, 
        help_text="نام انگلیسی فیلد برای دیتابیس (مثلاً material_type)"
    )
    
    label = models.CharField(
        max_length=100, 
        help_text="نام نمایشی برای کاربر (مثلاً نوع متریال)"
    )
    
    field_type = models.CharField(
        max_length=20, 
        choices=FIELD_TYPES, 
        default='text'
    )

    # <--- فیلد جدید برای ذخیره گزینه‌های دراپ‌داون
    dropdown_options = models.TextField(
        blank=True,
        null=True,
        verbose_name="گزینه‌های دراپ‌داون",
        help_text="فقط برای نوع دراپ‌داون: گزینه‌ها را با ویرگول انگلیسی (,) از هم جدا کنید. مثلاً: چرم,فوم,پلاستیک"
    )
    
    is_required = models.BooleanField(
        default=False, 
        verbose_name="اجباری است؟"
    )

    def __str__(self):
        return f"{self.service.name} - {self.label}"


# =============================
# Service Measurments
# =============================
class ServiceMeasurements(TimeStampedModel): # ترجیحا املا اصلاح شود
    FIELD_TYPES = (
        ('number', 'عدد'),
        ('checkbox', 'چک‌باکس (بله/خیر)'),
        ('textarea', 'متن طولانی (توضیحات)'),
        ('select', 'دراپ‌داون (لیست کشویی)'), 
    )

    service = models.ForeignKey(
        Services, 
        on_delete=models.CASCADE,
        related_name="measurements" # نام ساده‌تر برای ریلیشن
    )
    
    name = models.CharField(max_length=50, help_text="نام انگلیسی فیلد برای دیتابیس (مثلاً foot_length)")
    label = models.CharField(max_length=100, help_text="نام نمایشی برای کاربر (مثلاً طول پا)")
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES, default='number') # دیفالت اصلاح شد
    dropdown_options = models.TextField(blank=True, null=True, verbose_name="گزینه‌های دراپ‌داون")
    is_required = models.BooleanField(default=False, verbose_name="اجباری است؟")

    def __str__(self):
        return f"{self.service.name} - {self.label}"
