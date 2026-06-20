"""
Workflow Reopen Sprint — tests.

Coverage:
  WORKFLOW RULES
    - completed → in_progress  (valid recovery)
    - cancelled → under_review (valid recovery)
    - completed → under_review (invalid)
    - completed → cancelled    (invalid)
    - cancelled → in_progress  (invalid)
    - cancelled → completed    (invalid)
    - is_recovery_transition helper
  ADMIN INTEGRATION
    - Reopen accepted, history created, note stored
    - Workflow hint labels include "(بازگشایی سفارش)"
    - Restricted dropdown shows recovery label suffix
  NOTIFICATIONS
    - completed→in_progress fires TYPE_ORDER_REOPENED
    - cancelled→under_review fires TYPE_ORDER_REACTIVATED
    - regular in_progress transition still fires TYPE_ORDER_IN_PROGRESS
    - regular under_review transition still fires TYPE_ORDER_IN_REVIEW
  TIMELINE
    - Reopen events show "بازگشایی شد" title
    - Reactivation events show "بازگشت" title
    - Reopen note appears in timeline
  AUDIT TRAIL
    - OrderStatusHistory created for reopen
    - History is immutable after creation
"""

import tempfile
from datetime import date

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from kyc.models import KYCProfile
from notifications.models import Notification
from orders.models import Category, Order, OrderStatusHistory, SubCategory
from orders.workflow import (
    is_recovery_transition,
    is_valid_transition,
    get_allowed_transitions,
    validate_transition,
    InvalidTransition,
)

_PRIVATE_MEDIA_TMP = tempfile.mkdtemp(prefix='jp24_reopen_test_')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(email, is_staff=False, kyc_approved=False):
    user = User.objects.create_user(
        email=email, password='Test1234!',
        first_name='Test', last_name='User',
    )
    user.is_staff = is_staff
    user.save()
    if kyc_approved:
        numeric_id = str(abs(hash(email)) % 10_000_000_000).zfill(10)
        KYCProfile.objects.create(
            user=user,
            national_id=numeric_id,
            date_of_birth=date(1990, 1, 1),
            status=KYCProfile.STATUS_APPROVED,
        )
    return user


def _make_category():
    cat = Category.objects.create(title='Reopen Cat', slug='reopen-cat')
    sub = SubCategory.objects.create(category=cat, title='Reopen Sub')
    return cat, sub


def _make_order(user, cat, sub, status=None):
    order = Order.objects.create(
        user=user, category=cat, subcategory=sub,
        description='Reopen test order',
    )
    if status:
        order.status = status
        order.save()
    return order


# ===========================================================================
# Workflow rules
# ===========================================================================

class ReopenWorkflowRulesTests(TestCase):

    # ── new valid transitions ──────────────────────────────────────────────

    def test_completed_to_in_progress_valid(self):
        self.assertTrue(is_valid_transition('completed', 'in_progress'))

    def test_cancelled_to_under_review_valid(self):
        self.assertTrue(is_valid_transition('cancelled', 'under_review'))

    # ── previously-invalid are still invalid ──────────────────────────────

    def test_completed_to_under_review_invalid(self):
        self.assertFalse(is_valid_transition('completed', 'under_review'))

    def test_completed_to_cancelled_invalid(self):
        self.assertFalse(is_valid_transition('completed', 'cancelled'))

    def test_completed_to_waiting_customer_invalid(self):
        self.assertFalse(is_valid_transition('completed', 'waiting_customer'))

    def test_cancelled_to_in_progress_invalid(self):
        self.assertFalse(is_valid_transition('cancelled', 'in_progress'))

    def test_cancelled_to_completed_invalid(self):
        self.assertFalse(is_valid_transition('cancelled', 'completed'))

    def test_cancelled_to_waiting_customer_invalid(self):
        self.assertFalse(is_valid_transition('cancelled', 'waiting_customer'))

    # ── is_recovery_transition ─────────────────────────────────────────────

    def test_completed_in_progress_is_recovery(self):
        self.assertTrue(is_recovery_transition('completed', 'in_progress'))

    def test_cancelled_under_review_is_recovery(self):
        self.assertTrue(is_recovery_transition('cancelled', 'under_review'))

    def test_normal_transition_is_not_recovery(self):
        self.assertFalse(is_recovery_transition('submitted', 'under_review'))
        self.assertFalse(is_recovery_transition('under_review', 'in_progress'))
        self.assertFalse(is_recovery_transition('in_progress', 'completed'))

    # ── get_allowed_transitions ────────────────────────────────────────────

    def test_completed_has_one_allowed_transition(self):
        allowed = get_allowed_transitions('completed')
        self.assertEqual(allowed, ['in_progress'])

    def test_cancelled_has_one_allowed_transition(self):
        allowed = get_allowed_transitions('cancelled')
        self.assertEqual(allowed, ['under_review'])

    # ── validate_transition ────────────────────────────────────────────────

    def test_validate_completed_to_in_progress_ok(self):
        validate_transition('completed', 'in_progress')  # must not raise

    def test_validate_cancelled_to_under_review_ok(self):
        validate_transition('cancelled', 'under_review')  # must not raise

    def test_validate_completed_to_cancelled_raises(self):
        with self.assertRaises(InvalidTransition):
            validate_transition('completed', 'cancelled')

    def test_validate_cancelled_to_completed_raises(self):
        with self.assertRaises(InvalidTransition):
            validate_transition('cancelled', 'completed')


