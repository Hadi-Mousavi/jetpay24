from django.utils import timezone


def relative_time_fa(dt):
    """Return a short Persian relative time string for notification dropdowns."""
    if not dt:
        return ''

    now = timezone.now()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())

    diff = now - dt
    seconds = max(int(diff.total_seconds()), 0)

    if seconds < 60:
        return 'همین الان'

    minutes = seconds // 60
    if minutes < 60:
        return f'{minutes} دقیقه پیش'

    hours = minutes // 60
    if hours < 24:
        return f'{hours} ساعت پیش'

    days = hours // 24
    if days == 1:
        return 'دیروز'
    if days < 7:
        return f'{days} روز پیش'

    return dt.strftime('%Y/m/d')


def serialize_notification(notification):
    return {
        'id': notification.pk,
        'title': notification.title,
        'message': notification.message,
        'emoji': notification.display_emoji,
        'icon': notification.display_icon,
        'display_type': notification.display_type,
        'is_read': notification.is_read,
        'relative_time': relative_time_fa(notification.created_at),
    }
