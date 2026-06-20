from django.conf import settings
from django.db import models

from orders.models import Order
from orders.storage import PrivateFileSystemStorage


class Payment(models.Model):
    """
    Records a single payment submission for an order.

    Lifecycle:
        submitted  →  approved  (order moves to in_progress automatically)
                   ↘  rejected  →  customer may submit again

    Receipt storage:
        Stored at PRIVATE_MEDIA_ROOT via PrivateFileSystemStorage.
        No public URL; served only through the authenticated download view.
    """

    STATUS_SUBMITTED = 'submitted'
    STATUS_APPROVED  = 'approved'
    STATUS_REJECTED  = 'rejected'

    STATUS_CHOICES = [
        (STATUS_SUBMITTED, 'ارسال شده'),
        (STATUS_APPROVED,  'تأیید شده'),
        (STATUS_REJECTED,  'رد شده'),
    ]

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='سفارش',
    )
    amount = models.DecimalField(
        max_digits=14, decimal_places=2,
        null=True, blank=True,
        verbose_name='مبلغ',
    )
    currency = models.CharField(
        max_length=10, blank=True,
        verbose_name='ارز',
    )
    receipt_file = models.FileField(
        storage=PrivateFileSystemStorage(),
        upload_to='payments/receipts/%Y/%m/',
        verbose_name='فایل رسید',
    )
    reference_number = models.CharField(
        max_length=100, blank=True,
        verbose_name='شماره مرجع / پیگیری',
        help_text='شماره مرجع تراکنش بانکی (اختیاری)',
    )
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default=STATUS_SUBMITTED,
        db_index=True,
        verbose_name='وضعیت',
    )
    rejection_note = models.TextField(
        blank=True,
        verbose_name='دلیل رد',
        help_text='در صورت رد پرداخت، این متن به مشتری نمایش داده می‌شود.',
    )
    submitted_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ارسال',
    )
    reviewed_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='تاریخ بررسی',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_payments',
        limit_choices_to={'is_staff': True},
        verbose_name='بررسی‌کننده',
    )

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'پرداخت'
        verbose_name_plural = 'پرداخت‌ها'

    def __str__(self):
        return f'{self.order.order_number} — {self.get_status_display()}'

    # ── helpers ───────────────────────────────────────────────────────────────

    @property
    def filename(self):
        return self.receipt_file.name.split('/')[-1] if self.receipt_file else ''

    @property
    def is_submitted(self):
        return self.status == self.STATUS_SUBMITTED

    @property
    def is_approved(self):
        return self.status == self.STATUS_APPROVED

    @property
    def is_rejected(self):
        return self.status == self.STATUS_REJECTED
