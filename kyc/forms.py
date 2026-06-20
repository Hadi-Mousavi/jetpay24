import jdatetime
from django import forms

from .models import KYCProfile
from .utils import validate_kyc_image

_FA_TO_EN = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
_EN_TO_FA = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')


def _normalize_digits(value: str) -> str:
    """Translate Persian/Arabic-Indic Eastern-Arabic digits to ASCII."""
    return value.translate(_FA_TO_EN)


class JalaliDateField(forms.CharField):
    """
    A form field that accepts Jalali dates in YYYY/MM/DD format
    (both Persian and ASCII digits) and converts them to a Python
    datetime.date (Gregorian) for storage.

    When rendering an existing value from the model (a Gregorian date),
    prepare_value() converts it back to Jalali with Persian digits so
    the user always sees the familiar Persian calendar.
    """

    def to_python(self, value):
        value = super().to_python(value)
        if not value:
            return None
        normalized = _normalize_digits(value.strip())
        parts = normalized.replace('-', '/').split('/')
        if len(parts) != 3:
            raise forms.ValidationError('تاریخ را به فرمت ۱۴۰۰/۰۱/۰۱ وارد کنید.')
        try:
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            return jdatetime.date(year, month, day).togregorian()
        except Exception:
            raise forms.ValidationError('تاریخ وارد شده معتبر نیست.')

    def prepare_value(self, value):
        """
        - Gregorian date object (from instance) → convert to Jalali + Persian digits
        - String (re-render after POST error) → pass through as-is
        - None/empty → empty string
        """
        if value is None:
            return ''
        if hasattr(value, 'year') and hasattr(value, 'month') and hasattr(value, 'day'):
            try:
                jd = jdatetime.date.fromgregorian(date=value)
                latin = f'{jd.year:04d}/{jd.month:02d}/{jd.day:02d}'
                return latin.translate(_EN_TO_FA)
            except Exception:
                return str(value)
        return value


class KYCSubmitForm(forms.ModelForm):

    national_id = forms.CharField(
        label='کد ملی',
        max_length=10,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '۱۰ رقم کد ملی',
            'dir': 'ltr',
            'maxlength': '10',
            'inputmode': 'numeric',
        }),
    )

    date_of_birth = JalaliDateField(
        label='تاریخ تولد',
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '۱۳۷۰/۰۵/۲۲',
            'autocomplete': 'off',
            'dir': 'ltr',
        }),
    )

    national_id_image = forms.ImageField(
        label='تصویر کارت ملی',
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/jpeg,image/png',
        }),
    )

    selfie_image = forms.ImageField(
        label='سلفی با کارت ملی',
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/jpeg,image/png',
        }),
    )

    # ── Banking information ────────────────────────────────────────────────

    card_holder_name = forms.CharField(
        label='نام صاحب کارت',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'نام و نام خانوادگی روی کارت',
        }),
    )

    bank_name = forms.CharField(
        label='نام بانک',
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'مثال: ملت، ملی، صادرات',
        }),
    )

    card_last4 = forms.CharField(
        label='چهار رقم آخر کارت',
        max_length=4,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '۴ رقم آخر',
            'dir': 'ltr',
            'maxlength': '4',
            'inputmode': 'numeric',
        }),
    )

    bank_card_image = forms.ImageField(
        label='تصویر کارت بانکی',
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/jpeg,image/png',
        }),
    )

    class Meta:
        model = KYCProfile
        fields = [
            'national_id', 'date_of_birth',
            'national_id_image', 'selfie_image',
            'card_holder_name', 'bank_name', 'card_last4', 'bank_card_image',
        ]

    def clean_national_id(self):
        value = self.cleaned_data.get('national_id', '').strip()
        value = _normalize_digits(value)
        if not value.isdigit() or len(value) != 10:
            raise forms.ValidationError('کد ملی باید دقیقا ۱۰ رقم باشد.')
        return value

    def clean_card_last4(self):
        value = self.cleaned_data.get('card_last4', '').strip()
        if not value:
            return value
        value = _normalize_digits(value)
        if not value.isdigit() or len(value) != 4:
            raise forms.ValidationError('چهار رقم آخر کارت باید دقیقاً ۴ رقم باشد.')
        return value

    def clean_national_id_image(self):
        f = self.cleaned_data.get('national_id_image')
        validate_kyc_image(f)
        return f

    def clean_selfie_image(self):
        f = self.cleaned_data.get('selfie_image')
        validate_kyc_image(f)
        return f

    def clean_bank_card_image(self):
        f = self.cleaned_data.get('bank_card_image')
        validate_kyc_image(f)
        return f
