"""
Service Workflow Engine Sprint — comprehensive tests.

Coverage:
  WORKFLOW ENGINE (pure unit)
    - Valid transitions accepted by is_valid_transition / validate_transition
    - Invalid transitions rejected with InvalidTransition
    - Terminal states (completed, cancelled) have no allowed next steps
  ORDER STATUS HISTORY (DB)
    - Records created with correct fields
    - Ordering is newest-first
    - Properties (new_status_label, old_status_label, __str__)
  ADMIN WORKFLOW VALIDATION (integration)
    - Valid transition is persisted, history created, note stored
    - Invalid transition is rejected; order status unchanged; no history
    - No history when status unchanged
  NOTIFICATIONS (signal)
    - in_review, in_progress, waiting_customer, completed, cancelled
      each create the correct notification_type
  DASHBOARD COUNTERS
    - waiting_customer, pending_payment counters in context
    - Action-required badge visible / hidden based on count
  CUSTOMER ACTION REQUIRED FLOW
    - action_required context flag True for waiting_customer only
    - Banner shown/hidden appropriately
    - Status-change note visible on order detail
  TIMELINE INTEGRATION
    - Status history events appear in timeline
    - Notes from history shown in timeline
    - Fallback for orders without history
"""

import tempfile

from django.test import TestCase, override_settings
from django.urls import reverse

from notifications.models import Notification
from orders.models import (
    Category, Order, OrderStatusHistory, SubCategory,
)
from orders.workflow import (
    InvalidTransition,
    get_allowed_transitions,
    is_valid_transition,
    validate_transition,
)

from accounts.models import User
from kyc.models import KYCProfile
from datetime import date

_PRIVATE_MEDIA_TMP = tempfile.mkdtemp(prefix='jp24_wf_test_')


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
    cat = Category.objects.create(title='WF Category', slug='wf-cat')
    sub = SubCategory.objects.create(category=cat, title='WF Sub')
    return cat, sub


def _make_order(user, cat, sub, description='Workflow test order'):
    return Order.objects.create(
        user=user, category=cat, subcategory=sub, description=description,
    )


# ===========================================================================
# Workflow engine unit tests
# ===========================================================================

class WorkflowTransitionRulesTests(TestCase):
    """Pure unit tests for orders/workflow.py — no DB required."""

    # ── valid transitions ──────────────────────────────────────────────────

    def test_submitted_can_go_to_waiting_payment(self):
        self.assertTrue(is_valid_transition('submitted', 'waiting_customer_payment'))

    def test_submitted_can_go_to_under_review(self):
        self.assertTrue(is_valid_transition('submitted', 'under_review'))

    def test_under_review_can_go_to_in_progress(self):
        self.assertTrue(is_valid_transition('under_review', 'in_progress'))

    def test_under_review_can_go_to_cancelled(self):
        self.assertTrue(is_valid_transition('under_review', 'cancelled'))

    def test_waiting_payment_to_payment_rejected(self):
        self.assertTrue(is_valid_transition('waiting_customer_payment', 'payment_rejected'))

    def test_waiting_payment_to_under_review(self):
        self.assertTrue(is_valid_transition('waiting_customer_payment', 'under_review'))

    def test_payment_rejected_back_to_waiting_payment(self):
        self.assertTrue(is_valid_transition('payment_rejected', 'waiting_customer_payment'))

    def test_in_progress_to_waiting_customer(self):
        self.assertTrue(is_valid_transition('in_progress', 'waiting_customer'))

    def test_in_progress_to_completed(self):
        self.assertTrue(is_valid_transition('in_progress', 'completed'))

    def test_in_progress_to_cancelled(self):
        self.assertTrue(is_valid_transition('in_progress', 'cancelled'))

    def test_waiting_customer_to_in_progress(self):
        self.assertTrue(is_valid_transition('waiting_customer', 'in_progress'))

    def test_waiting_customer_to_cancelled(self):
        self.assertTrue(is_valid_transition('waiting_customer', 'cancelled'))

    # ── invalid transitions ────────────────────────────────────────────────

    def test_submitted_cannot_skip_to_completed(self):
        self.assertFalse(is_valid_transition('submitted', 'completed'))

    def test_submitted_cannot_skip_to_in_progress(self):
        self.assertFalse(is_valid_transition('submitted', 'in_progress'))

    def test_waiting_payment_cannot_jump_to_completed(self):
        self.assertFalse(is_valid_transition('waiting_customer_payment', 'completed'))

    def test_completed_has_one_recovery_transition(self):
        # completed → in_progress (reopen)
        self.assertEqual(get_allowed_transitions('completed'), ['in_progress'])

    def test_cancelled_has_one_recovery_transition(self):
        # cancelled → under_review (reopen)
        self.assertEqual(get_allowed_transitions('cancelled'), ['under_review'])

    def test_unknown_status_has_no_transitions(self):
        self.assertEqual(get_allowed_transitions('nonexistent'), [])

    def test_in_progress_cannot_go_back_to_submitted(self):
        self.assertFalse(is_valid_transition('in_progress', 'submitted'))

    def test_completed_can_reopen_to_in_progress(self):
        # Reopen sprint: completed is no longer a hard terminal state
        self.assertTrue(is_valid_transition('completed', 'in_progress'))

    def test_validate_transition_raises_on_invalid(self):
        with self.assertRaises(InvalidTransition):
            validate_transition('submitted', 'completed')

    def test_validate_transition_no_op_same_status(self):
        validate_transition('submitted', 'submitted')  # must not raise

    def test_invalid_transition_persian_message(self):
        try:
            validate_transition('submitted', 'completed')
        except InvalidTransition as exc:
            msg = exc.persian_message()
            self.assertIn('ثبت شده', msg)
            self.assertIn('تکمیل شده', msg)

    def test_get_allowed_in_progress_returns_three(self):
        allowed = get_allowed_transitions('in_progress')
        self.assertIn('waiting_customer', allowed)
        self.assertIn('completed', allowed)
        self.assertIn('cancelled', allowed)


