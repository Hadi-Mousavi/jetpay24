from .models import Notification


def create_notification(*, user, title, message, notification_type):
    """Create an in-app notification for a customer."""
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
    )


def count_unread_notifications(user):
    return Notification.objects.filter(user=user, is_read=False).count()
