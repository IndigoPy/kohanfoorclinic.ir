from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from django.conf import settings
from django.db import IntegrityError
from .serializers import CallLogSerializer, SmsLogSerializer
from .models import CallLog, SmsLog,ContactTag
import hashlib
from django.db.models import Q
from .models import PendingCommand
from django.views.decorators.http import require_POST
from django.shortcuts import redirect
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import time

def check_api_key(request):
    key = (
        request.headers.get('X-API-KEY')
        or request.headers.get('X-Api-Key')
        or request.META.get('HTTP_X_API_KEY')
        or request.GET.get('key')  # برای تست راحت‌تر
    )
    expected = getattr(settings, 'PHONE_SYNC_API_KEY', None)

    # برای دیباگ موقت (بعداً حذف کن)
    print("RECEIVED KEY:", repr(key))
    print("EXPECTED KEY:", repr(expected))

    if not expected or not key or key.strip() != expected.strip():
        raise PermissionDenied("API Key نامعتبر است")


def make_call_hash(item):
    # مثال برای هش تماس
    raw = f"{item.get('device_id','main-phone')}|{item['number']}|{item['date'].isoformat()}|{item['call_type']}|{item['duration']}"
    return hashlib.sha256(raw.encode()).hexdigest()


def make_sms_hash(item):
    body_part = (item.get('body') or "")[:100]
    raw = f"{item.get('device_id','main-phone')}|{item['number']}|{item['date'].isoformat()}|{item['sms_type']}|{body_part}"
    return hashlib.sha256(raw.encode()).hexdigest()


