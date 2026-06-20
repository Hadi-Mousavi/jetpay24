from django import forms

from orders.utils import validate_upload

from .models import Payment


class PaymentSubmitForm(forms.ModelForm):
    """
    Customer-facing form for submitting a payment receipt.

    Validation pipeline (mirrors orders/utils.py):
      1. Extension must be jpg / jpeg / png / pdf
      2. Size ≤ 10 MB
      3. Magic bytes confirmed by filetype library
    """

    receipt_file = forms.FileField(
        label='فایل رسید پرداخت',
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/jpeg,image/png,application/pdf',
        }),
        help_text='فرمت‌های مجاز: JPG، PNG، PDF — حداکثر ۱۰ مگابایت',
    )

    reference_number = forms.CharField(
        label='شماره مرجع / پیگیری',
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'شماره مرجع تراکنش بانکی (اختیاری)',
            'dir': 'ltr',
        }),
    )

    class Meta:
        model = Payment
        fields = ['receipt_file', 'reference_number']

    def clean_receipt_file(self):
        f = self.cleaned_data.get('receipt_file')
        validate_upload(f)
        return f
