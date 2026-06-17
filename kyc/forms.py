import jdatetime
from django import forms

from .models import KYCProfile

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
            'accept': 'image/*',
        }),
    )

    selfie_image = forms.ImageField(
        label='سلفی با کارت ملی',
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*',
        }),
    )

    class Meta:
        model = KYCProfile
        fields = ['national_id', 'date_of_birth', 'national_id_image', 'selfie_image']

    def clean_national_id(self):
        value = self.cleaned_data.get('national_id', '').strip()
        value = _normalize_digits(value)
        if not value.isdigit() or len(value) != 10:
            raise forms.ValidationError('کد ملی باید دقیقا ۱۰ رقم باشد.')
        return value