# ===========================================================================
# OrderStatusHistory model tests
# ===========================================================================

@override_settings(PRIVATE_MEDIA_ROOT=_PRIVATE_MEDIA_TMP)
class OrderStatusHistoryModelTests(TestCase):

    def setUp(self):
        self.cat, self.sub = _make_category()
        self.user  = _make_user('hist-m@test.com', kyc_approved=True)
        self.admin = _make_user('hist-adm@test.com', is_staff=True)
        self.order = _make_order(self.user, self.cat, self.sub)

    def _h(self, old, new, note=''):
        return OrderStatusHistory.objects.create(
            order=self.order, old_status=old, new_status=new,
            changed_by=self.admin, note=note,
        )

    def test_create_history_entry(self):
        h = self._h('submitted', 'under_review')
        self.assertEqual(h.old_status, 'submitted')
        self.assertEqual(h.new_status, 'under_review')
        self.assertEqual(h.changed_by, self.admin)

    def test_history_ordering_newest_first(self):
        self._h('submitted', 'under_review')
        self._h('under_review', 'in_progress')
        qs = list(self.order.status_history.all())
        self.assertEqual(len(qs), 2)
        # Newest (higher pk) must appear first when timestamps are equal
        self.assertGreater(qs[0].pk, qs[1].pk)

    def test_history_str(self):
        h = self._h('submitted', 'under_review')
        self.assertIn(self.order.order_number, str(h))
        self.assertIn('submitted', str(h))
        self.assertIn('under_review', str(h))

    def test_new_status_label(self):
        h = self._h('submitted', 'in_progress')
        self.assertEqual(h.new_status_label, 'در حال انجام')

    def test_old_status_label(self):
        h = self._h('submitted', 'in_progress')
        self.assertEqual(h.old_status_label, 'ثبت شده')

    def test_note_stored(self):
        note = 'سفارش آماده انجام است.'
        h = self._h('under_review', 'in_progress', note=note)
        h.refresh_from_db()
        self.assertEqual(h.note, note)

    def test_waiting_customer_status_label(self):
        h = self._h('in_progress', 'waiting_customer')
        self.assertEqual(h.new_status_label, 'منتظر اقدام مشتری')

    def test_payment_rejected_status_label(self):
        h = self._h('waiting_customer_payment', 'payment_rejected')
        self.assertEqual(h.new_status_label, 'پرداخت رد شده')


# ===========================================================================
# Admin workflow validation tests
# ===========================================================================

