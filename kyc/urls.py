from django.urls import path

from .views import kyc_submit

urlpatterns = [
    path('', kyc_submit, name='kyc_submit'),
]
