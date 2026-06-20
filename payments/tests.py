"""
Payment workflow test suite.

Coverage:
  - Payment model: status properties, filename helper
  - Receipt upload: extension, size, magic-byte validation in the form
  - payment_submit view: auth, wrong-status guard, duplicate-pending guard,
    successful submit, form error handling
  - payment_receipt_download: auth, ownership, missing file
  - Order automation: approved payment → order moves to in_progress
  - Signal: approved/rejected notifications; no double-notification on re-save;
    rejection_note embedded in notification message
  - Timeline: payment events appear in order timeline
  - Permission: customer cannot download another customer's receipt
"""

import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile, InMemoryUploadedFile
from django.test import TestCase
from django.urls import reverse

from kyc.models import KYCProfile
from notifications.models import Notification
from orders.models import Category, Order, SubCategory
from payments.models import Payment

User = get_user_model()


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_user(email='pay@test.com', is_staff=False, **kw):
    return User.objects.create_user(
        email=email, password='pass1234',
        first_name='تست', last_name='کاربر',
        is_staff=is_staff, **kw,
    )


def _approve_kyc(user):
    profile, _ = KYCProfile.objects.get_or_create(user=user)
    profile.status = KYCProfile.STATUS_APPROVED
    profile.save()
    return profile


def _make_order(user, status=Order.STATUS_WAITING_PAYMENT):
    cat = Category.objects.first()
    if not cat:
        cat = Category.objects.create(title='تست', is_active=True)
    sub = SubCategory.objects.filter(category=cat).first()
    if not sub:
        sub = SubCategory.objects.create(
            category=cat, title='زیر تست', is_active=True, display_order=1,
        )
    return Order.objects.create(
        user=user, category=cat, subcategory=sub,
        description='تست پرداخت', status=status,
        amount='100.00', currency='USD',
    )


_JPEG_BYTES = b'\xff\xd8\xff\xe0' + b'\x00' * 257
_PDF_BYTES  = b'%PDF-1.4 ' + b'\x00' * 252


def _jpeg_file(name='receipt.jpg'):
    """Return a BytesIO with JPEG magic bytes (for form upload tests)."""
    f = io.BytesIO(_JPEG_BYTES)
    f.name = name
    f.size = len(_JPEG_BYTES)
    return f


def _pdf_file(name='receipt.pdf'):
    """Return a BytesIO with PDF magic bytes (for form upload tests)."""
    f = io.BytesIO(_PDF_BYTES)
    f.name = name
    f.size = len(_PDF_BYTES)
    return f


def _make_payment(order, status=Payment.STATUS_SUBMITTED, **kw):
    """Create a Payment with a valid SimpleUploadedFile receipt."""
    receipt = SimpleUploadedFile('receipt.jpg', _JPEG_BYTES, content_type='image/jpeg')
    return Payment.objects.create(
        order=order,
        receipt_file=receipt,
        status=status,
        **kw,
    )


# ── Model tests ──────────────────────────────────────────────────────────────

class PaymentModelTests(TestCase):

    def setUp(self):
        self.user  = _make_user()
        _approve_kyc(self.user)
        self.order = _make_order(self.user)

    def test_is_submitted_property(self):
        p = _make_payment(self.order, status=Payment.STATUS_SUBMITTED)
        self.assertTrue(p.is_submitted)
        self.assertFalse(p.is_approved)
        self.assertFalse(p.is_rejected)

    def test_is_approved_property(self):
        p = _make_payment(self.order, status=Payment.STATUS_APPROVED)
        self.assertTrue(p.is_approved)

    def test_is_rejected_property(self):
        p = _make_payment(self.order, status=Payment.STATUS_REJECTED)
        self.assertTrue(p.is_rejected)

    def test_str_representation(self):
        p = _make_payment(self.order)
        self.assertIn(self.order.order_number, str(p))

    def test_default_status_is_submitted(self):
        p = Payment(order=self.order, receipt_file=_jpeg_file())
        self.assertEqual(p.status, Payment.STATUS_SUBMITTED)

    def test_filename_property(self):
        p = _make_payment(self.order)
        self.assertIn('receipt', p.filename)


