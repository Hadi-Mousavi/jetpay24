"""
KYC Phase 2 test suite.

Coverage:
  - card_last4 validation (English / Persian digits, length, empty OK)
  - bank_card_image magic-byte validation (validate_kyc_image)
  - needs_correction status: is_locked=False, is_needs_correction=True
  - Edit locking: pending and approved are locked, others editable
  - is_locked property for all statuses
  - Notification creation: approved, rejected, needs_correction
  - needs_correction notification carries admin_note content
  - admin_note visibility in KYC page and dashboard
  - Status transitions: re-submission sets status back to pending
  - KYC page renders banking fields and their current values
"""

import io

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from kyc.forms import KYCSubmitForm
from kyc.models import KYCProfile
from kyc.utils import validate_kyc_image
from notifications.models import Notification

User = get_user_model()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_user(email='kyc@test.com', **kwargs):
    return User.objects.create_user(
        email=email, password='pass1234',
        first_name='تست', last_name='کاربر', **kwargs,
    )


def _make_profile(user, **kwargs):
    profile, _ = KYCProfile.objects.get_or_create(user=user)
    for k, v in kwargs.items():
        setattr(profile, k, v)
    profile.save()
    return profile


def _jpeg_header():
    """Minimal valid JPEG header bytes (SOI marker + enough filler)."""
    return b'\xff\xd8\xff\xe0' + b'\x00' * 257


def _png_header():
    """Minimal valid PNG header bytes."""
    return b'\x89PNG\r\n\x1a\n' + b'\x00' * 253


def _fake_upload(name, content):
    """Return an in-memory file-like object for form/validator tests."""
    f = io.BytesIO(content)
    f.name = name
    f.size = len(content)
    return f


# ── card_last4 validation ──────────────────────────────────────────────────────

class CardLast4ValidationTests(TestCase):

    def setUp(self):
        self.user = _make_user('last4@test.com')
        _make_profile(
            self.user,
            national_id='1234567890',
            status=KYCProfile.STATUS_NOT_SUBMITTED,
        )
        self.client.login(username='last4@test.com', password='pass1234')

    def _post(self, card_last4):
        return self.client.post(reverse('kyc_submit'), {
            'national_id': '1234567890',
            'date_of_birth': '۱۳۷۰/۰۱/۰۱',
            'card_last4': card_last4,
        })

    def test_valid_english_digits(self):
        form = KYCSubmitForm({'card_last4': '1234',
                              'national_id': '1234567890',
                              'date_of_birth': '1370/01/01'})
        form.is_valid()
        self.assertEqual(form.cleaned_data.get('card_last4'), '1234')

    def test_valid_persian_digits(self):
        form = KYCSubmitForm({'card_last4': '۱۲۳۴',
                              'national_id': '1234567890',
                              'date_of_birth': '1370/01/01'})
        form.is_valid()
        # Normalized to English digits
        self.assertEqual(form.cleaned_data.get('card_last4'), '1234')

    def test_too_short_rejected(self):
        form = KYCSubmitForm({'card_last4': '12',
                              'national_id': '1234567890',
                              'date_of_birth': '1370/01/01'})
        form.is_valid()
        self.assertIn('card_last4', form.errors)

    def test_too_long_rejected(self):
        form = KYCSubmitForm({'card_last4': '12345',
                              'national_id': '1234567890',
                              'date_of_birth': '1370/01/01'})
        form.is_valid()
        self.assertIn('card_last4', form.errors)

    def test_non_digits_rejected(self):
        form = KYCSubmitForm({'card_last4': 'abcd',
                              'national_id': '1234567890',
                              'date_of_birth': '1370/01/01'})
        form.is_valid()
        self.assertIn('card_last4', form.errors)

    def test_empty_is_valid(self):
        """card_last4 is optional; empty string should pass."""
        form = KYCSubmitForm({'card_last4': '',
                              'national_id': '1234567890',
                              'date_of_birth': '1370/01/01'})
        form.is_valid()
        self.assertNotIn('card_last4', form.errors)

    def test_mixed_persian_english_rejected_if_wrong_length(self):
        form = KYCSubmitForm({'card_last4': '۱2',
                              'national_id': '1234567890',
                              'date_of_birth': '1370/01/01'})
        form.is_valid()
        self.assertIn('card_last4', form.errors)


# ── bank_card_image magic-byte validation ──────────────────────────────────────

