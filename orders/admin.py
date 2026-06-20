from django import forms
from django.contrib import admin, messages
from django.db.models import Count, FileField, Q
from django.forms.widgets import ClearableFileInput
from django.urls import reverse
from django.utils.html import format_html

from .forms import ValidatedOrderAttachmentForm, ValidatedOrderMessageAttachmentForm
from .models import (
    Category, Order, OrderAttachment,
    OrderMessage, OrderMessageAttachment,
    OrderStatusHistory, SubCategory,
)
from .workflow import (
    InvalidTransition, STATUS_LABELS,
    get_allowed_transitions, is_recovery_transition, validate_transition,
)


# ── Private-storage-safe file widget ──────────────────────────────────────────
#
# Problem: Django's ClearableFileInput.is_initial() contains:
#
#     return bool(value and getattr(value, 'url', False))
#
# PrivateFileSystemStorage sets base_url=None, so accessing .url raises
# ValueError (not AttributeError).  getattr's default only suppresses
# AttributeError, so the ValueError propagates and crashes the admin page.
#
# Fix: override is_initial() to check value.name instead of value.url.
# Returning False suppresses the "Currently: <link>" section in the widget
# template, so .url is never called.  Existing-file information is shown
# instead via the _file_info readonly column on each inline.

class PrivateFileWidget(ClearableFileInput):
    """
    ClearableFileInput that never calls file.url.

    Safe for use with PrivateFileSystemStorage (base_url=None).
    Always renders only the file-upload input; file metadata is shown
    in the companion _file_info readonly column instead.
    """

    def is_initial(self, value):
        # Detect an existing file by name only — never touch .url.
        return False


def _fmt_size(n_bytes):
    """Human-readable file size."""
    if n_bytes < 1024:
        return f'{n_bytes} B'
    if n_bytes < 1024 * 1024:
        return f'{n_bytes / 1024:.1f} KB'
    return f'{n_bytes / (1024 * 1024):.1f} MB'


def _order_att_info(obj, download_url_name):
    """
    Return a safe HTML snippet with filename, size, and a download link.

    Uses storage.size(name) rather than file.url — works with private storage.
    """
    if not obj.pk or not obj.file or not obj.file.name:
        return '—'

    filename = obj.filename          # .name.split('/')[-1] — no .url call

    try:
        size_str = _fmt_size(obj.file.size)   # calls storage.size(name), not .url
    except (FileNotFoundError, OSError, NotImplementedError):
        size_str = 'فایل روی دیسک موجود نیست'

    dl_url = reverse(download_url_name, args=[obj.pk])

    return format_html(
        '<div style="line-height:1.7;font-size:.85em">'
        '<a href="{}" target="_blank" style="font-weight:600;text-decoration:none">'
        '⬇ {}</a><br>'
        '<span style="color:#6c757d">{}</span>'
        '</div>',
        dl_url, filename, size_str,
    )


# ── Sub-model inlines ─────────────────────────────────────────────────────────

class SubCategoryInline(admin.TabularInline):
    model       = SubCategory
    extra       = 1
    fields      = ['title', 'description', 'is_active', 'display_order']
    ordering    = ['display_order', 'title']


class OrderAttachmentInline(admin.TabularInline):
    model           = OrderAttachment
    form            = ValidatedOrderAttachmentForm
    extra           = 0
    readonly_fields = ['_file_info', 'created_at']
    fields          = ['_file_info', 'file', 'title', 'uploaded_by', 'created_at']
    formfield_overrides = {
        FileField: {'widget': PrivateFileWidget},
    }

    @admin.display(description='فایل پیوست')
    def _file_info(self, obj):
        return _order_att_info(obj, 'order_attachment_download')


class OrderMessageAttachmentInline(admin.TabularInline):
    model           = OrderMessageAttachment
    form            = ValidatedOrderMessageAttachmentForm
    extra           = 0
    readonly_fields = ['_file_info', 'uploaded_at']
    fields          = ['_file_info', 'file', 'uploaded_at']
    formfield_overrides = {
        FileField: {'widget': PrivateFileWidget},
    }

    @admin.display(description='فایل پیوست')
    def _file_info(self, obj):
        return _order_att_info(obj, 'message_attachment_download')


class OrderMessageInline(admin.StackedInline):
    model           = OrderMessage
    extra           = 1
    readonly_fields = ['created_at', 'is_read']
    fields          = ['sender', 'message', 'is_read', 'created_at']
    ordering        = ['created_at']
    show_change_link = True


