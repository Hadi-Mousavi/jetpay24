from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'title', 'message']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    fieldsets = (
        (None, {
            'fields': ('user', 'title', 'message', 'notification_type', 'is_read'),
        }),
        ('زمان‌بندی', {
            'fields': ('created_at',),
        }),
    )
