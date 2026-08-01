from django.urls import path
from . import views

app_name = 'appointments'

urlpatterns = [
    # --- نماهای اصلی (صفحات HTML) ---
    path('', views.AppointmentListView.as_view(), name='list'),
    path('calendar/', views.CalendarTemplateView.as_view(), name='calendar'),

    # --- API اصلی FullCalendar ---
    path('api/calendar/', views.CalendarApiView.as_view(), name='api_calendar'),

    # --- APIهای دیگر ---
    path('api/calendar-events/', views.calendar_events_api, name='api_calendar_events'),
    path('api/update_event_time/', views.update_event_time, name='api_update_event_time'),
    path('ajax/load-dynamic-fields/', views.load_dynamic_fields, name='ajax_load_dynamic_fields'),
    path(
    'api/update_status/',
    views.update_appointment_status,
    name='api_update_appointment_status'
),


    path('create/', views.AppointmentCreateView.as_view(), name='create'),
    path('<int:pk>/update/', views.AppointmentUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.AppointmentDeleteView.as_view(), name='delete'),
    path('<int:pk>/send-sms/', views.SendSMSView.as_view(), name='send_sms'),
    path('<int:pk>/detail/', views.AppointmentDetailView.as_view(), name='detail'),
    path('<int:pk>/toggle-sms-status/', views.ToggleSMSStatusView.as_view(), name='toggle_sms_status'),
]
