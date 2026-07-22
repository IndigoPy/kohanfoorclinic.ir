# reception/models/manufacturing.py
from django.db import models
from .patient import TimeStampedModel
from .orders import Order, Technician


# =============================
# Manufacturing Stage
# =============================

class ManufacturingStage(models.Model):

    name = models.CharField(max_length=200)

    description = models.TextField(blank=True)

    order = models.IntegerField(
        help_text="Execution order of this stage"
    )

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["order"]


# =============================
# Production Tracking
# =============================

class ProductionTracking(TimeStampedModel):

    STATUS_CHOICES = (
        ("pending", "در انتظار ساخت"),
        ("in_progress", "در حال ساخت"),
        ("completed", "آماده تحویل"),
        ("skipped", "لغو شده"),
    )

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="production_steps"
    )

    stage = models.ForeignKey(
        ManufacturingStage,
        on_delete=models.PROTECT
    )

    technician = models.ForeignKey(
        Technician,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    notes = models.TextField(
        blank=True,
        null=True
    )

    def __str__(self):
        return f"{self.order} - {self.stage}"


# =============================
# Delivery
# =============================

class Delivery(TimeStampedModel):

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="delivery"
    )

    delivered_at = models.DateTimeField()

    delivered_by = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    patient_signature = models.ImageField(
        upload_to="delivery_signatures/",
        blank=True,
        null=True
    )

    notes = models.TextField(
        blank=True,
        null=True
    )

    def __str__(self):
        return f"Delivery - Order {self.order.id}"
