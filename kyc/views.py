from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render

from .forms import KYCSubmitForm
from .models import KYCProfile, KYCSiteSettings


@login_required
def kyc_submit(request):
    profile, _ = KYCProfile.objects.get_or_create(user=request.user)
    kyc_settings = KYCSiteSettings.get()

    # ── Server-side lock: pending/approved profiles cannot be modified ──────
    if profile.is_locked and request.method == 'POST':
        return HttpResponseForbidden(
            'احراز هویت شما در حال بررسی یا تأیید شده است و امکان ویرایش وجود ندارد.'
        )

    # ── Read-only view for locked profiles ──────────────────────────────────
    if profile.is_locked:
        return render(request, 'kyc/kyc_submit.html', {
            'kyc_profile': profile,
            'kyc_settings': kyc_settings,
            'is_locked': True,
        })

    # ── Editable form for not_submitted / rejected profiles ─────────────────
    if request.method == 'POST':
        form = KYCSubmitForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            kyc = form.save(commit=False)
            kyc.status = KYCProfile.STATUS_PENDING
            kyc.save()
            messages.success(
                request,
                'اطلاعات احراز هویت شما با موفقیت ثبت شد و در انتظار بررسی است.',
            )
            return redirect('kyc_submit')
    else:
        form = KYCSubmitForm(instance=profile)

    return render(request, 'kyc/kyc_submit.html', {
        'form': form,
        'kyc_profile': profile,
        'kyc_settings': kyc_settings,
        'is_locked': False,
    })
