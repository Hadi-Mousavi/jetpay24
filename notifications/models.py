from django.conf import settings
from django.db import models


class Notification(models.Model):

    TYPE_ORDER_CREATED        = 'ORDER_CREATED'
    TYPE_ORDER_STATUS_CHANGED = 'ORDER_STATUS_CHANGED'
    TYPE_ADMIN_MESSAGE        = 'ADMIN_MESSAGE'
    TYPE_KYC_APPROVED         = 'KYC_APPROVED'
    TYPE_KYC_REJECTED         = 'KYC_REJECTED'
    TYPE_KYC_NEEDS_CORRECTION = 'KYC_NEEDS_CORRECTION'
    TYPE_PAYMENT_APPROVED     = 'PAYMENT_APPROVED'
    TYPE_PAYMENT_REJECTED     = 'PAYMENT_REJECTED'

    TYPE_CHOICES = [
        (TYPE_ORDER_CREATED,        'ثبت سفارش'),
        (TYPE_ORDER_STATUS_CHANGED, 'تغییر وضعیت سفارش'),
        (TYPE_ADMIN_MESSAGE,        'پیام ادمین'),
        (TYPE_KYC_APPROVED,         'تأیید احراز هویت'),
        (TYPE_KYC_REJECTED,         'رد احراز هویت'),
        (TYPE_KYC_NEEDS_CORRECTION, 'درخواست اصلاح احراز هویت'),
        (TYPE_PAYMENT_APPROVED,     'تأیید پرداخت'),
        (TYPE_PAYMENT_REJECTED,     'رد پرداخت'),
    ]

    DISPLAY_TYPES = {
        TYPE_ORDER_CREATED:        'neutral',
        TYPE_ORDER_STATUS_CHANGED: 'info',
        TYPE_ADMIN_MESSAGE:        'primary',
        TYPE_KYC_APPROVED:         'success',
        TYPE_KYC_REJECTED:         'danger',
        TYPE_KYC_NEEDS_CORRECTION: 'warning',
        TYPE_PAYMENT_APPROVED:     'success',
        TYPE_PAYMENT_REJECTED:     'danger',
    }

    DISPLAY_ICONS = {
        TYPE_ORDER_CREATED:        'bi-box-seam-fill',
        TYPE_ORDER_STATUS_CHANGED: 'bi-arrow-repeat',
        TYPE_ADMIN_MESSAGE:        'bi-chat-dots-fill',
        TYPE_KYC_APPROVED:         'bi-shield-check',
        TYPE_KYC_REJECTED:         'bi-exclamation-triangle-fill',
        TYPE_KYC_NEEDS_CORRECTION: 'bi-pencil-square',
        TYPE_PAYMENT_APPROVED:     'bi-credit-card-2-front-fill',
        TYPE_PAYMENT_REJECTED:     'bi-credit-card-fill',
    }

    DISPLAY_EMOJIS = {
        TYPE_ORDER_CREATED:        '📦',
        TYPE_ORDER_STATUS_CHANGED: '🔄',
        TYPE_ADMIN_MESSAGE:        '💬',
        TYPE_KYC_APPROVED:         '✅',
        TYPE_KYC_REJECTED:         '⚠️',
        TYPE_KYC_NEEDS_CORRECTION: '✏️',
        TYPE_PAYMENT_APPROVED:     '💰',
        TYPE_PAYMENT_REJECTED:     '❌',
    }

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='کاربر',
    )
    title = models.CharField(max_length=200, verbose_name='عنوان')
    message = models.TextField(verbose_name='متن')
    notification_type = models.CharField(
        max_length=30,
        choices=TYPE_CHOICES,
        db_index=True,
        verbose_name='نوع اعلان',
    )
    is_read = models.BooleanField(default=False, db_index=True, verbose_name='خوانده شده')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='تاریخ ایجاد')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'اعلان'
        verbose_name_plural = 'اعلان‌ها'
        indexes = [
            models.Index(fields=['user', 'is_read', '-created_at'], name='notif_user_read_created_idx'),
        ]

    def __str__(self):
        return f'{self.user} — {self.title}'

    @property
    def display_type(self):
        return self.DISPLAY_TYPES.get(self.notification_type, 'neutral')

    @property
    def display_icon(self):
        return self.DISPLAY_ICONS.get(self.notification_type, 'bi-bell-fill')

    @property
    def display_emoji(self):
        return self.DISPLAY_EMOJIS.get(self.notification_type, '🔔')
