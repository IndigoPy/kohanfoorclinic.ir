# KohanOrthotics/views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.utils import timezone
from apps.reception.models import Order



@login_required
def main_dashboard(request):
    user = request.user

    # آمار کلی سفارش‌ها
    ready_orders_count = Order.objects.filter(status='ready').count()
    urgent_ready_count = Order.objects.filter(
        status='ready', priority='urgent').count()
    today_orders_count = Order.objects.filter(
        created_at__date__gte=timezone.now().date()).count()
    today_delivered_count = Order.objects.filter(
        delivered_at__gte=timezone.now().date()).count()
    # today_delivered_count = Order.objects.filter(
    #     delivered_at__date__gte=timezone.now().date()).count()

    # نوتیفیکیشن‌های کاربر (۱۰ تای آخر، خوانده‌نشده اول)
    # notifications = request.user.notifications.order_by(
    #     '-is_read', '-created_at')[:10]
    # unread_notifications_count = request.user.notifications.filter(
    #     is_read=False).count()

    context = {
        'user': user,
        'ready_orders_count': ready_orders_count,
        'urgent_ready_count': urgent_ready_count,
        'today_orders_count': today_orders_count,
        'today_delivered_count': today_delivered_count,
        # 'notifications': notifications,
        # 'unread_notifications_count': unread_notifications_count,
    }
    return render(request, 'core/base_dashboard.html', context)


def custom_403_view(request, exception=None):
    # اگر کاربر لاگین است ولی دسترسی ندارد، ابتدا او را خارج (Logout) می‌کنیم
    if request.user.is_authenticated:
        logout(request)
        # اختیاری: ارسال یک پیام به کاربر برای توضیح علت خروج
        messages.warning(request, "شما دسترسی لازم برای این بخش را نداشتید. لطفاً با حساب کاربری مجاز وارد شوید.")
    
    # هدایت به صفحه لاگین (نام url لاگین خود را به جای 'login' قرار دهید)
    return redirect('login')