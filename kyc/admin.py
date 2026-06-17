from django.contrib import admin
from django.utils.html import format_html

from .models import KYCProfile, KYCSiteSettings


# ── KYCProfile ─────────────────────────────────────────────────────────────

@admin.register(KYCProfile)
class KYCProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'national_id',
        'status',
        'created_at',
        'national_id_thumbnail',
        'selfie_thumbnail',
    ]
    list_filter = ['status']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'national_id']
    ordering = ['-created_at']
    readonly_fields = [
        'created_at',
        'updated_at',
        'national_id_preview',
        'selfie_preview',
    ]

    fieldsets = (
        (None, {
            'fields': ('user', 'status'),
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
        ('تاریخ‌ها', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

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

    @admin.display(description='کارت ملی')
    def national_id_thumbnail(self, obj):
        return self._img_tag(obj.national_id_image, height=50)

    @admin.display(description='سلفی')
    def selfie_thumbnail(self, obj):
        return self._img_tag(obj.selfie_image, height=50)

    @admin.display(description='پیش‌نمایش کارت ملی')
    def national_id_preview(self, obj):
        return self._img_tag(obj.national_id_image, height=200)

    @admin.display(description='پیش‌نمایش سلفی')
    def selfie_preview(self, obj):
        return self._img_tag(obj.selfie_image, height=200)


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
