from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from kyc.models import KYCProfile
from notifications.models import Notification
from orders.models import Category, Order, OrderMessage, SubCategory

User = get_user_model()


def _make_user(email, is_staff=False):
    return User.objects.create_user(
        email=email,
        password='testpass123',
        first_name='Test',
        last_name='User',
        is_staff=is_staff,
    )


def _make_category():
    cat = Category.objects.create(title='Cat', slug='cat')
    sub = SubCategory.objects.create(category=cat, title='Sub')
    return cat, sub


def _make_order(user, cat, sub):
    return Order.objects.create(
        user=user,
        category=cat,
        subcategory=sub,
        description='Test order',
    )


class NotificationSignalTests(TestCase):

    def setUp(self):
        self.cat, self.sub = _make_category()
        self.customer = _make_user('customer@test.com')
        self.staff = _make_user('staff@test.com', is_staff=True)

    def test_order_created_notification(self):
        order = _make_order(self.customer, self.cat, self.sub)
        note = Notification.objects.get(user=self.customer)
        self.assertEqual(note.notification_type, Notification.TYPE_ORDER_CREATED)
        self.assertIn(order.order_number, note.message)

    def test_order_status_changed_notification(self):
        order = _make_order(self.customer, self.cat, self.sub)
        Notification.objects.all().delete()
        order.status = Order.STATUS_IN_PROGRESS
        order.save()
        note = Notification.objects.get(user=self.customer)
        self.assertEqual(note.notification_type, Notification.TYPE_ORDER_STATUS_CHANGED)

    def test_admin_message_notification(self):
        order = _make_order(self.customer, self.cat, self.sub)
        Notification.objects.all().delete()
        OrderMessage.objects.create(
            order=order, sender=self.staff, message='سلام، پیام تیم',
        )
        note = Notification.objects.get(user=self.customer)
        self.assertEqual(note.notification_type, Notification.TYPE_ADMIN_MESSAGE)

    def test_customer_message_does_not_create_notification(self):
        order = _make_order(self.customer, self.cat, self.sub)
        before = Notification.objects.filter(user=self.customer).count()
        OrderMessage.objects.create(
            order=order, sender=self.customer, message='سوال من',
        )
        self.assertEqual(
            Notification.objects.filter(user=self.customer).count(),
            before,
        )

    def test_kyc_approved_notification(self):
        profile = KYCProfile.objects.create(user=self.customer)
        profile.status = KYCProfile.STATUS_APPROVED
        profile.save()
        note = Notification.objects.get(
            user=self.customer,
            notification_type=Notification.TYPE_KYC_APPROVED,
        )
        self.assertIn('تأیید', note.title)

    def test_kyc_rejected_notification(self):
        profile = KYCProfile.objects.create(
            user=self.customer,
            status=KYCProfile.STATUS_PENDING,
        )
        profile.status = KYCProfile.STATUS_REJECTED
        profile.save()
        note = Notification.objects.get(
            user=self.customer,
            notification_type=Notification.TYPE_KYC_REJECTED,
        )
        self.assertIn('رد', note.title)


class NotificationViewTests(TestCase):

    def setUp(self):
        self.cat, self.sub = _make_category()
        self.customer = _make_user('customer@test.com')
        self.other = _make_user('other@test.com')
        self.client = Client()
        self.client.force_login(self.customer)
        self.notification = Notification.objects.create(
            user=self.customer,
            title='تست',
            message='پیام تست',
            notification_type=Notification.TYPE_ORDER_CREATED,
        )

    def test_mark_read(self):
        resp = self.client.post(
            reverse('notification_mark_read', args=[self.notification.pk]),
        )
        self.assertEqual(resp.status_code, 302)
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_mark_read_other_users_notification_returns_404(self):
        other_note = Notification.objects.create(
            user=self.other,
            title='دیگر',
            message='پیام',
            notification_type=Notification.TYPE_ORDER_CREATED,
        )
        resp = self.client.post(
            reverse('notification_mark_read', args=[other_note.pk]),
        )
        self.assertEqual(resp.status_code, 404)

    def test_mark_all_read(self):
        Notification.objects.create(
            user=self.customer,
            title='دوم',
            message='پیام',
            notification_type=Notification.TYPE_ADMIN_MESSAGE,
        )
        resp = self.client.post(reverse('notifications_mark_all_read'))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(
            Notification.objects.filter(user=self.customer, is_read=False).exists()
        )

    def test_mark_all_read_ajax(self):
        resp = self.client.post(
            reverse('notifications_mark_all_read'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['unread_count'], 0)

    def test_dropdown_api_returns_latest_five(self):
        for i in range(7):
            Notification.objects.create(
                user=self.customer,
                title=f'N{i}',
                message=f'M{i}',
                notification_type=Notification.TYPE_ORDER_CREATED,
            )
        resp = self.client.get(reverse('notifications_dropdown'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['notifications']), 5)

    def test_dropdown_api_only_shows_own_notifications(self):
        Notification.objects.create(
            user=self.other,
            title='other',
            message='secret',
            notification_type=Notification.TYPE_ORDER_CREATED,
        )
        resp = self.client.get(reverse('notifications_dropdown'))
        titles = [n['title'] for n in resp.json()['notifications']]
        self.assertNotIn('other', titles)

    def test_dashboard_shows_latest_notifications(self):
        for i in range(12):
            Notification.objects.create(
                user=self.customer,
                title=f'N{i}',
                message=f'M{i}',
                notification_type=Notification.TYPE_ORDER_CREATED,
            )
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context['notifications']), 10)

    def test_dashboard_unread_badge(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertContains(resp, 'اعلان‌ها')
        self.assertContains(resp, '(1)')
