from django.urls import path

from . import views

urlpatterns = [
    path('<int:order_pk>/submit/', views.payment_submit, name='payment_submit'),
    path('receipt/<int:pk>/download/', views.payment_receipt_download, name='payment_receipt_download'),
]
