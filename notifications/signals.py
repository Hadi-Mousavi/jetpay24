from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from kyc.models import KYCProfile
from orders.models import Order, OrderMessage

from .models import Notification
from .services import create_notification


@receiver(pre_save, sender=Order)
def _cache_order_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._previous_status = (
                Order.objects.filter(pk=instance.pk)
                .values_list('status', flat=True)
                .first()
            )
        except Order.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


@receiver(post_save, sender=Order)
def _notify_order_events(sender, instance, created, **kwargs):
    if created:
        create_notification(
            user=instance.user,
            title='سفارش ثبت شد',
            message=f'سفارش {instance.order_number} با موفقیت ثبت شد.',
            notification_type=Notification.TYPE_ORDER_CREATED,
        )
        return

    previous = getattr(instance, '_previous_status', None)
    if previous and previous != instance.status:
        create_notification(
            user=instance.user,
            title='وضعیت سفارش تغییر کرد',
            message=(
                f'وضعیت سفارش {instance.order_number} '
                f'به «{instance.status_label}» تغییر یافت.'
            ),
            notification_type=Notification.TYPE_ORDER_STATUS_CHANGED,
        )


@receiver(post_save, sender=OrderMessage)
def _notify_admin_message(sender, instance, created, **kwargs):
    if not created:
        return
    if not instance.sender or not instance.sender.is_staff:
        return
    preview = instance.message.strip()
    if len(preview) > 120:
        preview = preview[:117] + '…'
    create_notification(
        user=instance.order.user,
        title='پیام جدید از تیم جت‌پی‌۲۴',
        message=preview or 'پیام جدیدی برای سفارش شما ثبت شد.',
        notification_type=Notification.TYPE_ADMIN_MESSAGE,
    )


@receiver(pre_save, sender=KYCProfile)
def _cache_kyc_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._previous_status = (
                KYCProfile.objects.filter(pk=instance.pk)
                .values_list('status', flat=True)
                .first()
            )
        except KYCProfile.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


@receiver(post_save, sender=KYCProfile)
def _notify_kyc_status(sender, instance, created, **kwargs):
    if created:
        return

    previous = getattr(instance, '_previous_status', None)
    if previous == instance.status:
        return

    if instance.status == KYCProfile.STATUS_APPROVED:
        create_notification(
            user=instance.user,
            title='احراز هویت تأیید شد',
            message='احراز هویت شما توسط تیم جت‌پی‌۲۴ تأیید شد.',
            notification_type=Notification.TYPE_KYC_APPROVED,
        )
    elif instance.status == KYCProfile.STATUS_REJECTED:
        create_notification(
            user=instance.user,
            title='احراز هویت رد شد',
            message='احراز هویت شما نیاز به اصلاح دارد. لطفاً مجدداً ارسال کنید.',
            notification_type=Notification.TYPE_KYC_REJECTED,
        )
