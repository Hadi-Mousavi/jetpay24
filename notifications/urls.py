from django.urls import path

from . import views

urlpatterns = [
    path('dropdown/', views.dropdown_api, name='notifications_dropdown'),
    path('mark-all-read/', views.mark_all_read, name='notifications_mark_all_read'),
    path('<int:pk>/read/', views.mark_read, name='notification_mark_read'),
]