class OrderStatusHistoryInline(admin.TabularInline):
    model           = OrderStatusHistory
    extra           = 0
    can_delete      = False
    readonly_fields = [
        '_old_label', '_new_label', 'changed_by', 'note', 'created_at',
    ]
    fields          = ['_old_label', '_new_label', 'changed_by', 'note', 'created_at']
    ordering        = ['-created_at']

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description='وضعیت قبلی')
    def _old_label(self, obj):
        return STATUS_LABELS.get(obj.old_status, obj.old_status)

    @admin.display(description='وضعیت جدید')
    def _new_label(self, obj):
        return STATUS_LABELS.get(obj.new_status, obj.new_status)


# ── Category ──────────────────────────────────────────────────────────────────

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display        = ['title', 'slug', 'is_active', 'display_order', '_sub_count', 'created_at']
    list_filter         = ['is_active']
    search_fields       = ['title', 'slug']
    prepopulated_fields = {'slug': ('title',)}
    inlines             = [SubCategoryInline]
    list_editable       = ['is_active', 'display_order']

    @admin.display(description='تعداد زیر دسته‌ها')
    def _sub_count(self, obj):
        return obj.subcategories.count()


# ── SubCategory ───────────────────────────────────────────────────────────────

@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display  = ['title', 'category', 'is_active', 'display_order']
    list_filter   = ['is_active', 'category']
    search_fields = ['title', 'category__title']
    list_editable = ['is_active', 'display_order']


# ── Order — status badge colours ──────────────────────────────────────────────

_STATUS_BADGE_STYLES = {
    Order.STATUS_DRAFT:            ('background:#e9ecef;color:#495057',  'پیش‌نویس'),
    Order.STATUS_SUBMITTED:        ('background:#cfe2ff;color:#084298',  'ثبت شده'),
    Order.STATUS_UNDER_REVIEW:     ('background:#cff4fc;color:#055160',  'در حال بررسی'),
    Order.STATUS_WAITING_PAYMENT:  ('background:#fff3cd;color:#664d03',  'در انتظار پرداخت'),
    Order.STATUS_PAYMENT_REJECTED: ('background:#f8d7da;color:#58151c',  'پرداخت رد شده'),
    Order.STATUS_IN_PROGRESS:      ('background:#d1ecf1;color:#0c5460',  'در حال انجام'),
    Order.STATUS_WAITING_CUSTOMER: ('background:#fff3cd;color:#664d03',  'منتظر اقدام مشتری'),
    Order.STATUS_COMPLETED:        ('background:#d1e7dd;color:#0a3622',  'تکمیل شده'),
    Order.STATUS_REJECTED:         ('background:#f8d7da;color:#58151c',  'رد شده'),
    Order.STATUS_CANCELLED:        ('background:#e9ecef;color:#495057',  'لغو شده'),
}

_BADGE_BASE = (
    'display:inline-block;padding:3px 10px;border-radius:12px;'
    'font-size:0.78rem;font-weight:600;white-space:nowrap;letter-spacing:.02em'
)


# ── Workflow-aware ModelForm ───────────────────────────────────────────────────

class OrderAdminForm(forms.ModelForm):
    """
    Admin form with:
      - status field limited to allowed workflow transitions
      - status_change_note extra field stored in OrderStatusHistory
      - server-side transition validation (defence-in-depth)
    """

    status_change_note = forms.CharField(
        label='یادداشت تغییر وضعیت',
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 2,
            'placeholder': 'توضیح دلیل تغییر وضعیت برای مشتری (اختیاری)…',
            'style': 'font-size:.9em;',
            'dir': 'rtl',
        }),
        help_text='این یادداشت در تاریخچه سفارش ذخیره و برای مشتری نمایش داده می‌شود.',
    )

    class Meta:
        model  = Order
        fields = '__all__'

    def clean_status(self):
        new_status = self.cleaned_data['status']
        if not self.instance.pk:
            return new_status

        # Fetch the committed status from DB (the value BEFORE this form save)
        committed = (
            Order.objects.filter(pk=self.instance.pk)
            .values_list('status', flat=True)
            .first()
        )
        if committed and committed != new_status:
            try:
                validate_transition(committed, new_status)
            except InvalidTransition as exc:
                raise forms.ValidationError(exc.persian_message())
        return new_status


# ── Order — bulk actions ───────────────────────────────────────────────────────

def _make_status_action(target_status, label, icon):
    """Factory that builds a bulk-action function for a given target status."""

    def action(modeladmin, request, queryset):
        updated = 0
        skipped = 0
        for order in queryset.exclude(status=target_status):
            from .workflow import is_valid_transition
            if is_valid_transition(order.status, target_status):
                old = order.status
                order.status = target_status
                order.save()
                OrderStatusHistory.objects.create(
                    order=order,
                    old_status=old,
                    new_status=target_status,
                    changed_by=request.user,
                    note='',
                )
                updated += 1
            else:
                skipped += 1
        if updated:
            messages.success(request, f'{updated} سفارش به وضعیت «{label}» تغییر یافت.')
        if skipped:
            messages.warning(
                request,
                f'{skipped} سفارش به دلیل گردش‌کار نامعتبر تغییر نیافت.',
            )

    action.short_description = f'{icon} {label}'
    action.__name__ = f'mark_as_{target_status}'
    return action