@override_settings(PRIVATE_MEDIA_ROOT=_PRIVATE_MEDIA_TMP)
class AdminWorkflowValidationTests(TestCase):

    def setUp(self):
        self.cat, self.sub = _make_category()
        self.admin = _make_user('adm-wf@test.com', is_staff=True)
        self.admin.is_superuser = True
        self.admin.save()
        self.user  = _make_user('cust-wf@test.com', kyc_approved=True)
        self.order = _make_order(self.user, self.cat, self.sub)
        self.client.force_login(self.admin)

    def _post_admin_change(self, extra_data):
        url = reverse('admin:orders_order_change', args=[self.order.pk])
        data = {
            'order_number':        self.order.order_number,
            'user':                self.user.pk,
            'category':            self.cat.pk,
            'subcategory':         self.sub.pk,
            'description':         self.order.description,
            'status':              self.order.status,
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

    def test_valid_transition_accepted(self):
        resp = self._post_admin_change({'status': 'under_review'})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'under_review')

    def test_valid_transition_creates_history(self):
        self._post_admin_change({'status': 'under_review'})
        h = OrderStatusHistory.objects.filter(order=self.order).first()
        self.assertIsNotNone(h)
        self.assertEqual(h.old_status, 'submitted')
        self.assertEqual(h.new_status, 'under_review')

    def test_valid_transition_stores_note(self):
        note = 'مدارک بررسی شد.'
        self._post_admin_change({'status': 'under_review', 'status_change_note': note})
        h = OrderStatusHistory.objects.filter(order=self.order).first()
        self.assertIsNotNone(h)
        self.assertEqual(h.note, note)

    def test_invalid_transition_rejected(self):
        self._post_admin_change({'status': 'completed'})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'submitted')

    def test_invalid_transition_shows_error(self):
        resp = self._post_admin_change({'status': 'completed'})
        # The form must re-render with an error (errorlist CSS class from Django admin)
        self.assertContains(resp, 'errorlist', status_code=200)

    def test_invalid_transition_creates_no_history(self):
        self._post_admin_change({'status': 'completed'})
        self.assertEqual(OrderStatusHistory.objects.filter(order=self.order).count(), 0)

    def test_no_history_when_status_unchanged(self):
        self._post_admin_change({'status': self.order.status})
        self.assertEqual(OrderStatusHistory.objects.filter(order=self.order).count(), 0)

    def test_skip_registered_to_in_progress_rejected(self):
        self._post_admin_change({'status': 'in_progress'})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'submitted')

    def test_waiting_payment_to_under_review_valid(self):
        self.order.status = Order.STATUS_WAITING_PAYMENT
        self.order.save()
        resp = self._post_admin_change({'status': 'under_review'})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'under_review')


# ===========================================================================
# Workflow notification tests
# ===========================================================================

@override_settings(PRIVATE_MEDIA_ROOT=_PRIVATE_MEDIA_TMP)
class WorkflowNotificationTests(TestCase):

    def setUp(self):
        self.cat, self.sub = _make_category()
        self.user  = _make_user('notif-wf2@test.com', kyc_approved=True)
        self.order = _make_order(self.user, self.cat, self.sub)

    def _set_status(self, status):
        self.order.status = status
        self.order.save()

    def test_in_review_notification(self):
        self._set_status(Order.STATUS_UNDER_REVIEW)
        n = Notification.objects.filter(
            user=self.user,
            notification_type=Notification.TYPE_ORDER_IN_REVIEW,
        )
        self.assertEqual(n.count(), 1)

    def test_in_progress_notification(self):
        self.order.status = Order.STATUS_UNDER_REVIEW
        self.order.save()
        self._set_status(Order.STATUS_IN_PROGRESS)
        n = Notification.objects.filter(
            user=self.user,
            notification_type=Notification.TYPE_ORDER_IN_PROGRESS,
        )
        self.assertEqual(n.count(), 1)

    def test_waiting_customer_notification(self):
        self.order.status = Order.STATUS_IN_PROGRESS
        self.order.save()
        self._set_status(Order.STATUS_WAITING_CUSTOMER)
        n = Notification.objects.filter(
            user=self.user,
            notification_type=Notification.TYPE_ORDER_WAITING_CUSTOMER,
        )
        self.assertEqual(n.count(), 1)
        self.assertIn('منتظر', n.first().message)

    def test_completed_notification(self):
        self.order.status = Order.STATUS_IN_PROGRESS
        self.order.save()
        self._set_status(Order.STATUS_COMPLETED)
        n = Notification.objects.filter(
            user=self.user,
            notification_type=Notification.TYPE_ORDER_COMPLETED,
        )
        self.assertEqual(n.count(), 1)

    def test_cancelled_notification(self):
        self.order.status = Order.STATUS_UNDER_REVIEW
        self.order.save()
        self._set_status(Order.STATUS_CANCELLED)
        n = Notification.objects.filter(
            user=self.user,
            notification_type=Notification.TYPE_ORDER_CANCELLED,
        )
        self.assertEqual(n.count(), 1)

    def test_no_duplicate_notification_on_resave_same_status(self):
        self._set_status(Order.STATUS_UNDER_REVIEW)
        count_before = Notification.objects.filter(
            user=self.user,
            notification_type=Notification.TYPE_ORDER_IN_REVIEW,
        ).count()
        # Save again with same status — signal checks previous != current
        self.order.save()
        count_after = Notification.objects.filter(
            user=self.user,
            notification_type=Notification.TYPE_ORDER_IN_REVIEW,
        ).count()
        self.assertEqual(count_before, count_after)


