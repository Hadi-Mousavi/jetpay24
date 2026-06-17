from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth import logout
from django.shortcuts import redirect, render

from .forms import LoginForm, RegistrationForm
from .models import User


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            User.objects.create_user(
                email=data['email'],
                password=data['password1'],
                first_name=data['first_name'],
                last_name=data['last_name'],
                phone=data.get('phone'),
            )
            return redirect(settings.LOGIN_URL)
    else:
        form = RegistrationForm()

    return render(request, 'accounts/register.html', {
        'form': form,
        'login_url': settings.LOGIN_URL,
    })


def login_view(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect(settings.LOGIN_REDIRECT_URL)
    else:
        form = LoginForm(request)

    return render(request, 'accounts/login.html', {
        'form': form,
        'register_url': '/register/',
    })


def logout_view(request):
    logout(request)
    return redirect(settings.LOGIN_REDIRECT_URL)
