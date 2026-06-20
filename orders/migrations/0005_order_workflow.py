"""
Migration 0005: Service Workflow Engine Sprint

Changes:
  1. AlterField on Order.status — adds 'payment_rejected' and 'waiting_customer'
     choices and updates max_length (already 30, sufficient).
  2. CreateModel OrderStatusHistory — immutable audit log of status transitions.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0004_ordermessage_is_read'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ── 1. Expand Order.status choices ────────────────────────────────────
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft',                    'پیش‌نویس'),
                    ('submitted',                'ثبت شده'),
                    ('under_review',             'در حال بررسی'),
                    ('waiting_customer_payment', 'در انتظار پرداخت'),
                    ('payment_rejected',         'پرداخت رد شده'),
                    ('in_progress',              'در حال انجام'),
                    ('waiting_customer',         'منتظر اقدام مشتری'),
                    ('completed',                'تکمیل شده'),
                    ('rejected',                 'رد شده'),
                    ('cancelled',                'لغو شده'),
                ],
                db_index=True,
                default='submitted',
                max_length=30,
                verbose_name='وضعیت',
            ),
        ),

        # ── 2. Create OrderStatusHistory ──────────────────────────────────────
        migrations.CreateModel(
            name='OrderStatusHistory',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID',
                )),
                ('old_status', models.CharField(
                    max_length=30, verbose_name='وضعیت قبلی',
                )),
                ('new_status', models.CharField(
                    max_length=30, db_index=True, verbose_name='وضعیت جدید',
                )),
                ('note', models.TextField(
                    blank=True,
                    verbose_name='یادداشت تغییر وضعیت',
                    help_text='این یادداشت برای مشتری قابل مشاهده است.',
                )),
                ('created_at', models.DateTimeField(
                    auto_now_add=True, verbose_name='تاریخ تغییر',
                )),
                ('changed_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='status_changes',
                    limit_choices_to={'is_staff': True},
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='تغییر داده‌شده توسط',
                )),
                ('order', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='status_history',
                    to='orders.order',
                    verbose_name='سفارش',
                )),
            ],
            options={
                'verbose_name':        'تاریخچه وضعیت',
                'verbose_name_plural': 'تاریخچه وضعیت‌ها',
                'ordering':            ['-created_at'],
            },
        ),
    ]
