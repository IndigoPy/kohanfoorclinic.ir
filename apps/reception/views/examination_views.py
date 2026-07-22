# reception/views/examination_views
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import Patient, Document, Examination, Order, OrderItem, Services, Design, Exercises, Observation, ServicesCategory, ServiceSubCategory, ServiceDynamicField
# from WorkShop.forms import OrderCreateForm
from apps.core.decorators import group_required
from django.template.loader import render_to_string
import json
import jdatetime


@login_required
@group_required('Reception')
def create_examination(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)

    if request.method == 'POST':
        notes = request.POST.get('notes', '').strip()
        chief_complaint = request.POST.get('chief_complaint', '').strip()
        
        raw_exam_date = request.POST.get('exam_date', '').strip()
        if raw_exam_date:
            try:
                # پاکسازی و تبدیل
                year, month, day = map(int, raw_exam_date.split('/'))
                # فرض بر اینکه زمان کنونی را می‌خواهیم حفظ کنیم یا ساعت 00:00 قرار دهیم
                exam_datetime = jdatetime.datetime(year, month, day, 0, 0).togregorian()
                examination.exam_date = exam_datetime
            except Exception as e:
                messages.error(request, 'فرمت تاریخ معاینه معتبر نیست.')
        
        # بررسی وضعیت دکمه تفکیک مشاهدات
        is_separated_obs = request.POST.get('is_separated_observations') == 'on'

        # ---------- Create Examination ----------
        examination = Examination.objects.create(
            patient=patient,
            doctor_name = request.user.get_full_name(),
            chief_complaint=chief_complaint,  # ذخیره شرح حال
            notes=notes,
            is_separated_observations=is_separated_obs
        )

        # ---------- Observations ----------
        if not is_separated_obs:
            # حالت یکپارچه
            raw_observations = request.POST.getlist('observations')
            final_observation_ids = []

            if raw_observations:
                for obs in raw_observations:
                    if str(obs).isdigit():
                        final_observation_ids.append(int(obs))
                    else:
                        obj, _ = Observation.objects.get_or_create(name=obs)
                        final_observation_ids.append(obj.id)

                examination.observations.set(
                    Observation.objects.filter(id__in=final_observation_ids)
                )
        else:
            # حالت تفکیک شده (پای چپ)
            raw_observations_left = request.POST.getlist('observations_left')
            final_left_ids = []
            if raw_observations_left:
                for obs in raw_observations_left:
                    if str(obs).isdigit():
                        final_left_ids.append(int(obs))
                    else:
                        obj, _ = Observation.objects.get_or_create(name=obs)
                        final_left_ids.append(obj.id)
                examination.observations_left.set(
                    Observation.objects.filter(id__in=final_left_ids)
                )

            # حالت تفکیک شده (پای راست)
            raw_observations_right = request.POST.getlist('observations_right')
            final_right_ids = []
            if raw_observations_right:
                for obs in raw_observations_right:
                    if str(obs).isdigit():
                        final_right_ids.append(int(obs))
                    else:
                        obj, _ = Observation.objects.get_or_create(name=obs)
                        final_right_ids.append(obj.id)
                examination.observations_right.set(
                    Observation.objects.filter(id__in=final_right_ids)
                )

        # ---------- Exercises ----------
        raw_exercises = request.POST.getlist('exercises')
        final_exercise_ids = []
        
        if raw_exercises:
            for ex in raw_exercises:
                if str(ex).isdigit():
                    final_exercise_ids.append(int(ex))
                else:
                    obj, _ = Exercises.objects.get_or_create(name=ex)
                    final_exercise_ids.append(obj.id)

            examination.exercises.set(
                Exercises.objects.filter(id__in=final_exercise_ids)
            )

        # ---------- Prescription Services (Dynamic & JSON) ----------
        prescription_data = {}

        for key in request.POST:
            if not key.startswith('quantity_'):
                continue

            raw_cat = key.replace('quantity_', '')  
            quantity = int(request.POST.get(key, 1))

            entry = {"quantity": quantity}
            json_key_name = raw_cat 

            # دریافت آیدی و نام سرویس
            type_value = request.POST.get(f"type_{raw_cat}")
            if type_value:
                entry["type_id"] = type_value
                try:
                    service_obj = Services.objects.get(id=int(type_value))
                    entry["type_name"] = service_obj.name
                    json_key_name = service_obj.name  
                except (ValueError, Services.DoesNotExist):
                    entry["type_name"] = "سرویس نامشخص"
                    json_key_name = f"سرویس_نامشخص_{raw_cat}"

            # بررسی وضعیت دکمه تفکیک طراحی
            is_separated_design = request.POST.get(f"is_separated_{raw_cat}") == 'on'
            entry['is_separated'] = is_separated_design

            if not is_separated_design:
                raw_designs = request.POST.getlist(f"designs_{raw_cat}")
                final_design_ids = []
                for d in raw_designs:
                    if str(d).isdigit():
                        final_design_ids.append(int(d))
                    else:
                        obj, _ = Design.objects.get_or_create(name=d)
                        final_design_ids.append(obj.id)
                
                entry["designs"] = final_design_ids
                design_objs = Design.objects.filter(id__in=final_design_ids)
                entry["design_names"] = [d.name for d in design_objs]

            else:
                raw_designs_left = request.POST.getlist(f"designs_{raw_cat}_left")
                final_left_design_ids = []
                for d in raw_designs_left:
                    if str(d).isdigit():
                        final_left_design_ids.append(int(d))
                    else:
                        obj, _ = Design.objects.get_or_create(name=d)
                        final_left_design_ids.append(obj.id)
                        
                entry["designs_left"] = final_left_design_ids
                left_objs = Design.objects.filter(id__in=final_left_design_ids)
                entry["design_names_left"] = [d.name for d in left_objs]

                raw_designs_right = request.POST.getlist(f"designs_{raw_cat}_right")
                final_right_design_ids = []
                for d in raw_designs_right:
                    if str(d).isdigit():
                        final_right_design_ids.append(int(d))
                    else:
                        obj, _ = Design.objects.get_or_create(name=d)
                        final_right_design_ids.append(obj.id)
                        
                entry["designs_right"] = final_right_design_ids
                right_objs = Design.objects.filter(id__in=final_right_design_ids)
                entry["design_names_right"] = [d.name for d in right_objs]

            # دریافت فیلدهای داینامیک
            dynamic_data = {}
            for post_key, post_value in request.POST.items():
                prefix = f"dyn_{raw_cat}_"
                if post_key.startswith(prefix) and post_value:
                    field_name = post_key.replace(prefix, "")
                    dynamic_data[field_name] = post_value

            if dynamic_data:
                entry["dynamic_fields"] = dynamic_data

            prescription_data[json_key_name] = entry

        if prescription_data:
            examination.prescription_services = prescription_data
            examination.save(update_fields=["prescription_services"])

        patient.stage = "examined"
        patient.save(update_fields=["stage"])

        messages.success(request, "معاینه با موفقیت ثبت شد")
        return redirect("reception:patient-detail", patient_id=patient.id)

    # ---------- Load Data For Form (GET) ----------
    category_list = list(ServicesCategory.objects.values("id", "name"))
    services_list = list(Services.objects.values("id", "name", "category_id"))
    dynamic_fields_list = list(ServiceDynamicField.objects.values(
        "id", "service_id", "name", "label", "field_type", "is_required", "dropdown_options"
    ))

    designs_qs = Design.objects.prefetch_related('services').order_by('priority', 'name')
    designs_list = []
    for d in designs_qs:
        designs_list.append({
            "id": d.id,
            "name": d.name,
            "service_ids": list(d.services.values_list('id', flat=True))
        })

    observation_list = list(Observation.objects.values("id", "name"))
    exercise_list = list(Exercises.objects.values("id", "name"))

    context = {
        "patient": patient,
        "observations": observation_list,
        "exercises": exercise_list,
        "category": category_list,
        "services": services_list,
        "dynamic_fields": dynamic_fields_list,
        "designs_data": designs_list,
    }

    return render(request, "reception/examination.html", context)


