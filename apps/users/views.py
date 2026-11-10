from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages


def custom_login(request):
    if request.user.is_authenticated:
        return redirect('main-dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # هدایت بر اساس نقش
            if user.groups.filter(name__iexact='Reception').exists():
                # هدایت بر اساس نقش
                messages.success(
                    request, f'خوش آمدید {user.get_full_name() or user.username}')
                return redirect('main-dashboard')

            if user.groups.filter(name__iexact='Workshop').exists():
                # هدایت بر اساس نقش
                messages.success(
                    request, f'خوش آمدید {user.get_full_name() or user.username}')
                return redirect('main-dashboard')

            # اگر نقش نداشت
            logout(request)
            messages.error(request, 'نقش کاربری برای شما تعریف نشده است')

        else:
            messages.error(request, 'نام کاربری یا رمز عبور اشتباه است')

    return render(request, 'users/login.html')


def custom_logout(request):
    logout(request)
    return redirect('/users/login')