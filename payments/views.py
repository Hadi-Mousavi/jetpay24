from django.contrib import messages as flash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django_ratelimit.decorators import ratelimit

from orders.models import Order

from .forms import PaymentSubmitForm
from .models import Payment


@ratelimit(key='user', rate='10/h', method='POST', block=True, group='file_uploads')
@login_required
def payment_submit(request, order_pk):
    """
    Accept a payment receipt upload for an order that is in waiting_payment state.

    Rules:
      - Order must belong to request.user.
      - Order status must be waiting_payment.
      - Submission is blocked if a 'submitted' (pending review) payment already exists.
      - Customer may resubmit after a rejected payment.
    """
    order = get_object_or_404(Order, pk=order_pk, user=request.user)

    if order.status != Order.STATUS_WAITING_PAYMENT:
        return HttpResponseForbidden(
            'این سفارش در انتظار پرداخت نیست.'
        )

    # Block resubmission while a payment is under review
    if order.payments.filter(status=Payment.STATUS_SUBMITTED).exists():
        flash.warning(
            request,
            'رسید پرداخت شما در حال بررسی است. لطفاً منتظر نتیجه باشید.',
        )
        return redirect('order_detail', pk=order_pk)

    if request.method == 'POST':
        form = PaymentSubmitForm(request.POST, request.FILES)
        if form.is_valid():
            payment              = form.save(commit=False)
            payment.order        = order
            payment.amount       = order.amount
            payment.currency     = order.currency
            payment.status       = Payment.STATUS_SUBMITTED
            payment.save()
            flash.success(
                request,
                'رسید پرداخت شما با موفقیت ارسال شد و در انتظار بررسی است.',
            )
        else:
            for field_errors in form.errors.values():
                for err in field_errors:
                    flash.error(request, err)

    return redirect('order_detail', pk=order_pk)


@login_required
def payment_receipt_download(request, pk):
    """
    Serve a payment receipt file securely.
    Staff can download any receipt; customers only their own.
    """
    if request.user.is_staff:
        payment = get_object_or_404(
            Payment.objects.select_related('order'), pk=pk
        )
    else:
        payment = get_object_or_404(
            Payment.objects.select_related('order'),
            pk=pk,
            order__user=request.user,
        )

    if not payment.receipt_file:
        raise Http404

    try:
        return FileResponse(
            payment.receipt_file.open('rb'),
            as_attachment=True,
            filename=payment.filename,
        )
    except (FileNotFoundError, OSError):
        raise Http404
