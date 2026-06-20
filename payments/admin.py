from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from .models import Payment


# ── Status badge styles ─────────────────────────────────────────────────────

_STATUS_STYLES = {
    Payment.STATUS_SUBMITTED: ('background:#cfe2ff;color:#084298', 'ارسال شده'),
    Payment.STATUS_APPROVED:  ('background:#d1e7dd;color:#0a3622', 'تأیید شده'),
    Payment.STATUS_REJECTED:  ('background:#f8d7da;color:#58151c', 'رد شده'),
}
_BADGE_BASE = (
    'display:inline-block;padding:3px 10px;border-radius:12px;'
    'font-size:0.78rem;font-weight:600;white-space:nowrap'
)


# ── Bulk actions ────────────────────────────────────────────────────────────

@admin.action(description='✅ تأیید پرداخت‌های انتخاب‌شده')
def approve_payments(modeladmin, request, queryset):
    now = timezone.now()
    count = queryset.filter(status=Payment.STATUS_SUBMITTED).update(
        status=Payment.STATUS_APPROVED,
        reviewed_at=now,
        reviewed_by=request.user,
    )
    # Re-fetch to fire signals individually (update() bypasses signals)
    for payment in queryset.filter(status=Payment.STATUS_APPROVED, reviewed_at=now):
        payment._previous_status = Payment.STATUS_SUBMITTED
        payment.save(update_fields=['status'])  # trigger signal
    messages.success(request, f'{count} پرداخت تأیید شد.')


@admin.action(description='❌ رد پرداخت‌های انتخاب‌شده')
def reject_payments(modeladmin, request, queryset):
    now = timezone.now()
    count = queryset.filter(status=Payment.STATUS_SUBMITTED).update(
        status=Payment.STATUS_REJECTED,
        reviewed_at=now,
        reviewed_by=request.user,
    )
    for payment in queryset.filter(status=Payment.STATUS_REJECTED, reviewed_at=now):
        payment._previous_status = Payment.STATUS_SUBMITTED
        payment.save(update_fields=['status'])
    messages.success(request, f'{count} پرداخت رد شد.')


# ── PaymentAdmin ────────────────────────────────────────────────────────────

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):

    list_display = [
        '_order_link',
        '_status_badge',
        '_amount_display',
        'reference_number',
        '_submitted_at_display',
        '_reviewed_at_display',
        'reviewed_by',
        '_receipt_link',
    ]
    list_filter  = ['status', 'submitted_at']
    search_fields = [
        'order__order_number',
        'reference_number',
        'order__user__email',
        'order__user__first_name',
        'order__user__last_name',
    ]
    ordering = ['-submitted_at']
    actions  = [approve_payments, reject_payments]

    readonly_fields = [
        'order', 'amount', 'currency',
        'submitted_at', 'reviewed_at',
        'receipt_preview',
    ]

    fieldsets = (
        ('اطلاعات سفارش', {
            'fields': ('order', 'amount', 'currency'),
        }),
        ('رسید پرداخت', {
            'fields': ('receipt_file', 'receipt_preview', 'reference_number'),
        }),
        ('بررسی', {
            'fields': ('status', 'rejection_note', 'reviewed_by', 'reviewed_at'),
        }),
        ('زمان‌بندی', {
            'fields': ('submitted_at',),
        }),
    )

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .select_related('order', 'order__user', 'reviewed_by')
        )

    # ── List columns ─────────────────────────────────────────────────────────

    @admin.display(description='سفارش', ordering='order__order_number')
    def _order_link(self, obj):
        from django.urls import reverse
        url = reverse('admin:orders_order_change', args=[obj.order_id])
        return format_html(
            '<a href="{}" style="font-family:monospace;font-weight:600;'
            'font-size:0.82rem;color:#0d6efd">{}</a>'
            '<br><span style="font-size:0.76rem;color:#6c757d">{}</span>',
            url,
            obj.order.order_number,
            obj.order.user.email,
        )

    @admin.display(description='وضعیت', ordering='status')
    def _status_badge(self, obj):
        style, label = _STATUS_STYLES.get(
            obj.status, ('background:#e9ecef;color:#495057', obj.status)
        )
        return format_html(
            '<span style="{base};{style}">{label}</span>',
            base=_BADGE_BASE, style=style, label=label,
        )

    @admin.display(description='مبلغ', ordering='amount')
    def _amount_display(self, obj):
        if obj.amount:
            return format_html(
                '<span dir="ltr">{} {}</span>',
                obj.amount, obj.currency or '',
            )
        return '—'

    @admin.display(description='تاریخ ارسال', ordering='submitted_at')
    def _submitted_at_display(self, obj):
        return obj.submitted_at.strftime('%Y/%m/%d %H:%M') if obj.submitted_at else '—'

    @admin.display(description='تاریخ بررسی', ordering='reviewed_at')
    def _reviewed_at_display(self, obj):
        return obj.reviewed_at.strftime('%Y/%m/%d %H:%M') if obj.reviewed_at else '—'

    @admin.display(description='رسید')
    def _receipt_link(self, obj):
        if not obj.receipt_file:
            return '—'
        from django.urls import reverse
        url = reverse('payment_receipt_download', args=[obj.pk])
        return format_html(
            '<a href="{}" target="_blank" rel="noopener" '
            'style="font-size:0.8rem;">مشاهده</a>',
            url,
        )

    # ── Detail view receipt preview ──────────────────────────────────────────

    @admin.display(description='پیش‌نمایش رسید')
    def receipt_preview(self, obj):
        if not obj.receipt_file or not obj.pk:
            return '—'
        from django.urls import reverse
        url = reverse('payment_receipt_download', args=[obj.pk])
        # Show image preview for image files, a generic link for PDFs
        name = obj.filename.lower()
        if name.endswith(('.jpg', '.jpeg', '.png')):
            return format_html(
                '<a href="{url}" target="_blank" rel="noopener">'
                '<img src="{url}" style="max-height:200px;max-width:350px;'
                'border-radius:6px;object-fit:contain;" /></a>',
                url=url,
            )
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">'
            '<i class="bi bi-file-earmark-text"></i> {}</a>',
            url, obj.filename,
        )
