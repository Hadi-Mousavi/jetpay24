"""
Presentation helpers for the order detail timeline.

Transforms raw events from _build_order_timeline() for display only —
does not add, remove, or reorder underlying events.
"""

from django.utils import timezone

TITLE_DISPLAY = {
    'پیام جدید ثبت شد': 'پیام جدید از تیم جت‌پی‌۲۴',
    'فایل جدید بارگذاری شد': 'مدرک جدید به سفارش اضافه شد',
    'مسئول سفارش تعیین شد': 'کارشناس سفارش تعیین شد',
}


def _timestamp_key(ts):
    if ts is None:
        return None
    if timezone.is_aware(ts):
        ts = timezone.localtime(ts)
    return ts.replace(microsecond=0)


def _event_color(event):
    # Status-history events carry a pre-computed color hint; honour it first.
    if 'color_hint' in event:
        return event['color_hint']

    sort_order = event.get('sort_order', 0)
    title = event.get('title', '')
    emoji = event.get('emoji', '')

    if sort_order == 10:
        return 'primary'
    if sort_order in (55, 60):
        return 'gray'
    if sort_order == 50:
        return 'purple'
    if sort_order == 30:
        return 'indigo'
    if sort_order == 40:
        return 'gray'
    if sort_order in (45, 46, 47):   # payment events
        if emoji == '💳' or 'رسید' in title:
            return 'yellow'
        if emoji == '💰' or 'تأیید' in title:
            return 'green'
        if emoji == '❌' or 'رد' in title:
            return 'red'
        return 'yellow'
    if sort_order == 20:
        if emoji == '🚀' or 'در حال انجام' in title:
            return 'orange'
        if emoji == '🔍' or 'بررسی' in title:
            return 'yellow'
        if emoji == '✅' or 'تکمیل' in title:
            return 'green'
        if emoji == '❌' or 'رد' in title or 'لغو' in title:
            return 'red'
        if emoji in ('💳', '⚠️') or 'پرداخت' in title or 'اقدام' in title:
            return 'yellow'
        return 'primary'
    return 'primary'


def _display_title(event):
    return TITLE_DISPLAY.get(event.get('title', ''), event.get('title', ''))


def prepare_timeline_for_display(events):
    """
    Enrich timeline events with display metadata and group by exact timestamp.
    Input order is preserved (newest first).
    """
    if not events:
        return []

    groups = []
    current_key = None
    current_group = None

    for index, event in enumerate(events):
        ts_key = _timestamp_key(event.get('timestamp'))
        display_event = {
            **event,
            'title': _display_title(event),
            'color': _event_color(event),
            'is_latest': index == 0,
        }

        if ts_key != current_key:
            current_group = {
                'timestamp': event.get('timestamp'),
                'is_latest': index == 0,
                'events': [display_event],
            }
            groups.append(current_group)
            current_key = ts_key
        else:
            current_group['events'].append(display_event)

    return groups
