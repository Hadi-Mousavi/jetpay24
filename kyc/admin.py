from django.contrib import admin
from django.utils.html import format_html

from .models import KYCProfile, KYCSiteSettings


# ── Status badge styles ─────────────────────────────────────────────────────

_STATUS_STYLES = {
    KYCProfile.STATUS_NOT_SUBMITTED:   ('background:#e9ecef;color:#495057', 'تکمیل نشده'),
    KYCProfile.STATUS_PENDING:         ('background:#cfe2ff;color:#084298', 'در انتظار بررسی'),
    KYCProfile.STATUS_APPROVED:        ('background:#d1e7dd;color:#0a3622', 'تأیید شده'),
    KYCProfile.STATUS_REJECTED:        ('background:#f8d7da;color:#58151c', 'رد شده'),
    KYCProfile.STATUS_NEEDS_CORRECTION:('background:#fff3cd;color:#664d03', 'نیاز به اصلاح'),
}
_BADGE_BASE = (
    'display:inline-block;padding:3px 10px;border-radius:12px;'
    'font-size:0.78rem;font-weight:600;white-space:nowrap'
)


# ── KYCProfile ─────────────────────────────────────────────────────────────

@admin.register(KYCProfile)
class KYCProfileAdmin(admin.ModelAdmin):

    list_display = [
        'user',
        '_status_badge',
        'national_id',
        'card_last4',
        'created_at',
        'national_id_thumbnail',
        'selfie_thumbnail',
        'bank_card_thumbnail',
    ]
    list_filter = ['status', 'created_at']
    search_fields = [
        'user__email',
        'user__first_name',
        'user__last_name',
        'national_id',
        'card_last4',
    ]
    ordering = ['-created_at']

    readonly_fields = [
        'created_at',
        'updated_at',
        'national_id_preview',
        'selfie_preview',
        'bank_card_preview',
    ]

    fieldsets = (
        (None, {
            'fields': ('user', 'status', 'admin_note'),
        }),
        ('اطلاعات هویتی', {
            'fields': ('national_id', 'date_of_birth'),
        }),
        ('مدارک تصویری', {
            'fields': (
                'national_id_image',
                'national_id_preview',
                'selfie_image',
                'selfie_preview',
            ),
        }),
        ('اطلاعات بانکی', {
            'fields': (
                'card_holder_name',
                'bank_name',
                'card_last4',
                'bank_card_image',
                'bank_card_preview',
            ),
        }),
        ('تاریخ‌ها', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

    # ── Shared image helper ──────────────────────────────────────────────────

    def _img_tag(self, image_field, height):
        if not image_field or not image_field.name:
            return '—'
        try:
            url = image_field.url
        except ValueError:
            return '—'
        return format_html(
            '<a href="{url}" target="_blank" rel="noopener">'
            '<img src="{url}" height="{h}" style="border-radius:4px;object-fit:cover;" />'
            '</a>',
            url=url,
            h=height,
        )

    # ── List display columns ─────────────────────────────────────────────────

    @admin.display(description='وضعیت', ordering='status')
    def _status_badge(self, obj):
        style, label = _STATUS_STYLES.get(
            obj.status, ('background:#e9ecef;color:#495057', obj.status)
        )
        return format_html(
            '<span style="{base};{style}">{label}</span>',
            base=_BADGE_BASE, style=style, label=label,
        )

    @admin.display(description='کارت ملی')
    def national_id_thumbnail(self, obj):
        return self._img_tag(obj.national_id_image, height=50)

    @admin.display(description='سلفی')
    def selfie_thumbnail(self, obj):
        return self._img_tag(obj.selfie_image, height=50)

    @admin.display(description='کارت بانکی')
    def bank_card_thumbnail(self, obj):
        return self._img_tag(obj.bank_card_image, height=50)

    # ── Detail view previews ─────────────────────────────────────────────────

    @admin.display(description='پیش‌نمایش کارت ملی')
    def national_id_preview(self, obj):
        return self._img_tag(obj.national_id_image, height=200)

    @admin.display(description='پیش‌نمایش سلفی')
    def selfie_preview(self, obj):
        return self._img_tag(obj.selfie_image, height=200)

    @admin.display(description='پیش‌نمایش کارت بانکی')
    def bank_card_preview(self, obj):
        return self._img_tag(obj.bank_card_image, height=200)


# ── KYCSiteSettings (singleton) ────────────────────────────────────────────

@admin.register(KYCSiteSettings)
class KYCSiteSettingsAdmin(admin.ModelAdmin):
    """
    Singleton admin: only one KYCSiteSettings row is allowed.
    The admin can upload/replace the guide image but cannot delete the row
    or create a second one.
    """

    fieldsets = (
        ('تصویر راهنما', {
            'fields': ('guide_image', 'guide_image_preview'),
            'description': (
                'این تصویر در صفحه احراز هویت کاربران در کنار فرم نمایش داده می‌شود.'
            ),
        }),
    )
    readonly_fields = ['guide_image_preview']

    def has_add_permission(self, request):
        return not KYCSiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='پیش‌نمایش تصویر راهنما')
    def guide_image_preview(self, obj):
        if obj and obj.guide_image and obj.guide_image.name:
            try:
                url = obj.guide_image.url
                return format_html(
                    '<a href="{url}" target="_blank" rel="noopener">'
                    '<img src="{url}" style="max-height:220px;max-width:380px;'
                    'border-radius:8px;object-fit:contain;" /></a>',
                    url=url,
                )
            except ValueError:
                pass
        return '—'
