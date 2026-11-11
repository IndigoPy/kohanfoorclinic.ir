# reception/views/examination_views
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import group_required

from ..models import (
    Patient, Examination, Services, Design, Exercises,
    Observation, ServicesCategory, ServiceDynamicField,
)
from ..utils import parse_jalali_datetime, to_persian_date_str


# =====================================================================
# توابع کمکی
# =====================================================================

def _resolve_ids(raw_values, model):
    """
    لیست مقادیر ارسالی (id عددی یا نام جدید) را به لیست id تبدیل می‌کند.
    مقدار غیرعددی یعنی تگ جدید که باید ساخته شود.
    """
    ids = []
    for value in raw_values:
        value = str(value).strip()
        if not value:
            continue
        if value.isdigit():
            ids.append(int(value))
        else:
            obj, _ = model.objects.get_or_create(name=value)
            ids.append(obj.id)
    return ids


def _save_observations(request, exam):
    """ذخیره مشاهدات (یکپارچه یا تفکیک‌شده چپ/راست)."""
    separated = request.POST.get('is_separated_observations') == 'on'
    exam.is_separated_observations = separated

    if not separated:
        ids = _resolve_ids(request.POST.getlist('observations'), Observation)
        exam.observations.set(Observation.objects.filter(id__in=ids))
        exam.observations_left.clear()
        exam.observations_right.clear()
    else:
        left = _resolve_ids(request.POST.getlist('observations_left'), Observation)
        right = _resolve_ids(request.POST.getlist('observations_right'), Observation)
        exam.observations_left.set(Observation.objects.filter(id__in=left))
        exam.observations_right.set(Observation.objects.filter(id__in=right))
        exam.observations.clear()


def _save_exercises(request, exam):
    ids = _resolve_ids(request.POST.getlist('exercises'), Exercises)
    exam.exercises.set(Exercises.objects.filter(id__in=ids))


def _safe_quantity(raw):
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 1


def _design_entry(request, raw_cat, entry):
    """طراحی‌های یک سرویس (مشترک یا جدا برای چپ و راست) را داخل entry می‌نویسد."""
    separated = request.POST.get(f"is_separated_{raw_cat}") == 'on'
    entry['is_separated'] = separated

    def fill(post_key, ids_key, names_key):
        ids = _resolve_ids(request.POST.getlist(post_key), Design)
        if ids:
            entry[ids_key] = ids
            entry[names_key] = [d.name for d in Design.objects.filter(id__in=ids)]

    if not separated:
        fill(f"designs_{raw_cat}", "designs", "design_names")
    else:
        fill(f"designs_{raw_cat}_left", "designs_left", "design_names_left")
        fill(f"designs_{raw_cat}_right", "designs_right", "design_names_right")


def _build_prescription(request):
    """از فیلدهای quantity_* فرم، دیکشنری تجویز خدمات (JSON) را می‌سازد."""
    prescription = {}

    for key in request.POST:
        if not key.startswith('quantity_'):
            continue

        raw_cat = key.replace('quantity_', '', 1)
        entry = {"quantity": _safe_quantity(request.POST.get(key, 1))}
        json_key = raw_cat

        type_value = request.POST.get(f"type_{raw_cat}")
        if type_value:
            entry["type_id"] = type_value
            try:
                service = Services.objects.get(id=int(type_value))
                entry["type_name"] = service.name
                json_key = service.name
            except (ValueError, Services.DoesNotExist):
                entry["type_name"] = "سرویس نامشخص"
                json_key = f"سرویس_نامشخص_{raw_cat}"

        _design_entry(request, raw_cat, entry)

        prefix = f"dyn_{raw_cat}_"
        dynamic = {
            k[len(prefix):]: v
            for k, v in request.POST.items()
            if k.startswith(prefix) and v
        }
        if dynamic:
            entry["dynamic_fields"] = dynamic

        prescription[json_key] = entry

    return prescription


def _form_context():
    """داده‌های پایه‌ی فرم معاینه (مشترک بین ایجاد و ویرایش)."""
    designs = []
    for d in Design.objects.prefetch_related('services').order_by('priority', 'name'):
        designs.append({
            "id": d.id,
            "name": d.name,
            "service_ids": [s.id for s in d.services.all()],
        })

    return {
        "category": list(ServicesCategory.objects.values("id", "name")),
        "services": list(Services.objects.values("id", "name", "category_id")),
        "dynamic_fields": list(ServiceDynamicField.objects.values(
            "id", "service_id", "name", "label", "field_type",
            "is_required", "dropdown_options",
        )),
        "designs_data": designs,
        "observations": list(Observation.objects.values("id", "name")),
        "exercises": list(Exercises.objects.values("id", "name")),
    }