mark_as_under_review = _make_status_action(
    Order.STATUS_UNDER_REVIEW, 'در حال بررسی', '🔍',
)
mark_as_in_progress = _make_status_action(
    Order.STATUS_IN_PROGRESS, 'در حال انجام', '🚀',
)
mark_as_completed = _make_status_action(
    Order.STATUS_COMPLETED, 'تکمیل شده', '✅',
)
mark_as_waiting_customer = _make_status_action(
    Order.STATUS_WAITING_CUSTOMER, 'منتظر اقدام مشتری', '⚠️',
)
mark_as_cancelled = _make_status_action(
    Order.STATUS_CANCELLED, 'لغو شده', '❌',
)


# ── Order ─────────────────────────────────────────────────────────────────────

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):

    form = OrderAdminForm

    # ── list columns ──────────────────────────────────────────────────────────
    list_display = [
        '_tracking_code',
        '_customer_name',
        'category',
        '_status_badge',
        '_assigned_admin_display',
        '_created_at_display',
    ]

    # ── filters ───────────────────────────────────────────────────────────────
    list_filter = [
        'status',
        'category',
        'assigned_admin',
        'created_at',
    ]

    # ── search ────────────────────────────────────────────────────────────────
    search_fields = [
        'order_number',
        'user__first_name',
        'user__last_name',
        'user__email',
        'user__national_id',
        'organization_name',
        'assigned_admin__email',
    ]

    # ── form ──────────────────────────────────────────────────────────────────
    readonly_fields = ['order_number', 'created_at', 'updated_at', '_workflow_hint']
    inlines         = [
        OrderAttachmentInline,
        OrderMessageInline,
        OrderStatusHistoryInline,
    ]
    actions         = [
        mark_as_under_review,
        mark_as_in_progress,
        mark_as_waiting_customer,
        mark_as_completed,
        mark_as_cancelled,
    ]

    fieldsets = (
        ('شماره سفارش', {
            'fields': ('order_number',),
        }),
        ('کاربر', {
            'fields': ('user',),
        }),
        ('جزئیات سفارش', {
            'fields': (
                'category', 'subcategory',
                'organization_name', 'amount', 'currency',
                'deadline', 'description',
            ),
        }),
        ('یادداشت مشتری', {
            'fields': ('customer_note',),
        }),
        ('مدیریت', {
            'fields': (
                '_workflow_hint',
                'status', 'status_change_note',
                'assigned_admin', 'admin_note',
            ),
        }),
        ('زمان‌بندی', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    # ── queryset ──────────────────────────────────────────────────────────────

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .select_related('user', 'assigned_admin', 'category', 'subcategory')
        )

    # ── dynamic status choices ────────────────────────────────────────────────

    def get_form(self, request, obj=None, **kwargs):
        """
        Returns a form class with the status choices restricted to allowed
        workflow transitions for the current order state.
        """
        FormClass = super().get_form(request, obj, **kwargs)
        if obj is None:
            return FormClass

        current = obj.status
        allowed_next = get_allowed_transitions(current)
        all_labels = dict(Order.STATUS_CHOICES)

        # Always include the current status so the dropdown shows it
        restricted_choices = [(current, all_labels.get(current, current))]
        for s in allowed_next:
            label = all_labels.get(s, s)
            if is_recovery_transition(current, s):
                label = f'{label} (بازگشایی سفارش)'
            restricted_choices.append((s, label))

        # Build a one-off subclass so we don't mutate the shared base_fields
        class _WorkflowForm(FormClass):
            def __init__(self_inner, *args, **kw):
                super().__init__(*args, **kw)
                self_inner.fields['status'].choices = restricted_choices

        return _WorkflowForm

    # ── save with history recording ───────────────────────────────────────────

    def save_model(self, request, obj, form, change):
        old_status = None
        if change and 'status' in form.changed_data:
            # Capture old status before super() commits
            old_status = (
                Order.objects.filter(pk=obj.pk)
                .values_list('status', flat=True)
                .first()
            )

        super().save_model(request, obj, form, change)

        if change and old_status and old_status != obj.status:
            OrderStatusHistory.objects.create(
                order=obj,
                old_status=old_status,
                new_status=obj.status,
                changed_by=request.user,
                note=form.cleaned_data.get('status_change_note', ''),
            )

    # ── changelist with stats card ────────────────────────────────────────────

    def changelist_view(self, request, extra_context=None):
        stats = Order.objects.aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(
                status__in=[Order.STATUS_SUBMITTED, Order.STATUS_UNDER_REVIEW],
            )),
            in_progress=Count('id', filter=Q(status=Order.STATUS_IN_PROGRESS)),
            waiting_customer=Count('id', filter=Q(status=Order.STATUS_WAITING_CUSTOMER)),
            completed=Count('id', filter=Q(status=Order.STATUS_COMPLETED)),
        )
        extra_context = extra_context or {}
        extra_context['order_stats'] = stats
        return super().changelist_view(request, extra_context=extra_context)

    # ── display columns ───────────────────────────────────────────────────────

    @admin.display(description='راهنمای گردش‌کار')
    def _workflow_hint(self, obj):
        if not obj or not obj.pk:
            return '—'
        allowed = get_allowed_transitions(obj.status)
        all_labels = dict(Order.STATUS_CHOICES)
        current_label = all_labels.get(obj.status, obj.status)
        if not allowed:
            return format_html(
                '<span style="color:#6c757d;font-size:.88em;">'
                'وضعیت فعلی: <strong>{}</strong> — وضعیت نهایی (بدون تغییر بیشتر)</span>',
                current_label,
            )

        parts = []
        for s in allowed:
            label = all_labels.get(s, s)
            if is_recovery_transition(obj.status, s):
                label = f'{label} ⟵ بازگشایی سفارش'
            parts.append(f'<strong>{label}</strong>')
        arrows = ' &nbsp;،&nbsp; '.join(parts)

        return format_html(
            '<div style="font-size:.88em;line-height:1.8;direction:rtl">'
            'وضعیت فعلی: <strong style="color:#0c5460">{}</strong>'
            '<br>می‌توان تغییر داد به: {}'
            '</div>',
            current_label, arrows,
        )

    @admin.display(description='کد پیگیری', ordering='order_number')
    def _tracking_code(self, obj):
        url = reverse('admin:orders_order_change', args=[obj.pk])
        return format_html(
            '<a href="{}" style="font-family:monospace;font-weight:600;'
            'font-size:0.82rem;letter-spacing:.03em;color:#0d6efd">{}</a>',
            url, obj.order_number,
        )

    @admin.display(description='مشتری', ordering='user__last_name')
    def _customer_name(self, obj):
        full = obj.user.get_full_name() or obj.user.email
        return format_html(
            '<span style="font-weight:600">{}</span>'
            '<br><span style="font-size:0.78rem;color:#6c757d">{}</span>',
            full, obj.user.email,
        )

    @admin.display(description='وضعیت', ordering='status')
    def _status_badge(self, obj):
        style, label = _STATUS_BADGE_STYLES.get(
            obj.status,
            ('background:#e9ecef;color:#495057', obj.status_label),
        )
        return format_html(
            '<span style="{};{}">{}</span>',
            _BADGE_BASE, style, label,
        )

    @admin.display(description='مسئول سفارش', ordering='assigned_admin__last_name')
    def _assigned_admin_display(self, obj):
        if not obj.assigned_admin:
            return format_html('<span style="color:#adb5bd;font-size:0.82rem">—</span>')
        name = obj.assigned_admin.get_full_name() or obj.assigned_admin.email
        return format_html(
            '<span style="font-size:0.88rem;font-weight:600">{}</span>',
            name,
        )

    @admin.display(description='تاریخ ثبت', ordering='created_at')
    def _created_at_display(self, obj):
        return format_html(
            '<span style="font-size:0.82rem;color:#495057;white-space:nowrap">{}</span>',
            obj.created_at.strftime('%Y/%m/%d'),
        )


