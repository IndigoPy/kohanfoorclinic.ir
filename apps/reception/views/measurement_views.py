from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from apps.core.decorators import group_required
from apps.workshop.services.measurement import request_measurement

from ..models import Examination


@login_required
@group_required('Reception')
@require_POST
def send_exam_for_measurement(request, exam_id):
    exam = get_object_or_404(Examination.objects.select_related('patient'), id=exam_id)

    try:
        order, created = request_measurement(exam=exam, user=request.user)
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        if created:
            messages.success(request, 'پرونده برای اندازه‌گیری و تعیین مشخصات به کارگاه ارسال شد.')
        else:
            messages.info(request, 'این معاینه قبلاً برای اندازه‌گیری ارسال شده است.')

    return redirect('reception:patient-detail', patient_id=exam.patient_id)