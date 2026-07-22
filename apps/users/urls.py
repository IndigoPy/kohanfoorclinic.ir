# apps/users/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'users'

urlpatterns = [
    path('', views.custom_login),
    path('login/', views.custom_login , name='login'),
    path('logout/', views.custom_logout, name='logout'),
]