class BankCardImageValidationTests(TestCase):

    def test_valid_jpeg_passes(self):
        f = _fake_upload('card.jpg', _jpeg_header())
        try:
            validate_kyc_image(f)
        except Exception as exc:
            self.fail(f'validate_kyc_image raised unexpectedly: {exc}')

    def test_valid_png_passes(self):
        f = _fake_upload('card.png', _png_header())
        try:
            validate_kyc_image(f)
        except Exception as exc:
            self.fail(f'validate_kyc_image raised unexpectedly: {exc}')

    def test_wrong_extension_rejected(self):
        from django.core.exceptions import ValidationError
        f = _fake_upload('card.pdf', _jpeg_header())
        with self.assertRaises(ValidationError):
            validate_kyc_image(f)

    def test_fake_jpeg_magic_rejected(self):
        """A file named .jpg but with arbitrary content must be rejected."""
        from django.core.exceptions import ValidationError
        f = _fake_upload('card.jpg', b'NOTAREAL' + b'\x00' * 253)
        with self.assertRaises(ValidationError):
            validate_kyc_image(f)

    def test_oversized_file_rejected(self):
        from django.core.exceptions import ValidationError
        content = _jpeg_header()
        f = _fake_upload('card.jpg', content)
        f.size = 11 * 1024 * 1024  # fake size > 10 MB
        with self.assertRaises(ValidationError):
            validate_kyc_image(f)

    def test_none_passes_silently(self):
        """validate_kyc_image(None) must be a no-op."""
        try:
            validate_kyc_image(None)
        except Exception as exc:
            self.fail(f'validate_kyc_image(None) raised: {exc}')

    def test_file_pointer_reset_after_validation(self):
        """validate_kyc_image must reset file pointer to 0 after magic read."""
        f = _fake_upload('card.jpg', _jpeg_header())
        validate_kyc_image(f)
        self.assertEqual(f.tell(), 0)


# ── Status property helpers ────────────────────────────────────────────────────

class KYCStatusPropertiesTests(TestCase):

    def setUp(self):
        self.user = _make_user('props@test.com')

    def _profile(self, status):
        return _make_profile(self.user, status=status)

    def test_is_needs_correction_true(self):
        p = self._profile(KYCProfile.STATUS_NEEDS_CORRECTION)
        self.assertTrue(p.is_needs_correction)

    def test_is_needs_correction_false_for_others(self):
        for s in (KYCProfile.STATUS_NOT_SUBMITTED,
                  KYCProfile.STATUS_PENDING,
                  KYCProfile.STATUS_APPROVED,
                  KYCProfile.STATUS_REJECTED):
            p = self._profile(s)
            self.assertFalse(p.is_needs_correction, msg=f'failed for status={s}')

    def test_is_locked_pending(self):
        p = self._profile(KYCProfile.STATUS_PENDING)
        self.assertTrue(p.is_locked)

    def test_is_locked_approved(self):
        p = self._profile(KYCProfile.STATUS_APPROVED)
        self.assertTrue(p.is_locked)

    def test_not_locked_rejected(self):
        p = self._profile(KYCProfile.STATUS_REJECTED)
        self.assertFalse(p.is_locked)

    def test_not_locked_needs_correction(self):
        p = self._profile(KYCProfile.STATUS_NEEDS_CORRECTION)
        self.assertFalse(p.is_locked)

    def test_not_locked_not_submitted(self):
        p = self._profile(KYCProfile.STATUS_NOT_SUBMITTED)
        self.assertFalse(p.is_locked)


# ── Edit locking: view-level enforcement ──────────────────────────────────────

