# reception/urls.py

from django.urls import path

from apps.reception.views import order_views
from . import views

app_name = 'reception'

urlpatterns = [
    path('', views.reception_dashboard, name='dashboard'),
    path('new-patient/', views.create_patient, name='new-patient'),
    path('patient/<int:patient_id>/', views.patient_detail, name='patient-detail'),
    path('search-patients-ajax/', views.search_patients_ajax,name='search-patients-ajax'),
    path('patient/<int:patient_id>/edit/', views.edit_patient, name='edit-patient'),
    path('patient/<int:patient_id>/print/', views.print_patient, name='print-patient'),
    path('patient/delete/<int:patient_id>/', views.delete_patient, name='delete-patient'),
    path('patients/<int:patient_id>/documents/upload/',views.upload_patient_document,name='upload-patient-document'),
    # path('patient/<int:patient_id>/create-order/', views.create_order_for_patient, name='create-order'),
    path('patient/<int:patient_id>/exam/create/', views.create_examination, name='create-exam'),
    path('exam/<int:exam_id>/edit/', views.edit_examination, name='edit-exam'),
    path('exam/<int:exam_id>/delete/', views.delete_examination, name='delete-exam'),
    path('exam/<int:exam_id>/create-order/', views.create_order_from_exam, name='create-order-from-exam'),
    path('orders/<int:order_id>/edit/', order_views.edit_order, name='edit-order'),
    path('patient/<int:patient_id>/create-order/<int:exam_id>/', views.create_order, name='create-order'),
    path('order/<int:order_id>/delete/', views.delete_order, name='delete-order'),
    path('patient/<int:patient_id>/order/create-direct/',order_views.create_direct_order,name='create-direct-order'),
    # payment
    path('orders/<int:order_id>/add-payment/', order_views.add_payment, name='add-payment'),
    path('payments/<int:payment_id>/edit/', order_views.edit_payment, name='edit-payment'),
    path('payments/<int:payment_id>/delete/', order_views.delete_payment, name='delete-payment'),
    # api
    path('api/get-price-by-size/', views.get_price_by_size, name='get_price_by_size'),
    
    # path('patient/<int:patient_id>/create-order/',
    #      views.create_order_for_patient, name='create-order'),

]
