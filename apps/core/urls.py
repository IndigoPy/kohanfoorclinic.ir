# KohanOrthotics/urls.py

from django.contrib import admin
from django.urls import path, include
from . import views  # برای داشبورد اصلی و لاگین

urlpatterns = [
    path('admin/', admin.site.urls),

    # # صفحه اصلی — فقط لاگین
    # path('', views.custom_login, name='login'),  # یا هر ویوی لاگین که داری
    # path('login/', views.custom_login, name='login'),
    # path('logout/', views.custom_logout, name='logout'),

    # داشبورد مرکزی — بعد از لاگین
    path('dashboard/', views.main_dashboard, name='main-dashboard'),

    # اپ‌های مختلف
    # path('reception/', include('apps.reception.urls')),
    # path('workshop/', include('WorkShop.urls')),
]