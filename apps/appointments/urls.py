from django.urls import path
from . import views

app_name = 'appointments'

urlpatterns = [
    # --- نماهای اصلی (صفحات HTML) ---
    
    # لیست جدولی نوبت‌ها (صفحه اصلی اپلیکیشن نوبت‌دهی)
    path('', views.AppointmentListView.as_view(), name='list'),
    path('calendar/', views.CalendarTemplateView.as_view(), name='calendar'),
    # نمای تقویمی نوبت‌ها
    path('api/calendar/', views.CalendarApiView.as_view(), name='api_calendar'),
    
    
    # --- ای‌پی‌آی‌ها (برای استفاده در Ajax و FullCalendar) ---
    
    # ای‌پی‌آی تغذیه کننده تقویم
    path('api/calendar-events/', views.calendar_events_api, name='api_calendar'),
    path('api/update_event_time/', views.update_event_time, name='api_update_event_time'),
    path('ajax/load-dynamic-fields/', views.load_dynamic_fields, name='ajax_load_dynamic_fields'),
    # path('<int:pk>/edit/', AppointmentUpdateView.as_view(), name='update'),
    # --- مسیرهای آینده (فعلاً کامنت هستند تا در مراحل بعد ویوهایشان را بنویسیم) ---
    
    path('create/', views.AppointmentCreateView.as_view(), name='create'),
    path('<int:pk>/update/', views.AppointmentUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.AppointmentDeleteView.as_view(), name='delete'),
    path('<int:pk>/send-sms/', views.SendSMSView.as_view(), name='send_sms'),
    path('<int:pk>/detail/', views.AppointmentDetailView.as_view(), name='detail'),
    path('<int:pk>/toggle-sms-status/', views.ToggleSMSStatusView.as_view(), name='toggle_sms_status'),
    # path('api/search-patients/', views.PatientSearchAPIView.as_view(), name='api_search_patients'),
]