class CallLogCreateView(APIView):
    def post(self, request):
        check_api_key(request)
        serializer = CallLogSerializer(data=request.data, many=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        created_count = 0
        for item in serializer.validated_data:
            h = make_call_hash(item)
            try:
                obj, created = CallLog.objects.get_or_create(
                    unique_hash=h,
                    defaults={
                        'name': item.get('name'),
                        'number': item['number'],
                        'call_type': item['call_type'],
                        'date': item['date'],
                        'duration': item['duration'],
                        'unique_hash': h,
                    }
                )
                if created:
                    created_count += 1
            except IntegrityError:
                pass  # تکراری بود

        return Response({
            "message": f"{created_count} تماس جدید ذخیره شد",
            "total_received": len(serializer.validated_data)
        }, status=status.HTTP_201_CREATED)


class SmsLogCreateView(APIView):
    def post(self, request):
        check_api_key(request)
        serializer = SmsLogSerializer(data=request.data, many=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        created_count = 0
        for item in serializer.validated_data:
            h = make_sms_hash(item)
            try:
                obj, created = SmsLog.objects.get_or_create(
                    unique_hash=h,
                    defaults={
                        'name': item.get('name'),
                        'number': item['number'],
                        'sms_type': item['sms_type'],
                        'body': item['body'],
                        'date': item['date'],
                        'unique_hash': h,
                    }
                )
                if created:
                    created_count += 1
            except IntegrityError:
                pass

        return Response({
            "message": f"{created_count} پیامک جدید ذخیره شد",
            "total_received": len(serializer.validated_data)
        }, status=status.HTTP_201_CREATED)
        
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from .models import CallLog, SmsLog

@staff_member_required
def dashboard(request):
    q = request.GET.get('q', '').strip()
    call_type = request.GET.get('call_type', '')
    sms_type = request.GET.get('sms_type', '')

    calls = CallLog.objects.all()
    sms_list = SmsLog.objects.all()

    if q:
        calls = calls.filter(Q(number__icontains=q) | Q(name__icontains=q))
        sms_list = sms_list.filter(
            Q(number__icontains=q) | Q(name__icontains=q) | Q(body__icontains=q)
        )

    if call_type:
        calls = calls.filter(call_type=call_type)
    if sms_type:
        sms_list = sms_list.filter(sms_type=sms_type)
        
    device_id = request.GET.get('device_id', '')
    if device_id:
        calls = calls.filter(device_id=device_id)
        sms_list = sms_list.filter(device_id=device_id)

    calls = list(calls.order_by('-date')[:100])
    sms_list = list(sms_list.order_by('-date')[:100])

    # برچسب‌ها
    tags = {t.number: t for t in ContactTag.objects.all()}
    tag_labels = {
        'customer': 'مشتری',
        'personal': 'شخصی',
        'spam': 'اسپم',
        'work': 'کاری',
        'other': 'سایر',
    }
    for call in calls:
        t = tags.get(call.number)
        call.tag_label = tag_labels.get(t.tag, t.tag) if t else None

    today = timezone.now().date()
    week_ago = today - timedelta(days=7)

    top_numbers = list(
        CallLog.objects.filter(date__date__gte=week_ago)
        .values('number', 'name')
        .annotate(c=Count('id'))
        .order_by('-c')[:10]
    )
    for item in top_numbers:
        t = tags.get(item['number'])
        item['tag_label'] = tag_labels.get(t.tag, t.tag) if t else None

    stats = {
        'today_incoming': CallLog.objects.filter(date__date=today, call_type='incoming').count(),
        'today_outgoing': CallLog.objects.filter(date__date=today, call_type='outgoing').count(),
        'today_missed': CallLog.objects.filter(date__date=today, call_type='missed').count(),
        'today_sms': SmsLog.objects.filter(date__date=today).count(),
        'top_numbers': top_numbers,
    }

    return render(request, 'calls/dashboard.html', {  # مسیر تمپلیت خودت را بگذار
        'stats': stats,
        'calls': calls,
        'sms_list': sms_list,
        'calls_count': CallLog.objects.count(),
        'sms_count': SmsLog.objects.count(),
        'commands': PendingCommand.objects.all().order_by('-created_at')[:50],
        'q': q,
        'call_type': call_type,
        'sms_type': sms_type,
    })
    
class PendingCommandsView(APIView):
    def get(self, request):
        check_api_key(request)
        device_id = request.GET.get('device_id', 'main-phone')
        commands = PendingCommand.objects.filter(status='pending').order_by('id')[:10]
        data = [{
            'id': c.id,
            'command_type': c.command_type,
            'number': c.number,
            'body': c.body or '',
            'device_id': c.device_id,
        } for c in commands]
        return Response(data)


class AckCommandView(APIView):
    VALID = ('done', 'failed', 'rejected')

    def post(self, request):
        check_api_key(request)
        cmd_id = request.data.get('id')
        status_value = request.data.get('status')

        if status_value not in self.VALID:
            return Response({'ok': False, 'error': 'status is required: done/failed/rejected'}, status=400)

        try:
            cmd = PendingCommand.objects.get(id=cmd_id)
        except PendingCommand.DoesNotExist:
            return Response({'ok': False}, status=404)

        # فقط دستورات در حال انتظار قابل تغییرند
        if cmd.status != PendingCommand.STATUS_PENDING:
            return Response({'ok': True, 'ignored': True})

        cmd.status = status_value
        cmd.is_done = True
        cmd.done_at = timezone.now()
        cmd.error = (request.data.get('error') or '')[:255]
        cmd.save()
        return Response({'ok': True})




@staff_member_required
@require_POST
def create_command(request):
    command_type = request.POST.get('command_type')
    number = request.POST.get('number', '').strip()
    body = request.POST.get('body', '').strip()

    if command_type in ['call', 'sms'] and number:
        device_id = request.POST.get('device_id', 'main-phone')
        PendingCommand.objects.create(
            command_type=command_type,
            number=number,
            body=body if command_type == 'sms' else None,
            status='pending',
            device_id=device_id,
        )
    return redirect('dashboard')

@staff_member_required
@require_POST
def set_tag(request):
    number = request.POST.get('number', '').strip()
    tag = request.POST.get('tag', 'other')
    name = request.POST.get('name', '')
    if number and tag:
        ContactTag.objects.update_or_create(
            number=number,
            defaults={'tag': tag, 'name': name or ''}
        )
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


class WaitCommandsView(APIView):
    def get(self, request):
        check_api_key(request)
        device_id = request.GET.get('device_id', 'main-phone')
        since_id = int(request.GET.get('since_id', 0) or 0)
        timeout, interval, elapsed = 15, 1, 0
        commands = PendingCommand.objects.filter(status='pending').order_by('id')[:10]
        while elapsed < timeout:
            qs = PendingCommand.objects.filter(
                status='pending',
                device_id=device_id,
                id__gt=since_id
            ).order_by('id')[:5]
            if qs.exists():
                data = [{
                    'id': c.id,
                    'command_type': c.command_type,
                    'number': c.number,
                    'body': c.body or '',
                } for c in qs]
                return Response({'commands': data})
            time.sleep(interval)
            elapsed += interval

        return Response({'commands': []})