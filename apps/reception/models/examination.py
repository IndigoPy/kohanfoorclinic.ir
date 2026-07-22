# reception/models/examination.py
from django.db import models
from .patient import TimeStampedModel, Patient
from .services import Design
from django.utils import timezone

# =============================
# Observations
# =============================

class Observation(TimeStampedModel):

    name = models.CharField(max_length=200)

    description = models.TextField(blank=True)

    priority = models.IntegerField(default=0)

    usage_count = models.IntegerField(default=0)

    def __str__(self):
        return self.name


# =============================
# Exercises
# =============================

class Exercises(TimeStampedModel):

    DIFFICULTY_CHOICES = (
        ("easy", "Easy"),
        ("medium", "Medium"),
        ("hard", "Hard"),
    )

    name = models.CharField(max_length=200)

    description = models.TextField()

    difficulty = models.CharField(
        max_length=10,
        choices=DIFFICULTY_CHOICES,
        default="easy"
    )

    duration_minutes = models.IntegerField(
        blank=True,
        null=True
    )

    equipment_needed = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    reference_link = models.URLField(
        blank=True,
        null=True
    )

    def __str__(self):
        return self.name


# =============================
# Examination
# =============================

class Examination(TimeStampedModel):

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="examinations"
    )
    
    exam_date = models.DateTimeField(default=timezone.now)

    doctor_name = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    # --------------------------------------------------------
    # بخش شرح حال مراجع
    # --------------------------------------------------------
    chief_complaint = models.TextField(
        blank=True,
        null=True,
        verbose_name="شرح حال و شکایت اصلی"
    )
    

    # --------------------------------------------------------
    # بخش مشاهدات بالینی (اضافه شدن تمایز پای چپ و راست)
    # --------------------------------------------------------
    is_separated_observations = models.BooleanField(
        default=False,
        verbose_name="تمایز پای چپ و راست برای مشاهدات"
    )

    observations = models.ManyToManyField(
        Observation,
        blank=True,
        related_name="examinations_general", # تغییر related_name برای جلوگیری از تداخل
        verbose_name="مشاهدات (حالت یکپارچه)"
    )

    observations_left = models.ManyToManyField(
        Observation,
        blank=True,
        related_name="examinations_left",
        verbose_name="مشاهدات (پای چپ)"
    )

    observations_right = models.ManyToManyField(
        Observation,
        blank=True,
        related_name="examinations_right",
        verbose_name="مشاهدات (پای راست)"
    )
    # --------------------------------------------------------

    prescription_services = models.JSONField(
        blank=True,
        null=True,
        help_text="Temporary storage for prescribed services"
    )

    prescription_designs = models.ManyToManyField(
        Design,
        blank=True,
        related_name="examinations"
    )

    exercises = models.ManyToManyField(
        Exercises,
        blank=True,
        related_name="examinations"
    )

    notes = models.TextField(
        blank=True,
        null=True
    )

    def __str__(self):
        # اگر full_name یک متد یا پراپرتی در مدل Patient است، همین ساختار صحیح است.
        return f"Examination - {self.patient.full_name}"


# =============================
# Measurement
# =============================

class Measurement(TimeStampedModel):

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="measurements"
    )

    parameter = models.CharField(
        max_length=100,
        help_text="Example: foot_length, arch_height"
    )

    value = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    unit = models.CharField(
        max_length=20,
        default="mm"
    )

    is_size_driver = models.BooleanField(
        default=False,
        help_text="If true, used to determine size-based pricing"
    )

    notes = models.TextField(
        blank=True,
        null=True
    )

    def __str__(self):
        return f"{self.parameter}: {self.value}{self.unit} ({self.patient})"
