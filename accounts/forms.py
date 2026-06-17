from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import User


class RegistrationForm(forms.Form):
    first_name = forms.CharField(
        max_length=60,
        label='نام',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'نام',
            'autofocus': True,
        }),
    )
    last_name = forms.CharField(
        max_length=60,
        label='نام خانوادگی',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'نام خانوادگی',
        }),
    )
    email = forms.EmailField(
        label='ایمیل',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'example@email.com',
            'dir': 'ltr',
        }),
    )
    phone = forms.CharField(
        max_length=20,
        required=True,
        label='شماره موبایل',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '۰۹۱۲۳۴۵۶۷۸۹',
            'dir': 'ltr',
        }),
    )
    password1 = forms.CharField(
        label='رمز عبور',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'رمز عبور',
        }),
    )
    password2 = forms.CharField(
        label='تکرار رمز عبور',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'تکرار رمز عبور',
        }),
    )

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError('این ایمیل قبلاً ثبت شده است.')
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not phone:
            raise ValidationError('شماره موبایل الزامی است.')
        if User.objects.filter(phone=phone).exists():
            raise ValidationError('این شماره موبایل قبلاً ثبت شده است.')
        return phone

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        if password:
            validate_password(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'رمزهای عبور با هم مطابقت ندارند.')
        return cleaned_data


class LoginForm(forms.Form):
    email = forms.EmailField(
        label='ایمیل',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'example@email.com',
            'dir': 'ltr',
            'autofocus': True,
        }),
    )
    password = forms.CharField(
        label='رمز عبور',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'رمز عبور',
        }),
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self._user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email', '').lower()
        password = cleaned_data.get('password')

        if email and password:
            user = authenticate(self.request, username=email, password=password)
            if user is None:
                raise ValidationError('ایمیل یا رمز عبور اشتباه است.')
            if not user.is_active:
                raise ValidationError('این حساب کاربری غیرفعال است.')
            self._user = user

        return cleaned_data

    def get_user(self):
        return self._user
