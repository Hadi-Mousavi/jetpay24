from django import forms

from .models import Order

SERVICE_LABELS = {
    'APPLICATION_FEE': 'پرداخت اپلیکیشن فی دانشگاه',
    'TUITION': 'پرداخت شهریه دانشگاه',
    'TOEFL': 'ثبت نام آزمون TOEFL',
    'GRE': 'ثبت نام آزمون GRE',
    'VISA': 'پرداخت هزینه سفارت',
    'OTHER': 'سایر پرداخت های بین المللی',
}

ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = [
            'name', 'phone', 'email', 'service_type',
            'amount', 'description', 'document',
        ]
        labels = {
            'name': 'نام و نام خانوادگی',
            'phone': 'شماره موبایل',
            'email': 'ایمیل',
            'service_type': 'نوع خدمت',
            'amount': 'مبلغ دلاری',
            'description': 'توضیحات',
            'document': 'مدرک یا فایل پیوست',
        }
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'نام و نام خانوادگی خود را وارد کنید',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': '۰۹۱۲۳۴۵۶۷۸۹',
                'dir': 'ltr',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'example@email.com',
                'dir': 'ltr',
            }),
            'service_type': forms.Select(attrs={
                'class': 'form-select form-select-lg',
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'مثال: ۱۵۰',
                'step': '0.01',
                'min': '0.01',
                'dir': 'ltr',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'توضیحات تکمیلی درباره سفارش (اختیاری)',
                'rows': 4,
            }),
            'document': forms.FileInput(attrs={
                'class': 'form-control form-control-lg',
                'accept': '.pdf,.jpg,.jpeg,.png',
            }),
        }
        error_messages = {
            'name': {'required': 'لطفاً نام و نام خانوادگی را وارد کنید.'},
            'phone': {'required': 'لطفاً شماره موبایل را وارد کنید.'},
            'email': {'required': 'لطفاً ایمیل را وارد کنید.'},
            'service_type': {'required': 'لطفاً نوع خدمت را انتخاب کنید.'},
            'amount': {'required': 'لطفاً مبلغ دلاری را وارد کنید.'},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].required = False
        self.fields['document'].required = False
        self.fields['service_type'].choices = [
            ('', '— انتخاب نوع خدمت —'),
        ] + [
            (value, SERVICE_LABELS.get(value, label))
            for value, label in Order.SERVICE_CHOICES
        ]

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise forms.ValidationError('مبلغ باید بزرگ‌تر از صفر باشد.')
        return amount

    def clean_document(self):
        document = self.cleaned_data.get('document')
        if not document:
            return document

        extension = document.name.rsplit('.', 1)[-1].lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise forms.ValidationError(
                'فرمت فایل مجاز نیست. فقط PDF، JPG، JPEG و PNG پذیرفته می‌شود.'
            )

        if document.size > MAX_FILE_SIZE:
            raise forms.ValidationError('حجم فایل نباید بیشتر از ۱۰ مگابایت باشد.')

        return document