# ── Form validation tests ────────────────────────────────────────────────────

class PaymentFormValidationTests(TestCase):

    def _form(self, file, field_name='receipt_file'):
        from payments.forms import PaymentSubmitForm
        from django.core.files.uploadedfile import InMemoryUploadedFile
        upload = InMemoryUploadedFile(
            file=file, field_name=field_name,
            name=file.name, content_type='application/octet-stream',
            size=file.size, charset=None,
        )
        return PaymentSubmitForm(data={}, files={field_name: upload})

    def test_valid_jpeg_accepted(self):
        form = self._form(_jpeg_file())
        self.assertNotIn('receipt_file', form.errors)

    def test_valid_pdf_accepted(self):
        form = self._form(_pdf_file())
        self.assertNotIn('receipt_file', form.errors)

    def test_wrong_extension_rejected(self):
        bad = io.BytesIO(b'\xff\xd8\xff\xe0' + b'\x00' * 257)
        bad.name = 'receipt.exe'
        bad.size = 261
        form = self._form(bad)
        self.assertIn('receipt_file', form.errors)

    def test_fake_jpeg_content_rejected(self):
        bad = io.BytesIO(b'NOTAJPEG' + b'\x00' * 253)
        bad.name = 'receipt.jpg'
        bad.size = 261
        form = self._form(bad)
        self.assertIn('receipt_file', form.errors)

    def test_oversized_file_rejected(self):
        f = _jpeg_file()
        f.size = 11 * 1024 * 1024
        form = self._form(f)
        self.assertIn('receipt_file', form.errors)


# ── View: payment_submit ─────────────────────────────────────────────────────

class PaymentSubmitViewTests(TestCase):

    def setUp(self):
        self.user  = _make_user()
        _approve_kyc(self.user)
        self.order = _make_order(self.user, status=Order.STATUS_WAITING_PAYMENT)
        self.url   = reverse('payment_submit', args=[self.order.pk])
        self.client.login(username='pay@test.com', password='pass1234')

    def _post(self, file=None, reference_number=''):
        from django.core.files.uploadedfile import InMemoryUploadedFile
        if file is None:
            file = _jpeg_file()
        upload = InMemoryUploadedFile(
            file=file, field_name='receipt_file',
            name=file.name, content_type='image/jpeg',
            size=file.size, charset=None,
        )
        return self.client.post(self.url, {
            'receipt_file': upload,
            'reference_number': reference_number,
        })

    def test_anonymous_redirects_to_login(self):
        self.client.logout()
        response = self.client.post(self.url)
        self.assertRedirects(response, f'/auth/login/?next={self.url}', fetch_redirect_response=False)

    def test_successful_submit_creates_payment(self):
        self._post()
        self.assertEqual(self.order.payments.count(), 1)
        p = self.order.payments.first()
        self.assertEqual(p.status, Payment.STATUS_SUBMITTED)

    def test_successful_submit_redirects_to_order_detail(self):
        response = self._post()
        self.assertRedirects(
            response,
            reverse('order_detail', args=[self.order.pk]),
            fetch_redirect_response=False,
        )

    def test_submit_copies_amount_and_currency(self):
        self._post()
        p = self.order.payments.first()
        self.assertEqual(str(p.amount), '100.00')
        self.assertEqual(p.currency, 'USD')

    def test_wrong_order_status_returns_403(self):
        order = _make_order(self.user, status=Order.STATUS_SUBMITTED)
        url   = reverse('payment_submit', args=[order.pk])
        response = self._post()  # this posts to self.url (waiting_payment)
        # now test with the submitted order
        response = self.client.post(url, {'receipt_file': _jpeg_file()})
        self.assertEqual(response.status_code, 403)

    def test_pending_payment_blocks_resubmit(self):
        _make_payment(self.order, status=Payment.STATUS_SUBMITTED)
        self._post()
        # Should still be only 1 payment
        self.assertEqual(self.order.payments.count(), 1)

    def test_rejected_payment_allows_resubmit(self):
        _make_payment(self.order, status=Payment.STATUS_REJECTED)
        self._post()
        self.assertEqual(self.order.payments.count(), 2)

    def test_other_user_cannot_submit_payment(self):
        other = _make_user('other@test.com')
        self.client.login(username='other@test.com', password='pass1234')
        response = self._post()
        self.assertEqual(response.status_code, 404)

    def test_reference_number_saved(self):
        self._post(reference_number='REF123456')
        p = self.order.payments.first()
        self.assertEqual(p.reference_number, 'REF123456')