# ===========================================================================
# Dashboard counter tests
# ===========================================================================

@override_settings(PRIVATE_MEDIA_ROOT=_PRIVATE_MEDIA_TMP)
class DashboardCounterTests(TestCase):

    def setUp(self):
        self.cat, self.sub = _make_category()
        self.user = _make_user('dash-wf@test.com', kyc_approved=True)
        self.client.force_login(self.user)
        self.url = reverse('dashboard')

    def _order(self, status):
        o = _make_order(self.user, self.cat, self.sub)
        o.status = status
        o.save()
        return o

    def test_total_orders(self):
        self._order(Order.STATUS_SUBMITTED)
        self._order(Order.STATUS_COMPLETED)
        resp = self.client.get(self.url)
        self.assertEqual(resp.context['total_orders'], 2)

    def test_pending_orders_counter(self):
        self._order(Order.STATUS_SUBMITTED)
        self._order(Order.STATUS_UNDER_REVIEW)
        self._order(Order.STATUS_COMPLETED)
        resp = self.client.get(self.url)
        self.assertEqual(resp.context['pending_orders'], 2)

    def test_in_progress_counter(self):
        self._order(Order.STATUS_IN_PROGRESS)
        resp = self.client.get(self.url)
        self.assertEqual(resp.context['in_progress_orders'], 1)

    def test_waiting_customer_counter(self):
        self._order(Order.STATUS_WAITING_CUSTOMER)
        resp = self.client.get(self.url)
        self.assertEqual(resp.context['waiting_customer_orders'], 1)

    def test_pending_payment_counter(self):
        self._order(Order.STATUS_WAITING_PAYMENT)
        resp = self.client.get(self.url)
        self.assertEqual(resp.context['pending_payment_orders'], 1)

    def test_completed_counter(self):
        self._order(Order.STATUS_COMPLETED)
        self._order(Order.STATUS_COMPLETED)
        resp = self.client.get(self.url)
        self.assertEqual(resp.context['completed_orders'], 2)

    def test_waiting_customer_badge_visible_when_nonzero(self):
        self._order(Order.STATUS_WAITING_CUSTOMER)
        resp = self.client.get(self.url)
        self.assertContains(resp, 'نیاز به اقدام')

    def test_action_required_row_class_in_orders_list(self):
        self._order(Order.STATUS_WAITING_CUSTOMER)
        resp = self.client.get(self.url)
        self.assertContains(resp, 'action-required-row')

    def test_no_action_required_row_when_no_waiting_customer(self):
        self._order(Order.STATUS_SUBMITTED)
        resp = self.client.get(self.url)
        # The class="action-required-row" HTML attribute must not appear
        # (the CSS definition string may appear in <style> but the attribute won't)
        self.assertNotContains(resp, 'class="action-required-row"')


# ===========================================================================
# Customer action-required flow tests
# ===========================================================================