# ── OrderStatusHistory (standalone) ──────────────────────────────────────────

@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display  = ['order', '_old_label', '_new_label', 'changed_by', 'note', 'created_at']
    list_filter   = ['new_status', 'created_at']
    search_fields = ['order__order_number', 'note']
    readonly_fields = [
        'order', 'old_status', 'new_status', 'changed_by', 'note', 'created_at',
    ]
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description='وضعیت قبلی', ordering='old_status')
    def _old_label(self, obj):
        return STATUS_LABELS.get(obj.old_status, obj.old_status)

    @admin.display(description='وضعیت جدید', ordering='new_status')
    def _new_label(self, obj):
        return STATUS_LABELS.get(obj.new_status, obj.new_status)


# ── OrderMessage (standalone, for search / direct access) ─────────────────────

@admin.register(OrderMessage)
class OrderMessageAdmin(admin.ModelAdmin):
    list_display    = ['order', 'sender', 'is_read', 'created_at', '_preview']
    list_filter     = ['is_read', 'created_at']
    search_fields   = ['order__order_number', 'sender__email', 'message']
    readonly_fields = ['created_at', 'is_read']
    inlines         = [OrderMessageAttachmentInline]

    @admin.display(description='پیام')
    def _preview(self, obj):
        return obj.message[:80] + ('…' if len(obj.message) > 80 else '')