@login_required
@group_required('Reception')
def edit_examination(request, exam_id):
    exam = get_object_or_404(Examination, id=exam_id)
    patient = exam.patient

    if request.method == 'POST':
        # ---------- Notes, Complaint & Date ----------
        exam.notes = request.POST.get('notes', '').strip()
        raw_exam_date = request.POST.get('exam_date', '').strip()

        if raw_exam_date:
            try:
                translation_table = str.maketrans(
                    '۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩',
                    '01234567890123456789'
                )
                normalized_date = raw_exam_date.translate(translation_table).replace('-', '/')
                year, month, day = map(int, normalized_date.split('/'))

                exam_datetime = jdatetime.datetime(year, month, day, 0, 0).togregorian()
                exam.exam_date = exam_datetime

            except Exception:
                messages.error(request, 'فرمت تاریخ معاینه معتبر نیست.')
                return redirect(request.path)

        exam.chief_complaint = request.POST.get('chief_complaint', '').strip()
        
        

        # ---------- Observations ----------
        is_obs_separated = request.POST.get('is_separated_observations') == 'on'
        exam.is_separated_observations = is_obs_separated

        if not is_obs_separated:
            # حالت یکپارچه
            raw_observations = request.POST.getlist('observations')
            final_obs_ids = []
            for obs in raw_observations:
                if str(obs).isdigit():
                    final_obs_ids.append(int(obs))
                else:
                    obj, _ = Observation.objects.get_or_create(name=obs)
                    final_obs_ids.append(obj.id)
            exam.observations.set(Observation.objects.filter(id__in=final_obs_ids))
            
            exam.observations_left.clear()
            exam.observations_right.clear()

        else:
            # حالت تفکیک شده
            raw_obs_left = request.POST.getlist('observations_left')
            final_left_ids = []
            for obs in raw_obs_left:
                if str(obs).isdigit():
                    final_left_ids.append(int(obs))
                else:
                    obj, _ = Observation.objects.get_or_create(name=obs)
                    final_left_ids.append(obj.id)
            exam.observations_left.set(Observation.objects.filter(id__in=final_left_ids))
            
            raw_obs_right = request.POST.getlist('observations_right')
            final_right_ids = []
            for obs in raw_obs_right:
                if str(obs).isdigit():
                    final_right_ids.append(int(obs))
                else:
                    obj, _ = Observation.objects.get_or_create(name=obs)
                    final_right_ids.append(obj.id)
            exam.observations_right.set(Observation.objects.filter(id__in=final_right_ids))
            
            exam.observations.clear()

        # ---------- Exercises ----------
        raw_exercises = request.POST.getlist('exercises')
        final_exercise_ids = []
        if raw_exercises:
            for ex in raw_exercises:
                if str(ex).isdigit():
                    final_exercise_ids.append(int(ex))
                else:
                    obj, _ = Exercises.objects.get_or_create(name=ex)
                    final_exercise_ids.append(obj.id)
            exam.exercises.set(Exercises.objects.filter(id__in=final_exercise_ids))
        else:
            exam.exercises.clear()

        # ---------- Prescription Services (JSON) ----------
        prescription_data = {}
        for key in request.POST:
            if not key.startswith('quantity_'):
                continue

            raw_cat = key.replace('quantity_', '')
            quantity = int(request.POST.get(key, 1))
            entry = {"quantity": quantity}
            
            json_key_name = raw_cat

            type_value = request.POST.get(f"type_{raw_cat}")
            if type_value:
                entry["type_id"] = type_value
                try:
                    service_obj = Services.objects.get(id=int(type_value))
                    entry["type_name"] = service_obj.name
                    json_key_name = service_obj.name
                except (ValueError, Services.DoesNotExist):
                    entry["type_name"] = "سرویس نامشخص"
                    json_key_name = f"سرویس_نامشخص_{raw_cat}"

            is_separated = request.POST.get(f"is_separated_{raw_cat}") == 'on'
            entry['is_separated'] = is_separated

            if not is_separated:
                raw_designs = request.POST.getlist(f"designs_{raw_cat}")
                final_design_ids = []
                for d in raw_designs:
                    if str(d).isdigit():
                        final_design_ids.append(int(d))
                    else:
                        obj, _ = Design.objects.get_or_create(name=d)
                        final_design_ids.append(obj.id)
                
                if final_design_ids:
                    entry["designs"] = final_design_ids
                    design_objs = Design.objects.filter(id__in=final_design_ids)
                    entry["design_names"] = [d.name for d in design_objs]

            else:
                raw_designs_left = request.POST.getlist(f"designs_{raw_cat}_left")
                final_left_ids = []
                for d in raw_designs_left:
                    if str(d).isdigit():
                        final_left_ids.append(int(d))
                    else:
                        obj, _ = Design.objects.get_or_create(name=d)
                        final_left_ids.append(obj.id)
                
                if final_left_ids:
                    entry["designs_left"] = final_left_ids
                    left_objs = Design.objects.filter(id__in=final_left_ids)
                    entry["design_names_left"] = [d.name for d in left_objs]

                raw_designs_right = request.POST.getlist(f"designs_{raw_cat}_right")
                final_right_ids = []
                for d in raw_designs_right:
                    if str(d).isdigit():
                        final_right_ids.append(int(d))
                    else:
                        obj, _ = Design.objects.get_or_create(name=d)
                        final_right_ids.append(obj.id)
                
                if final_right_ids:
                    entry["designs_right"] = final_right_ids
                    right_objs = Design.objects.filter(id__in=final_right_ids)
                    entry["design_names_right"] = [d.name for d in right_objs]

            dynamic_data = {}
            for post_key, post_value in request.POST.items():
                prefix = f"dyn_{raw_cat}_"
                if post_key.startswith(prefix) and post_value:
                    field_name = post_key.replace(prefix, "")
                    dynamic_data[field_name] = post_value

            if dynamic_data:
                entry["dynamic_fields"] = dynamic_data

            prescription_data[json_key_name] = entry

        exam.prescription_services = prescription_data
        exam.save()

        messages.success(request, 'معاینه با موفقیت ویرایش شد.')
        return redirect('reception:patient-detail', patient_id=exam.patient.id)

    # ---------- GET Request Data ----------
    category_list = list(ServicesCategory.objects.values("id", "name"))
    services_list = list(Services.objects.values("id", "name", "category_id"))
    dynamic_fields_list = list(ServiceDynamicField.objects.values(
        "id", "service_id", "name", "label", "field_type", "is_required", "dropdown_options"
    ))

    # در ویوی edit_examination (بخش GET)
    persian_exam_date = ""
    if exam.exam_date:
        j_date = jdatetime.date.fromgregorian(date=exam.exam_date)
        persian_exam_date = f"{j_date.year}/{j_date.month:02d}/{j_date.day:02d}"
    
    designs_qs = Design.objects.prefetch_related('services').order_by('priority', 'name')
    designs_list = []
    for d in designs_qs:
        designs_list.append({
            "id": d.id,
            "name": d.name,
            "service_ids": list(d.services.values_list('id', flat=True))
        })

    observation_list = list(Observation.objects.values("id", "name"))
    exercise_list = list(Exercises.objects.values("id", "name"))

    ps = exam.prescription_services
    if isinstance(ps, str):
        try:
            ps = json.loads(ps) if ps else {}
        except (json.JSONDecodeError, ValueError):
            ps = {}
    elif ps is None:
        ps = {}

    context = {
        'exam': exam,
        'patient': exam.patient,
        'category': category_list,
        'services': services_list,
        'dynamic_fields': dynamic_fields_list,
        'designs_data': designs_list,
        'observations': observation_list,
        'exercises': exercise_list,
        'selected_observations': list(exam.observations.values_list('id', flat=True)),
        'selected_observations_left': list(exam.observations_left.values_list('id', flat=True)),
        'selected_observations_right': list(exam.observations_right.values_list('id', flat=True)),
        'selected_exercises': list(exam.exercises.values_list('id', flat=True)),
        'prescription_data': json.dumps(ps, ensure_ascii=False),
        'persian_exam_date': persian_exam_date,
    }
    return render(request, 'reception/examination.html', context)

@group_required('Reception')
@login_required
def delete_examination(request, exam_id):
    exam = get_object_or_404(Examination, id=exam_id)
    patient_id = exam.patient.id
    print(request)
    if request.method == 'GET':
        exam.delete()
        messages.success(request, 'معاینه با موفقیت حذف شد.')
        return redirect('reception:patient-detail', patient_id=patient_id)

    return redirect('reception:patient-detail', patient_id=patient_id)