@override_settings(PRIVATE_MEDIA_ROOT=_PRIVATE_MEDIA_TMP)
class CustomerActionRequiredTests(TestCase):

    def setUp(self):
        self.cat, self.sub = _make_category()
        self.user  = _make_user('action-wf@test.com', kyc_approved=True)
        self.admin = _make_user('action-adm@test.com', is_staff=True)
        self.order = _make_order(self.user, self.cat, self.sub)
        self.client.force_login(self.user)

    def test_action_required_flag_true_for_waiting_customer(self):
        self.order.status = Order.STATUS_WAITING_CUSTOMER
        self.order.save()
        resp = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertTrue(resp.context['action_required'])

    def test_action_required_flag_false_for_submitted(self):
        resp = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertFalse(resp.context['action_required'])

    def test_action_required_banner_shown(self):
        self.order.status = Order.STATUS_WAITING_CUSTOMER
        self.order.save()
        resp = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(resp, 'این سفارش نیاز به اقدام شما دارد')

    def test_action_required_banner_not_shown_for_submitted(self):
        resp = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertNotContains(resp, 'این سفارش نیاز به اقدام شما دارد')

    def test_status_note_shown_in_action_banner(self):
        self.order.status = Order.STATUS_WAITING_CUSTOMER
        self.order.save()
        note = 'لطفاً اطلاعات ویزا را ارسال کنید.'
        OrderStatusHistory.objects.create(
            order=self.order,
            old_status=Order.STATUS_IN_PROGRESS,
            new_status=Order.STATUS_WAITING_CUSTOMER,
            changed_by=self.admin,
            note=note,
        )
        resp = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(resp, note)

    def test_latest_history_context(self):
        h = OrderStatusHistory.objects.create(
            order=self.order,
            old_status=Order.STATUS_SUBMITTED,
            new_status=Order.STATUS_UNDER_REVIEW,
            changed_by=self.admin,
            note='بررسی شد',
        )
        resp = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertEqual(resp.context['latest_history'], h)

    def test_status_note_shown_in_info_banner_for_non_action_order(self):
        """A status note should still show for non-waiting_customer orders."""
        h = OrderStatusHistory.objects.create(
            order=self.order,
            old_status=Order.STATUS_SUBMITTED,
            new_status=Order.STATUS_UNDER_REVIEW,
            changed_by=self.admin,
            note='سفارش در حال بررسی است.',
        )
        self.order.status = Order.STATUS_UNDER_REVIEW
        self.order.save()
        resp = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(resp, 'سفارش در حال بررسی است.')


# ===========================================================================
# Timeline integration tests
# ===========================================================================

@override_settings(PRIVATE_MEDIA_ROOT=_PRIVATE_MEDIA_TMP)
class TimelineIntegrationTests(TestCase):

    def setUp(self):
        self.cat, self.sub = _make_category()
        self.user  = _make_user('tl-wf@test.com', kyc_approved=True)
        self.admin = _make_user('tl-adm@test.com', is_staff=True)
        self.order = _make_order(self.user, self.cat, self.sub)
        self.client.force_login(self.user)

    def _h(self, old, new, note=''):
        return OrderStatusHistory.objects.create(
            order=self.order, old_status=old, new_status=new,
            changed_by=self.admin, note=note,
        )

    def test_timeline_shows_under_review_event(self):
        self._h('submitted', 'under_review')
        resp = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(resp, 'سفارش در حال بررسی قرار گرفت')

    def test_timeline_shows_in_progress_event(self):
        self._h('submitted', 'under_review')
        self._h('under_review', 'in_progress')
        resp = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(resp, 'سفارش در حال انجام قرار گرفت')

    def test_timeline_shows_waiting_customer_event(self):
        self._h('in_progress', 'waiting_customer')
        resp = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(resp, 'سفارش منتظر اقدام شما است')

    def test_timeline_shows_completed_event(self):
        self._h('in_progress', 'completed')
        resp = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(resp, 'سفارش تکمیل شد')

    def test_timeline_shows_cancelled_event(self):
        self._h('under_review', 'cancelled')
        resp = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(resp, 'سفارش لغو شد')

    def test_timeline_note_shown_in_event(self):
        note = 'مدارک بررسی شد.'
        self._h('submitted', 'under_review', note=note)
        resp = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(resp, note)

    def test_timeline_context_status_history_populated(self):
        self._h('submitted', 'under_review')
        resp = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertEqual(len(resp.context['status_history']), 1)

    def test_timeline_fallback_for_orders_without_history(self):
        """Order without history falls back to showing current-status event."""
        self.order.status = Order.STATUS_COMPLETED
        self.order.save()
        resp = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(resp, 'سفارش تکمیل شد')

    def test_multiple_history_events_all_in_timeline(self):
        self._h('submitted', 'under_review')
        self._h('under_review', 'in_progress')
        self._h('in_progress', 'completed')
        resp = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(resp, 'سفارش در حال بررسی قرار گرفت')
        self.assertContains(resp, 'سفارش در حال انجام قرار گرفت')
        self.assertContains(resp, 'سفارش تکمیل شد')