class KYCEditLockTests(TestCase):

    def setUp(self):
        self.user = _make_user('lock@test.com')
        self.client.login(username='lock@test.com', password='pass1234')

    def _post_kyc(self):
        return self.client.post(reverse('kyc_submit'), {
            'national_id': '1234567890',
            'date_of_birth': '1370/01/01',
        })

    def test_pending_profile_blocks_post(self):
        _make_profile(self.user, status=KYCProfile.STATUS_PENDING)
        response = self._post_kyc()
        self.assertEqual(response.status_code, 403)

    def test_approved_profile_blocks_post(self):
        _make_profile(self.user, status=KYCProfile.STATUS_APPROVED)
        response = self._post_kyc()
        self.assertEqual(response.status_code, 403)

    def test_needs_correction_allows_post(self):
        _make_profile(
            self.user,
            national_id='1234567890',
            status=KYCProfile.STATUS_NEEDS_CORRECTION,
        )
        response = self._post_kyc()
        # Should redirect (200 after following), not 403
        self.assertNotEqual(response.status_code, 403)

    def test_rejected_allows_resubmit(self):
        _make_profile(
            self.user,
            national_id='1234567890',
            status=KYCProfile.STATUS_REJECTED,
        )
        response = self._post_kyc()
        self.assertNotEqual(response.status_code, 403)

    def test_pending_GET_shows_readonly_view(self):
        _make_profile(self.user, status=KYCProfile.STATUS_PENDING)
        response = self.client.get(reverse('kyc_submit'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_locked'])

    def test_approved_GET_shows_readonly_view(self):
        _make_profile(self.user, status=KYCProfile.STATUS_APPROVED)
        response = self.client.get(reverse('kyc_submit'))
        self.assertTrue(response.context['is_locked'])

    def test_needs_correction_GET_shows_editable_form(self):
        _make_profile(self.user, status=KYCProfile.STATUS_NEEDS_CORRECTION)
        response = self.client.get(reverse('kyc_submit'))
        self.assertFalse(response.context['is_locked'])
        self.assertIn('form', response.context)


# ── Status transitions ─────────────────────────────────────────────────────────

class KYCStatusTransitionTests(TestCase):

    def setUp(self):
        self.user = _make_user('trans@test.com')
        self.client.login(username='trans@test.com', password='pass1234')

    def test_resubmit_from_needs_correction_sets_pending(self):
        _make_profile(
            self.user,
            national_id='1234567890',
            status=KYCProfile.STATUS_NEEDS_CORRECTION,
        )
        self.client.post(reverse('kyc_submit'), {
            'national_id': '1234567890',
            'date_of_birth': '1370/01/01',
        })
        self.user.kyc_profile.refresh_from_db()
        self.assertEqual(self.user.kyc_profile.status, KYCProfile.STATUS_PENDING)

    def test_resubmit_from_rejected_sets_pending(self):
        _make_profile(
            self.user,
            national_id='1234567890',
            status=KYCProfile.STATUS_REJECTED,
        )
        self.client.post(reverse('kyc_submit'), {
            'national_id': '1234567890',
            'date_of_birth': '1370/01/01',
        })
        self.user.kyc_profile.refresh_from_db()
        self.assertEqual(self.user.kyc_profile.status, KYCProfile.STATUS_PENDING)


# ── Notification creation ──────────────────────────────────────────────────────

class KYCNotificationTests(TestCase):

    def setUp(self):
        self.user = _make_user('notif@test.com')

    def _transition(self, from_status, to_status, admin_note=''):
        profile = _make_profile(self.user, status=from_status, admin_note=admin_note)
        # Clear any notifications created by initial save
        Notification.objects.filter(user=self.user).delete()
        profile.status = to_status
        if admin_note:
            profile.admin_note = admin_note
        profile.save()
        return Notification.objects.filter(user=self.user)

    def test_approved_creates_notification(self):
        notifs = self._transition(KYCProfile.STATUS_PENDING, KYCProfile.STATUS_APPROVED)
        self.assertEqual(notifs.count(), 1)
        self.assertEqual(notifs.first().notification_type, Notification.TYPE_KYC_APPROVED)

    def test_rejected_creates_notification(self):
        notifs = self._transition(KYCProfile.STATUS_PENDING, KYCProfile.STATUS_REJECTED)
        self.assertEqual(notifs.count(), 1)
        self.assertEqual(notifs.first().notification_type, Notification.TYPE_KYC_REJECTED)

    def test_needs_correction_creates_notification(self):
        notifs = self._transition(
            KYCProfile.STATUS_PENDING,
            KYCProfile.STATUS_NEEDS_CORRECTION,
        )
        self.assertEqual(notifs.count(), 1)
        self.assertEqual(notifs.first().notification_type, Notification.TYPE_KYC_NEEDS_CORRECTION)

    def test_needs_correction_notification_contains_admin_note(self):
        note = 'تصویر کارت ملی واضح نیست'
        notifs = self._transition(
            KYCProfile.STATUS_PENDING,
            KYCProfile.STATUS_NEEDS_CORRECTION,
            admin_note=note,
        )
        self.assertIn(note, notifs.first().message)

    def test_no_notification_when_status_unchanged(self):
        """Saving without a status change must not create a notification."""
        profile = _make_profile(self.user, status=KYCProfile.STATUS_PENDING)
        Notification.objects.filter(user=self.user).delete()
        # Save again without changing status
        profile.bank_name = 'ملت'
        profile.save()
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 0)

    def test_notification_is_unread_by_default(self):
        notifs = self._transition(KYCProfile.STATUS_PENDING, KYCProfile.STATUS_APPROVED)
        self.assertFalse(notifs.first().is_read)


# ── admin_note visibility ──────────────────────────────────────────────────────

class KYCAdminNoteVisibilityTests(TestCase):

    def setUp(self):
        self.user = _make_user('note@test.com')
        self.client.login(username='note@test.com', password='pass1234')

    def test_admin_note_shown_on_kyc_page_when_needs_correction(self):
        _make_profile(
            self.user,
            national_id='1234567890',
            status=KYCProfile.STATUS_NEEDS_CORRECTION,
            admin_note='لطفاً تصویر کارت ملی را بارگذاری کنید.',
        )
        response = self.client.get(reverse('kyc_submit'))
        self.assertContains(response, 'لطفاً تصویر کارت ملی را بارگذاری کنید.')

    def test_admin_note_shown_on_kyc_page_when_rejected(self):
        _make_profile(
            self.user,
            national_id='1234567890',
            status=KYCProfile.STATUS_REJECTED,
            admin_note='اطلاعات مطابقت ندارد.',
        )
        response = self.client.get(reverse('kyc_submit'))
        self.assertContains(response, 'اطلاعات مطابقت ندارد.')

    def test_admin_note_not_shown_when_pending(self):
        """Admin note must not be exposed when profile is pending (locked view)."""
        _make_profile(
            self.user,
            national_id='1234567890',
            status=KYCProfile.STATUS_PENDING,
            admin_note='این یادداشت نباید نمایش داده شود',
        )
        response = self.client.get(reverse('kyc_submit'))
        # The note in the DB should not be rendered while pending
        self.assertNotContains(response, 'این یادداشت نباید نمایش داده شود')

    def test_admin_note_shown_on_dashboard_when_needs_correction(self):
        _make_profile(
            self.user,
            national_id='1234567890',
            status=KYCProfile.STATUS_NEEDS_CORRECTION,
            admin_note='کارت ملی خوانا نیست.',
        )
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'کارت ملی خوانا نیست.')

    def test_admin_note_shown_on_dashboard_when_rejected(self):
        _make_profile(
            self.user,
            national_id='1234567890',
            status=KYCProfile.STATUS_REJECTED,
            admin_note='سلفی نادرست است.',
        )
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'سلفی نادرست است.')


