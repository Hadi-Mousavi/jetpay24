from .services import count_unread_notifications


def unread_notifications(request):
    if request.user.is_authenticated and not request.user.is_staff:
        return {
            'unread_notification_count': count_unread_notifications(request.user),
        }
    return {'unread_notification_count': 0}
