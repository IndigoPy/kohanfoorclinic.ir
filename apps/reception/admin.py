from .models import ServiceDynamicField, Services  # ایمپورت‌های خود را چک کنید
from django.contrib import admin
from .models import *
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from .models.orders import PaymentAccount
from .models.patient import *

# User = get_user_model()
# admin.site.register(User)
# admin.site.register(Group)

# =============================
# Patient
# =============================

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "first_name",
        "last_name",
        "phone",
        "national_id",
        "stage",
        "created_at",
    )

    search_fields = (
        "first_name",
        "last_name",
        "phone",
        "national_id",
    )

    list_filter = (
        "stage",
        "created_at",
    )


# =============================
# Services
# =============================

admin.site.register(ServicesCategory)


class ServicesCategoryAdmin(admin.ModelAdmin):

    search_fields = ("name",)


admin.site.register(ServiceSubCategory)


class ServiceSubCategoryAdmin(admin.ModelAdmin):

    search_fields = ("name",)
    list_filter = ("category",)


admin.site.register(Services)


class ServicesAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "category",
        "has_size",
        "unit_price",
        "base_cost",
    )

    search_fields = ("name",)

    list_filter = (
        "category",
        "has_size",
    )


admin.site.register(ServiceVariant)


class ServiceVariantAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "service",
    )

    search_fields = ("name",)

    list_filter = ("service",)


admin.site.register(ServiceSizePrice)


class ServiceSizePriceAdmin(admin.ModelAdmin):

    list_display = (
        "service",
        "variant",
        "foot_length_min",
        "foot_length_max",
        "price",
    )

    list_filter = ("service",)


admin.site.register(ServiceDynamicField)


class ServiceDynamicFieldAdmin(admin.ModelAdmin):
    list_display = ('label', 'name', 'service', 'field_type', 'is_required')
    list_filter = ('service', 'field_type', 'is_required')
    search_fields = ('name', 'label', 'service__name')
    # اگر سرویس‌ها زیاد هستند، جستجو را راحت می‌کند
    autocomplete_fields = ['service']

    # برای زیبایی، فیلدها را در فرم ادمین گروه‌بندی می‌کنیم
    fieldsets = (
        ('اطلاعات پایه', {
            'fields': ('service', 'name', 'label', 'is_required')
        }),
        ('نوع فیلد و مقادیر', {
            'fields': ('field_type', 'dropdown_options'),
            'description': 'اگر نوع فیلد را دراپ‌داون انتخاب کردید، حتماً گزینه‌های آن را با کاما وارد کنید.'
        }),
    )


class ServiceDynamicFieldInline(admin.TabularInline):
    model = ServiceDynamicField
    extra = 1  # تعداد ردیف‌های خالی پیش‌فرض
    # تعیین فیلدهایی که در حالت اینلاین نمایش داده شوند
    fields = ('name', 'label', 'field_type', 'dropdown_options', 'is_required')


admin.site.register(ServiceMeasurements)


class ServiceMeasurmentsAdmin(admin.ModelAdmin):
    list_display = ('label', 'name', 'service', 'field_type', 'is_required')
    list_filter = ('service', 'field_type', 'is_required')
    search_fields = ('name', 'label', 'service__name')
    # اگر سرویس‌ها زیاد هستند، جستجو را راحت می‌کند
    autocomplete_fields = ['service']

    # برای زیبایی، فیلدها را در فرم ادمین گروه‌بندی می‌کنیم
    fieldsets = (
        ('اطلاعات پایه', {
            'fields': ('service', 'name', 'label', 'is_required')
        }),
        ('نوع فیلد و مقادیر', {
            'fields': ('field_type', 'dropdown_options'),
            'description': 'اگر نوع فیلد را دراپ‌داون انتخاب کردید، حتماً گزینه‌های آن را با کاما وارد کنید.'
        }),
    )
# =============================
# Design
# =============================


@admin.register(Design)
class DesignAdmin(admin.ModelAdmin):
    list_display = ('name', 'priority', 'price', 'cost')
    list_editable = ('priority',)
    search_fields = ('name',)
    list_filter = ('categories', 'services')
    ordering = ('priority', 'name')


# =============================
# Examination
# =============================

admin.site.register(Observation)


class ObservationAdmin(admin.ModelAdmin):

    search_fields = ("name",)


@admin.register(Exercises)


class ExercisesAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "difficulty",
        "duration_minutes",
    )

    list_filter = ("difficulty",)

    search_fields = ("name",)


@admin.register(Examination)


class ExaminationAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "patient",
        "doctor_name",
        "created_at",
    )

    search_fields = (
        "patient__first_name",
        "patient__last_name",
    )

    filter_horizontal = (
        "observations",
        "exercises",
        "prescription_designs",
    )



@admin.register(Measurement)


class MeasurementAdmin(admin.ModelAdmin):

    list_display = (
        "patient",
        "parameter",
        "value",
        "unit",
        "is_size_driver",
    )

    search_fields = ("parameter",)

    list_filter = ("is_size_driver",)


# =============================
# Order Inlines
# =============================

class OrderItemInline(admin.TabularInline):

    model = OrderItem
    extra = 1
    # autocomplete_fields = ("service", "variant")


class OrderItemDesignInline(admin.TabularInline):

    model = OrderItemDesign
    extra = 1
    autocomplete_fields = ("design",)


# =============================
# Orders
# =============================
@admin.register(Order)



class OrderAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "patient",
        "status",
        "total_price",
        "created_at",
    )

    search_fields = (
        "patient__first_name",
        "patient__last_name",
    )

    list_filter = (
        "status",
        "created_at",
    )
    
    # autocomplete_fields = (
    #     "patient",
    #     "examination",
    # )

    inlines = (
        OrderItemInline,
        OrderItemDesignInline,
    )


# =============================
# Manufacturing
# =============================

@admin.register(Technician)


class TechnicianAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "specialization",
        "phone",
        "is_active",
    )

    search_fields = ("name",)


@admin.register(PatientScan)


class PatientScanAdmin(admin.ModelAdmin):

    list_display = (
        "patient",
        "scan_type",
        "technician",
        "created_at",
    )

    list_filter = ("scan_type",)

    autocomplete_fields = (
        "patient",
        "order",
        "technician",
    )


@admin.register(ManufacturingStage)


class ManufacturingStageAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "order",
        "is_active",
    )

    ordering = ("order",)


@admin.register(ProductionTracking)
class ProductionTrackingAdmin(admin.ModelAdmin):

    list_display = (
        "order",
        "stage",
        "technician",
        "status",
        "started_at",
        "completed_at",
    )

    list_filter = (
        "status",
        "stage",
    )

    # autocomplete_fields = (
    #     "order",
    #     "stage",
    #     "technician",
    # )


@admin.register(Delivery)


class DeliveryAdmin(admin.ModelAdmin):

    list_display = (
        "order",
        "delivered_at",
        "delivered_by",
    )

    autocomplete_fields = ("order",)




@admin.register(PaymentAccount)
class PaymentAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'method', 'account_number', 'is_active')
    list_filter = ('method', 'is_active')
    
    
    
@admin.register(UnderlyingDisease)
class DiseaseAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(OrthoticHistoryType)
class OrthoticAdmin(admin.ModelAdmin):
    list_display = ('name',)
