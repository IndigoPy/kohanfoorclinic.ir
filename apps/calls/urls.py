from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('command/', views.create_command, name='create_command'),
    path('tag/', views.set_tag, name='set_tag'),
    path('api/call-logs/', views.CallLogCreateView.as_view()),
    path('api/sms-logs/', views.SmsLogCreateView.as_view()),
    path('api/commands/', views.PendingCommandsView.as_view()),
    path('api/commands/wait/', views.WaitCommandsView.as_view()),
    path('api/commands/ack/', views.AckCommandView.as_view()),
]