import jdatetime
from django import template
from django.utils import timezone

register = template.Library()

_EN_TO_FA = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')

_PERSIAN_MONTHS = (
    '', 'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
    'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند',
)


def _to_persian_digits(value):
    return str(value).translate(_EN_TO_FA)


@register.filter
def to_jalali_datetime(value):
    """
    Format a datetime as Persian Jalali with named month and Persian digits.
    Example: ۱۸ خرداد ۱۴۰۵ - ۰۴:۵۶
    """
    if not value:
        return ''

    try:
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        jd = jdatetime.datetime.fromgregorian(datetime=value.replace(tzinfo=None))
        month_name = _PERSIAN_MONTHS[jd.month]
        latin = f'{jd.day} {month_name} {jd.year} - {jd.hour:02d}:{jd.minute:02d}'
        return _to_persian_digits(latin)
    except Exception:
        return str(value)
