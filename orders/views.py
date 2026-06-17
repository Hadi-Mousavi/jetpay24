from django.contrib import messages as flash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from kyc.models import KYCProfile

from .forms import AttachmentForm, MessageForm, OrderCreateForm
from .models import (
    Order, OrderAttachment, OrderMessage,
    OrderMessageAttachment, SubCategory,
)
from .utils import validate_upload


# ── helpers ──────────────────────────────────────────────────────────────────

def _kyc_profile(user):
    try:
        return user.kyc_profile
    except KYCProfile.DoesNotExist:
        return None


# ── customer views ────────────────────────────────────────────────────────────

@login_required
def order_list(request):
    orders      = (
        Order.objects
        .filter(user=request.user)
        .select_related('category', 'subcategory')
    )
    kyc         = _kyc_profile(request.user)
    kyc_approved = kyc and kyc.status == KYCProfile.STATUS_APPROVED

    return render(request, 'orders/order_list.html', {
        'orders':       orders,
        'kyc_profile':  kyc,
        'kyc_approved': kyc_approved,
    })


@login_required
def order_create(request):
    kyc          = _kyc_profile(request.user)
    kyc_approved = kyc and kyc.status == KYCProfile.STATUS_APPROVED

    if not kyc_approved:
        return render(request, 'orders/order_create.html', {
            'kyc_blocked': True,
            'kyc_profile': kyc,
        })

    if request.method == 'POST':
        form = OrderCreateForm(request.POST)
        if form.is_valid():
            # Validate every attachment file before committing the order row.
            files  = request.FILES.getlist('attachment_files')
            titles = request.POST.getlist('attachment_titles')
            file_errors = []
            for f in files:
                try:
                    validate_upload(f)
                except ValidationError as e:
                    file_errors.append(f'{f.name}: {e.message}')

            if file_errors:
                for err in file_errors:
                    flash.error(request, err)
            else:
                order      = form.save(commit=False)
                order.user = request.user
                order.save()

                for idx, f in enumerate(files):
                    title = titles[idx] if idx < len(titles) else ''
                    OrderAttachment.objects.create(
                        order=order, file=f,
                        title=title, uploaded_by=request.user,
                    )

                flash.success(
                    request,
                    f'سفارش شما با شماره {order.order_number} با موفقیت ثبت شد.',
                )
                return redirect('order_detail', pk=order.pk)
    else:
        form = OrderCreateForm()

    return render(request, 'orders/order_create.html', {
        'form':        form,
        'kyc_blocked': False,
    })


@login_required
def order_detail(request, pk):
    order       = get_object_or_404(Order, pk=pk, user=request.user)
    order_msgs  = order.messages.select_related('sender').prefetch_related('attachments')
    attachments = order.attachments.select_related('uploaded_by')
    msg_form    = MessageForm()
    attach_form = AttachmentForm()

    return render(request, 'orders/order_detail.html', {
        'order':        order,
        'order_msgs':   order_msgs,
        'attachments':  attachments,
        'msg_form':     msg_form,
        'attach_form':  attach_form,
    })


@login_required
def order_send_message(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)

    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            msg_files = request.FILES.getlist('message_files')

            # Validate attachments before saving anything.
            file_errors = []
            for f in msg_files:
                try:
                    validate_upload(f)
                except ValidationError as e:
                    file_errors.append(f'{f.name}: {e.message}')

            if file_errors:
                for err in file_errors:
                    flash.error(request, err)
            else:
                msg        = form.save(commit=False)
                msg.order  = order
                msg.sender = request.user
                msg.save()
                for f in msg_files:
                    OrderMessageAttachment.objects.create(message=msg, file=f)

    return redirect('order_detail', pk=pk)


@login_required
def order_upload_attachment(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)

    if request.method == 'POST':
        form = AttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            att             = form.save(commit=False)
            att.order       = order
            att.uploaded_by = request.user
            att.save()

    return redirect('order_detail', pk=pk)


# ── AJAX ──────────────────────────────────────────────────────────────────────

def ajax_subcategories(request):
    """Return JSON list of active subcategories for a given category."""
    try:
        cat_id = int(request.GET.get('category_id', ''))
    except (ValueError, TypeError):
        return JsonResponse({'subcategories': []})

    subs = (
        SubCategory.objects
        .filter(category_id=cat_id, is_active=True)
        .order_by('display_order', 'title')
        .values('id', 'title')
    )
    return JsonResponse({'subcategories': list(subs)})


# ── public tracking page (kept for backward compatibility) ────────────────────

def order_tracking(request):
    order = None
    error = None
    query = request.GET.get('code', '').strip().upper()

    if query:
        try:
            order = Order.objects.select_related(
                'category', 'subcategory',
            ).get(order_number=query)
        except Order.DoesNotExist:
            error = 'شماره سفارش یافت نشد. لطفاً دوباره بررسی کنید.'

    return render(request, 'orders/order_tracking.html', {
        'order': order,
        'error': error,
        'query': query,
    })


# ── legacy stubs (old URLs still wired in config/urls.py) ─────────────────────

def order_success(request, tracking_code=None):
    return redirect('order_list')


# ── secure file download views ────────────────────────────────────────────────

@login_required
def order_attachment_download(request, pk):
    """
    Serve an OrderAttachment file.
    Access rules:
      - Staff: unrestricted.
      - Customer: must own the order the attachment belongs to.
    Returns 404 if the attachment row or file on disk does not exist.
    Returns 403 if access is denied.
    """
    att = get_object_or_404(OrderAttachment, pk=pk)

    if not request.user.is_staff and att.order.user != request.user:
        raise PermissionDenied

    if not att.file:
        raise Http404

    try:
        return FileResponse(
            att.file.open('rb'),
            as_attachment=True,
            filename=att.filename,
        )
    except (FileNotFoundError, OSError):
        raise Http404


@login_required
def message_attachment_download(request, pk):
    """
    Serve an OrderMessageAttachment file.
    Access rules:
      - Staff: unrestricted.
      - Customer: must own the order the message belongs to.
    Returns 404 if the attachment row or file on disk does not exist.
    Returns 403 if access is denied.
    """
    att = get_object_or_404(
        OrderMessageAttachment.objects.select_related('message__order'),
        pk=pk,
    )

    if not request.user.is_staff and att.message.order.user != request.user:
        raise PermissionDenied

    if not att.file:
        raise Http404

    try:
        return FileResponse(
            att.file.open('rb'),
            as_attachment=True,
            filename=att.filename,
        )
    except (FileNotFoundError, OSError):
        raise Http404