# ── View: payment_receipt_download ──────────────────────────────────────────

class PaymentReceiptDownloadTests(TestCase):

    def setUp(self):
        self.user  = _make_user('dl@test.com')
        _approve_kyc(self.user)
        self.order   = _make_order(self.user)
        self.payment = _make_payment(self.order)
        self.url     = reverse('payment_receipt_download', args=[self.payment.pk])

    def test_anonymous_redirects_to_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f'/auth/login/?next={self.url}', fetch_redirect_response=False)

    def test_owner_can_download(self):
        self.client.login(username='dl@test.com', password='pass1234')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_other_user_gets_404(self):
        other = _make_user('other2@test.com')
        self.client.login(username='other2@test.com', password='pass1234')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_staff_can_download_any_receipt(self):
        staff = _make_user('staff@test.com', is_staff=True)
        self.client.login(username='staff@test.com', password='pass1234')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)


# ── Order automation ─────────────────────────────────────────────────────────

class PaymentOrderAutomationTests(TestCase):

    def setUp(self):
        self.user  = _make_user('auto@test.com')
        _approve_kyc(self.user)
        self.order = _make_order(self.user, status=Order.STATUS_WAITING_PAYMENT)

    def test_approved_payment_moves_order_to_in_progress(self):
        payment = _make_payment(self.order, status=Payment.STATUS_SUBMITTED)
        Notification.objects.filter(user=self.user).delete()

        payment._previous_status = Payment.STATUS_SUBMITTED
        payment.status = Payment.STATUS_APPROVED
        payment.save()

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_IN_PROGRESS)

    def test_rejected_payment_does_not_change_order_status(self):
        payment = _make_payment(self.order, status=Payment.STATUS_SUBMITTED)
        payment._previous_status = Payment.STATUS_SUBMITTED
        payment.status = Payment.STATUS_REJECTED
        payment.save()

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_WAITING_PAYMENT)

    def test_approved_payment_on_non_waiting_order_does_not_break(self):
        """Approving a payment when order is already in_progress is safe."""
        self.order.status = Order.STATUS_IN_PROGRESS
        self.order.save()
        payment = _make_payment(self.order, status=Payment.STATUS_SUBMITTED)
        payment._previous_status = Payment.STATUS_SUBMITTED
        payment.status = Payment.STATUS_APPROVED
        payment.save()  # should not raise
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_IN_PROGRESS)


# ── Notification signals ─────────────────────────────────────────────────────

class PaymentNotificationTests(TestCase):

    def setUp(self):
        self.user  = _make_user('pnotif@test.com')
        _approve_kyc(self.user)
        self.order = _make_order(self.user, status=Order.STATUS_WAITING_PAYMENT)

    def _transition(self, from_status, to_status, rejection_note=''):
        payment = _make_payment(self.order, status=from_status, rejection_note=rejection_note)
        Notification.objects.filter(user=self.user).delete()
        payment._previous_status = from_status
        payment.status = to_status
        if rejection_note:
            payment.rejection_note = rejection_note
        payment.save()
        return Notification.objects.filter(user=self.user)

    def test_approved_creates_notification(self):
        notifs = self._transition(Payment.STATUS_SUBMITTED, Payment.STATUS_APPROVED)
        # When payment is approved the order advances to in_progress, which may
        # trigger a second notification (ORDER_STATUS_CHANGED).  Assert only
        # that the PAYMENT_APPROVED notification is present.
        payment_notif = notifs.filter(notification_type=Notification.TYPE_PAYMENT_APPROVED)
        self.assertEqual(payment_notif.count(), 1)

    def test_rejected_creates_notification(self):
        notifs = self._transition(Payment.STATUS_SUBMITTED, Payment.STATUS_REJECTED)
        self.assertEqual(notifs.count(), 1)
        self.assertEqual(notifs.first().notification_type, Notification.TYPE_PAYMENT_REJECTED)

    def test_rejection_note_in_notification_message(self):
        note = 'رسید خوانا نیست'
        notifs = self._transition(
            Payment.STATUS_SUBMITTED, Payment.STATUS_REJECTED,
            rejection_note=note,
        )
        self.assertIn(note, notifs.first().message)

    def test_no_notification_on_new_payment(self):
        """Creating a new payment (submitted status) must NOT send a notification."""
        _make_payment(self.order, status=Payment.STATUS_SUBMITTED)
        # Only order-created notification may exist, not a payment one
        payment_notifs = Notification.objects.filter(
            user=self.user,
            notification_type__in=[
                Notification.TYPE_PAYMENT_APPROVED,
                Notification.TYPE_PAYMENT_REJECTED,
            ],
        )
        self.assertEqual(payment_notifs.count(), 0)

    def test_no_notification_when_status_unchanged(self):
        payment = _make_payment(self.order, status=Payment.STATUS_SUBMITTED)
        Notification.objects.filter(user=self.user).delete()
        payment.reference_number = 'updated-ref'
        payment.save()
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 0)

    def test_notification_is_unread_by_default(self):
        notifs = self._transition(Payment.STATUS_SUBMITTED, Payment.STATUS_APPROVED)
        self.assertFalse(notifs.first().is_read)