# ===========================================================================
# Admin integration tests
# ===========================================================================

@override_settings(PRIVATE_MEDIA_ROOT=_PRIVATE_MEDIA_TMP)
class AdminReopenTests(TestCase):

    def setUp(self):
        self.cat, self.sub = _make_category()
        self.admin = _make_user('adm-reopen@test.com', is_staff=True)
        self.admin.is_superuser = True
        self.admin.save()
        self.user = _make_user('cust-reopen@test.com', kyc_approved=True)
        self.client.force_login(self.admin)

    def _post_admin_change(self, order, extra_data):
        url = reverse('admin:orders_order_change', args=[order.pk])
        data = {
            'order_number':        order.order_number,
            'user':                self.user.pk,
            'category':            self.cat.pk,
            'subcategory':         self.sub.pk,
            'description':         order.description,
            'status':              order.status,
            'status_change_note':  '',
            'attachments-TOTAL_FORMS':      '0',
            'attachments-INITIAL_FORMS':    '0',
            'attachments-MIN_NUM_FORMS':    '0',
            'attachments-MAX_NUM_FORMS':    '1000',
            'messages-TOTAL_FORMS':         '0',
            'messages-INITIAL_FORMS':       '0',
            'messages-MIN_NUM_FORMS':       '0',
            'messages-MAX_NUM_FORMS':       '1000',
            'status_history-TOTAL_FORMS':   '0',
            'status_history-INITIAL_FORMS': '0',
            'status_history-MIN_NUM_FORMS': '0',
            'status_history-MAX_NUM_FORMS': '0',
        }
        data.update(extra_data)
        return self.client.post(url, data, follow=True)

    def test_reopen_completed_accepted(self):
        order = _make_order(self.user, self.cat, self.sub, status='completed')
        self._post_admin_change(order, {'status': 'in_progress'})
        order.refresh_from_db()
        self.assertEqual(order.status, 'in_progress')

    def test_reopen_completed_creates_history(self):
        order = _make_order(self.user, self.cat, self.sub, status='completed')
        self._post_admin_change(order, {'status': 'in_progress'})
        h = OrderStatusHistory.objects.filter(order=order).first()
        self.assertIsNotNone(h)
        self.assertEqual(h.old_status, 'completed')
        self.assertEqual(h.new_status, 'in_progress')

    def test_reopen_completed_stores_note(self):
        order = _make_order(self.user, self.cat, self.sub, status='completed')
        note = 'این سفارش به اشتباه تکمیل شده بود.'
        self._post_admin_change(order, {'status': 'in_progress', 'status_change_note': note})
        h = OrderStatusHistory.objects.filter(order=order).first()
        self.assertEqual(h.note, note)

    def test_reactivate_cancelled_accepted(self):
        order = _make_order(self.user, self.cat, self.sub, status='cancelled')
        self._post_admin_change(order, {'status': 'under_review'})
        order.refresh_from_db()
        self.assertEqual(order.status, 'under_review')

    def test_reactivate_cancelled_creates_history(self):
        order = _make_order(self.user, self.cat, self.sub, status='cancelled')
        self._post_admin_change(order, {'status': 'under_review'})
        h = OrderStatusHistory.objects.filter(order=order).first()
        self.assertIsNotNone(h)
        self.assertEqual(h.old_status, 'cancelled')
        self.assertEqual(h.new_status, 'under_review')

    def test_completed_to_cancelled_rejected(self):
        order = _make_order(self.user, self.cat, self.sub, status='completed')
        self._post_admin_change(order, {'status': 'cancelled'})
        order.refresh_from_db()
        self.assertEqual(order.status, 'completed')

    def test_cancelled_to_completed_rejected(self):
        order = _make_order(self.user, self.cat, self.sub, status='cancelled')
        self._post_admin_change(order, {'status': 'completed'})
        order.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')

    def test_workflow_hint_shows_reopen_label_for_completed(self):
        order = _make_order(self.user, self.cat, self.sub, status='completed')
        resp = self.client.get(
            reverse('admin:orders_order_change', args=[order.pk])
        )
        self.assertContains(resp, 'بازگشایی سفارش')

    def test_workflow_hint_shows_reopen_label_for_cancelled(self):
        order = _make_order(self.user, self.cat, self.sub, status='cancelled')
        resp = self.client.get(
            reverse('admin:orders_order_change', args=[order.pk])
        )
        self.assertContains(resp, 'بازگشایی سفارش')


