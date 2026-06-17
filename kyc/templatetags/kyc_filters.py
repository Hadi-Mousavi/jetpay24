import jdatetime
from django import template

register = template.Library()

_EN_TO_FA = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')


@register.filter
def to_persian_digits(value):
    """Translate ASCII digits 0-9 to Persian digits ۰-۹."""
    if value is None:
        return ''
    return str(value).translate(_EN_TO_FA)


@register.filter
def to_jalali(value):
    """Convert a Gregorian date/datetime to a Persian (Jalali) date string with Persian digits.

    Output format: ۱۳۷۰/۰۵/۲۲
    Returns empty string for falsy input; falls back to str(value) on conversion error.
    """
    if not value:
        return ''
    try:
        date_obj = value.date() if hasattr(value, 'date') else value
        jd = jdatetime.date.fromgregorian(date=date_obj)
        latin = f'{jd.year:04d}/{jd.month:02d}/{jd.day:02d}'
        return latin.translate(_EN_TO_FA)
    except Exception:
        return str(value)
