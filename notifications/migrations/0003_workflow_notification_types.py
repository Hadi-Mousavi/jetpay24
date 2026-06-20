"""
Migration 0003: Add workflow-specific notification types.

Adds: ORDER_IN_REVIEW, ORDER_IN_PROGRESS, ORDER_WAITING_CUSTOMER,
      ORDER_COMPLETED, ORDER_CANCELLED
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0002_alter_notification_notification_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='notification_type',
            field=models.CharField(
                choices=[
                    ('ORDER_CREATED',          'ثبت سفارش'),
                    ('ORDER_STATUS_CHANGED',   'تغییر وضعیت سفارش'),
                    ('ORDER_IN_REVIEW',        'سفارش در حال بررسی'),
                    ('ORDER_IN_PROGRESS',      'سفارش در حال انجام'),
                    ('ORDER_WAITING_CUSTOMER', 'سفارش نیاز به اقدام مشتری'),
                    ('ORDER_COMPLETED',        'سفارش تکمیل شد'),
                    ('ORDER_CANCELLED',        'سفارش لغو شد'),
                    ('ADMIN_MESSAGE',          'پیام ادمین'),
                    ('KYC_APPROVED',           'تأیید احراز هویت'),
                    ('KYC_REJECTED',           'رد احراز هویت'),
                    ('KYC_NEEDS_CORRECTION',   'درخواست اصلاح احراز هویت'),
                    ('PAYMENT_APPROVED',       'تأیید پرداخت'),
                    ('PAYMENT_REJECTED',       'رد پرداخت'),
                ],
                db_index=True,
                max_length=30,
                verbose_name='نوع اعلان',
            ),
        ),
    ]
