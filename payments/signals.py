"""
Payment signal handlers.

1. _cache_payment_status  (pre_save)
   Caches the previous status before a Payment row is saved so the
   post_save handler can detect actual status transitions.

2. _on_payment_saved  (post_save)
   When payment status transitions to approved:
     - Move the order to in_progress.
     - Create a TYPE_PAYMENT_APPROVED notification.
   When payment status transitions to rejected:
     - Create a TYPE_PAYMENT_REJECTED notification.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from notifications.models import Notification
from notifications.services import create_notification

from .models import Payment


@receiver(pre_save, sender=Payment)
def _cache_payment_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._previous_status = (
                Payment.objects.filter(pk=instance.pk)
                .values_list('status', flat=True)
                .first()
            )
        except Payment.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


@receiver(post_save, sender=Payment)
def _on_payment_saved(sender, instance, created, **kwargs):
    previous = getattr(instance, '_previous_status', None)

    # ── Newly submitted ────────────────────────────────────────────────────
    if created:
        return  # no notification on submission; order detail already confirms it

    # No status change — nothing to do
    if previous == instance.status:
        return

    order = instance.order

    # ── Approved: advance order to in_progress ─────────────────────────────
    if instance.status == Payment.STATUS_APPROVED:
        # Stamp the review timestamp if not already set by admin
        if not instance.reviewed_at:
            Payment.objects.filter(pk=instance.pk).update(reviewed_at=timezone.now())

        from orders.models import Order
        if order.status == Order.STATUS_WAITING_PAYMENT:
            order.status = Order.STATUS_IN_PROGRESS
            order.save(update_fields=['status', 'updated_at'])

        create_notification(
            user=order.user,
            title='پرداخت تأیید شد',
            message=(
                f'پرداخت سفارش {order.order_number} تأیید شد '
                'و سفارش شما وارد مرحله انجام شد.'
            ),
            notification_type=Notification.TYPE_PAYMENT_APPROVED,
        )

    # ── Rejected: notify customer ──────────────────────────────────────────
    elif instance.status == Payment.STATUS_REJECTED:
        if not instance.reviewed_at:
            Payment.objects.filter(pk=instance.pk).update(reviewed_at=timezone.now())

        note = instance.rejection_note.strip() if instance.rejection_note else ''
        message = (
            f'پرداخت سفارش {order.order_number} رد شد. {note}'
            if note
            else f'پرداخت سفارش {order.order_number} رد شد. لطفاً مجدداً اقدام کنید.'
        )
        create_notification(
            user=order.user,
            title='پرداخت رد شد',
            message=message,
            notification_type=Notification.TYPE_PAYMENT_REJECTED,
        )