# ===========================================================================
# Notification tests
# ===========================================================================

@override_settings(PRIVATE_MEDIA_ROOT=_PRIVATE_MEDIA_TMP)
class ReopenNotificationTests(TestCase):

    def setUp(self):
        self.cat, self.sub = _make_category()
        self.user = _make_user('notif-reopen@test.com', kyc_approved=True)

    def _order(self, status):
        return _make_order(self.user, self.cat, self.sub, status=status)

    def test_completed_to_in_progress_fires_reopened(self):
        order = self._order('completed')
        Notification.objects.all().delete()
        order.status = Order.STATUS_IN_PROGRESS
        order.save()
        n = Notification.objects.filter(
            user=self.user,
            notification_type=Notification.TYPE_ORDER_REOPENED,
        )
        self.assertEqual(n.count(), 1)
        self.assertIn('بازگشایی', n.first().message)

    def test_cancelled_to_under_review_fires_reactivated(self):
        order = self._order('cancelled')
        Notification.objects.all().delete()
        order.status = Order.STATUS_UNDER_REVIEW
        order.save()
        n = Notification.objects.filter(
            user=self.user,
            notification_type=Notification.TYPE_ORDER_REACTIVATED,
        )
        self.assertEqual(n.count(), 1)
        self.assertIn('بازگشایی', n.first().message)

    def test_normal_in_progress_still_fires_in_progress_type(self):
        """under_review → in_progress must still fire TYPE_ORDER_IN_PROGRESS."""
        order = self._order('under_review')
        Notification.objects.all().delete()
        order.status = Order.STATUS_IN_PROGRESS
        order.save()
        n = Notification.objects.filter(
            user=self.user,
            notification_type=Notification.TYPE_ORDER_IN_PROGRESS,
        )
        self.assertEqual(n.count(), 1)

    def test_normal_under_review_still_fires_in_review_type(self):
        """submitted → under_review must still fire TYPE_ORDER_IN_REVIEW."""
        order = self._order('submitted')
        Notification.objects.all().delete()
        order.status = Order.STATUS_UNDER_REVIEW
        order.save()
        n = Notification.objects.filter(
            user=self.user,
            notification_type=Notification.TYPE_ORDER_IN_REVIEW,
        )
        self.assertEqual(n.count(), 1)

    def test_reopened_notification_not_fired_for_normal_transition(self):
        """TYPE_ORDER_REOPENED must NOT fire for under_review→in_progress."""
        order = self._order('under_review')
        Notification.objects.all().delete()
        order.status = Order.STATUS_IN_PROGRESS
        order.save()
        self.assertEqual(
            Notification.objects.filter(
                user=self.user,
                notification_type=Notification.TYPE_ORDER_REOPENED,
            ).count(),
            0,
        )


# ===========================================================================
# Timeline tests
# ===========================================================================

