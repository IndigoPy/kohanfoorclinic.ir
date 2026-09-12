from django.urls import path
from .views import CallLogCreateView, SmsLogCreateView

urlpatterns = [
    path('api/call-logs/', CallLogCreateView.as_view()),
    path('api/sms-logs/', SmsLogCreateView.as_view()),
]