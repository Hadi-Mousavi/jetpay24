from django.urls import path

from .views import dashboard, login_view, logout_view, register

urlpatterns = [
    path('register/', register, name='register'),
    path('auth/login/', login_view, name='login'),
    path('auth/logout/', logout_view, name='logout'),
    path('dashboard/', dashboard, name='dashboard'),
]