# ── Dashboard KYC status card rendering ───────────────────────────────────────

class DashboardKYCStatusTests(TestCase):

    def setUp(self):
        self.user = _make_user('dash@test.com')
        self.client.login(username='dash@test.com', password='pass1234')

    def test_needs_correction_badge_on_dashboard(self):
        _make_profile(self.user, status=KYCProfile.STATUS_NEEDS_CORRECTION)
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'نیاز به اصلاح')

    def test_approved_badge_on_dashboard(self):
        _make_profile(self.user, status=KYCProfile.STATUS_APPROVED)
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'تأیید شده')

    def test_rejected_badge_on_dashboard(self):
        _make_profile(self.user, status=KYCProfile.STATUS_REJECTED)
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'رد شده')

    def test_pending_badge_on_dashboard(self):
        _make_profile(self.user, status=KYCProfile.STATUS_PENDING)
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'در انتظار بررسی')


# ── Banking fields render on KYC page ─────────────────────────────────────────

class KYCBankingFieldsTests(TestCase):

    def setUp(self):
        self.user = _make_user('bank@test.com')
        self.client.login(username='bank@test.com', password='pass1234')

    def test_banking_fields_present_in_editable_form(self):
        _make_profile(self.user, status=KYCProfile.STATUS_NOT_SUBMITTED)
        response = self.client.get(reverse('kyc_submit'))
        self.assertContains(response, 'نام صاحب کارت')
        self.assertContains(response, 'نام بانک')
        self.assertContains(response, 'چهار رقم آخر کارت')
        self.assertContains(response, 'تصویر کارت بانکی')

    def test_banking_fields_shown_in_locked_view(self):
        _make_profile(
            self.user,
            national_id='1234567890',
            status=KYCProfile.STATUS_APPROVED,
            card_holder_name='علی احمدی',
            bank_name='ملت',
            card_last4='5678',
        )
        response = self.client.get(reverse('kyc_submit'))
        self.assertContains(response, 'علی احمدی')
        self.assertContains(response, 'ملت')
        # card_last4 is displayed as Persian digits via |to_persian_digits
        self.assertContains(response, '۵۶۷۸')