# =====================================================================
# ایجاد معاینه
# =====================================================================

@login_required
@group_required('Reception')
def create_examination(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)

    if request.method == 'POST':
        # --- تاریخ معاینه ---
        exam_date = timezone.now()
        raw_exam_date = request.POST.get('exam_date', '').strip()
        if raw_exam_date:
            exam_date = parse_jalali_datetime(raw_exam_date)
            if exam_date is None:
                messages.error(request, 'فرمت تاریخ معاینه معتبر نیست.')
                return redirect(request.path)

        is_separated_obs = request.POST.get('is_separated_observations') == 'on'

        examination = Examination.objects.create(
            patient=patient,
            doctor_name=request.user.get_full_name(),
            chief_complaint=request.POST.get('chief_complaint', '').strip(),
            notes=request.POST.get('notes', '').strip(),
            exam_date=exam_date,
            is_separated_observations=is_separated_obs,
        )

        _save_observations(request, examination)
        _save_exercises(request, examination)

        prescription = _build_prescription(request)
        if prescription:
            examination.prescription_services = prescription
            examination.save(update_fields=["prescription_services", "updated_at"])

        patient.stage = "examined"
        patient.save(update_fields=["stage", "updated_at"])

        messages.success(request, "معاینه با موفقیت ثبت شد")
        return redirect("reception:patient-detail", patient_id=patient.id)

    # ---------- GET ----------
    context = {
        "patient": patient,
        "current_persian_date": to_persian_date_str(timezone.now()),
        **_form_context(),
    }
    return render(request, "reception/examination.html", context)


# =====================================================================
# ویرایش معاینه
# =====================================================================

@login_required
@group_required('Reception')
def edit_examination(request, exam_id):
    exam = get_object_or_404(Examination, id=exam_id)

    if request.method == 'POST':
        # --- تاریخ معاینه ---
        raw_exam_date = request.POST.get('exam_date', '').strip()
        if raw_exam_date:
            parsed = parse_jalali_datetime(raw_exam_date)
            if parsed is None:
                messages.error(request, 'فرمت تاریخ معاینه معتبر نیست.')
                return redirect(request.path)
            exam.exam_date = parsed

        exam.notes = request.POST.get('notes', '').strip()
        exam.chief_complaint = request.POST.get('chief_complaint', '').strip()

        _save_observations(request, exam)   # is_separated_observations را هم روی exam می‌گذارد
        _save_exercises(request, exam)

        exam.prescription_services = _build_prescription(request)
        exam.save()

        messages.success(request, 'معاینه با موفقیت ویرایش شد.')
        return redirect('reception:patient-detail', patient_id=exam.patient_id)

    # ---------- GET ----------
    ps = exam.prescription_services
    if isinstance(ps, str):
        try:
            ps = json.loads(ps) if ps else {}
        except (json.JSONDecodeError, ValueError):
            ps = {}
    elif ps is None:
        ps = {}

    persian_date = to_persian_date_str(exam.exam_date)

    context = {
        'exam': exam,
        'patient': exam.patient,
        'selected_observations': list(exam.observations.values_list('id', flat=True)),
        'selected_observations_left': list(exam.observations_left.values_list('id', flat=True)),
        'selected_observations_right': list(exam.observations_right.values_list('id', flat=True)),
        'selected_exercises': list(exam.exercises.values_list('id', flat=True)),
        'prescription_data': json.dumps(ps, ensure_ascii=False),
        'persian_exam_date': persian_date,
        'current_persian_date': persian_date,
        **_form_context(),
    }
    return render(request, 'reception/examination.html', context)


# =====================================================================
# حذف معاینه (فقط POST)
# =====================================================================

@login_required
@group_required('Reception')
@require_POST
def delete_examination(request, exam_id):
    exam = get_object_or_404(Examination, id=exam_id)
    patient_id = exam.patient_id
    exam.delete()
    messages.success(request, 'معاینه با موفقیت حذف شد.')
    return redirect('reception:patient-detail', patient_id=patient_id)