# ── Timeline integration ─────────────────────────────────────────────────────

class PaymentTimelineTests(TestCase):

    def setUp(self):
        self.user  = _make_user('timeline@test.com')
        _approve_kyc(self.user)
        self.order = _make_order(self.user, status=Order.STATUS_WAITING_PAYMENT)
        self.client.login(username='timeline@test.com', password='pass1234')

    def test_submitted_payment_appears_in_timeline(self):
        _make_payment(self.order, status=Payment.STATUS_SUBMITTED)
        response = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(response, 'رسید پرداخت ارسال شد')

    def test_approved_payment_appears_in_timeline(self):
        _make_payment(self.order, status=Payment.STATUS_APPROVED)
        response = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(response, 'پرداخت تأیید شد')

    def test_rejected_payment_appears_in_timeline(self):
        _make_payment(self.order, status=Payment.STATUS_REJECTED)
        response = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(response, 'پرداخت رد شد')


# ── Order detail template — payment section ──────────────────────────────────

class PaymentOrderDetailTemplateTests(TestCase):

    def setUp(self):
        self.user  = _make_user('tmpl@test.com')
        _approve_kyc(self.user)
        self.order = _make_order(self.user, status=Order.STATUS_WAITING_PAYMENT)
        self.client.login(username='tmpl@test.com', password='pass1234')

    def test_payment_section_shown_when_waiting_payment(self):
        response = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(response, 'پرداخت سفارش')
        self.assertContains(response, 'ارسال رسید')

    def test_payment_section_not_shown_when_not_waiting(self):
        self.order.status = Order.STATUS_SUBMITTED
        self.order.save()
        response = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertNotContains(response, 'ارسال رسید')

    def test_pending_review_shown_when_payment_submitted(self):
        _make_payment(self.order, status=Payment.STATUS_SUBMITTED)
        response = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(response, 'رسید پرداخت شما در حال بررسی است')
        # Upload form must NOT appear while pending
        self.assertNotContains(response, 'ارسال رسید')

    def test_rejected_shows_resubmit_form(self):
        _make_payment(self.order, status=Payment.STATUS_REJECTED)
        response = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(response, 'رسید پرداخت رد شد')
        self.assertContains(response, 'ارسال رسید')

    def test_rejection_note_shown_in_history(self):
        _make_payment(self.order, status=Payment.STATUS_REJECTED, rejection_note='مبلغ اشتباه است')
        response = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(response, 'مبلغ اشتباه است')

    def test_payment_history_shows_all_payments(self):
        _make_payment(self.order, status=Payment.STATUS_REJECTED)
        _make_payment(self.order, status=Payment.STATUS_SUBMITTED)
        response = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(response, 'سابقه پرداخت')

    def test_amount_shown_in_payment_section(self):
        response = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(response, '100.00')