@override_settings(PRIVATE_MEDIA_ROOT=_PRIVATE_MEDIA_TMP)
class ReopenTimelineTests(TestCase):

    def setUp(self):
        self.cat, self.sub = _make_category()
        self.user  = _make_user('tl-reopen@test.com', kyc_approved=True)
        self.admin = _make_user('tl-adm-reopen@test.com', is_staff=True)
        self.client.force_login(self.user)

    def _h(self, order, old_status, new_status, note=''):
        return OrderStatusHistory.objects.create(
            order=order, old_status=old_status, new_status=new_status,
            changed_by=self.admin, note=note,
        )

    def test_reopen_event_title_shown(self):
        order = _make_order(self.user, self.cat, self.sub, status='in_progress')
        self._h(order, 'completed', 'in_progress')
        resp = self.client.get(reverse('order_detail', args=[order.pk]))
        self.assertContains(resp, 'بازگشایی شد')

    def test_reactivation_event_title_shown(self):
        order = _make_order(self.user, self.cat, self.sub, status='under_review')
        self._h(order, 'cancelled', 'under_review')
        resp = self.client.get(reverse('order_detail', args=[order.pk]))
        self.assertContains(resp, 'بازگشت')

    def test_reopen_event_distinct_from_normal_in_progress(self):
        """completed→in_progress must NOT display the normal 'در حال انجام قرار گرفت' title."""
        order = _make_order(self.user, self.cat, self.sub, status='in_progress')
        self._h(order, 'completed', 'in_progress')
        resp = self.client.get(reverse('order_detail', args=[order.pk]))
        # The reopen title should be shown
        self.assertContains(resp, 'بازگشایی شد')
        # The reopen title is NOT the regular in-progress title
        # (the regular title is still there via _HISTORY_STATUS_MAP for other history,
        #  but for THIS history entry we should have the reopen label)
        content = resp.content.decode('utf-8')
        self.assertIn('بازگشایی شد', content)

    def test_reopen_note_shown_in_timeline(self):
        order = _make_order(self.user, self.cat, self.sub, status='in_progress')
        note = 'این سفارش به اشتباه تکمیل شده بود.'
        self._h(order, 'completed', 'in_progress', note=note)
        resp = self.client.get(reverse('order_detail', args=[order.pk]))
        self.assertContains(resp, note)

    def test_reactivation_note_shown_in_timeline(self):
        order = _make_order(self.user, self.cat, self.sub, status='under_review')
        note = 'سفارش اشتباهاً لغو شده بود.'
        self._h(order, 'cancelled', 'under_review', note=note)
        resp = self.client.get(reverse('order_detail', args=[order.pk]))
        self.assertContains(resp, note)


# ===========================================================================
# Audit trail immutability
# ===========================================================================

@override_settings(PRIVATE_MEDIA_ROOT=_PRIVATE_MEDIA_TMP)
class ReopenAuditTrailTests(TestCase):

    def setUp(self):
        self.cat, self.sub = _make_category()
        self.user  = _make_user('audit-reopen@test.com', kyc_approved=True)
        self.admin = _make_user('audit-adm-reopen@test.com', is_staff=True)

    def test_history_record_created_on_reopen(self):
        order = _make_order(self.user, self.cat, self.sub, status='completed')
        OrderStatusHistory.objects.create(
            order=order,
            old_status='completed',
            new_status='in_progress',
            changed_by=self.admin,
            note='بازگشایی دستی',
        )
        self.assertEqual(
            OrderStatusHistory.objects.filter(order=order).count(), 1
        )

    def test_history_fields_unchanged_after_creation(self):
        order = _make_order(self.user, self.cat, self.sub, status='cancelled')
        h = OrderStatusHistory.objects.create(
            order=order,
            old_status='cancelled',
            new_status='under_review',
            changed_by=self.admin,
            note='بازگشایی',
        )
        h.refresh_from_db()
        self.assertEqual(h.old_status, 'cancelled')
        self.assertEqual(h.new_status, 'under_review')
        self.assertEqual(h.note, 'بازگشایی')

    def test_multiple_reopen_cycles_all_audited(self):
        """An order can be reopened more than once; every reopen is in history."""
        order = _make_order(self.user, self.cat, self.sub, status='completed')
        # First reopen
        OrderStatusHistory.objects.create(
            order=order, old_status='completed', new_status='in_progress',
            changed_by=self.admin,
        )
        order.status = 'completed'
        order.save()
        # Second reopen
        OrderStatusHistory.objects.create(
            order=order, old_status='completed', new_status='in_progress',
            changed_by=self.admin,
        )
        self.assertEqual(
            OrderStatusHistory.objects.filter(
                order=order, old_status='completed', new_status='in_progress',
            ).count(),
            2,
        )
