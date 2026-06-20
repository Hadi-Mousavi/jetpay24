"""Initial migration for the payments app."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import orders.storage


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('orders', '0004_ordermessage_is_read'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True, verbose_name='مبلغ')),
                ('currency', models.CharField(blank=True, max_length=10, verbose_name='ارز')),
                ('receipt_file', models.FileField(
                    storage=orders.storage.PrivateFileSystemStorage(),
                    upload_to='payments/receipts/%Y/%m/',
                    verbose_name='فایل رسید',
                )),
                ('reference_number', models.CharField(
                    blank=True,
                    help_text='شماره مرجع تراکنش بانکی (اختیاری)',
                    max_length=100,
                    verbose_name='شماره مرجع / پیگیری',
                )),
                ('status', models.CharField(
                    choices=[
                        ('submitted', 'ارسال شده'),
                        ('approved',  'تأیید شده'),
                        ('rejected',  'رد شده'),
                    ],
                    db_index=True,
                    default='submitted',
                    max_length=15,
                    verbose_name='وضعیت',
                )),
                ('rejection_note', models.TextField(
                    blank=True,
                    help_text='در صورت رد پرداخت، این متن به مشتری نمایش داده می‌شود.',
                    verbose_name='دلیل رد',
                )),
                ('submitted_at', models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ارسال')),
                ('reviewed_at', models.DateTimeField(blank=True, null=True, verbose_name='تاریخ بررسی')),
                ('order', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='payments',
                    to='orders.order',
                    verbose_name='سفارش',
                )),
                ('reviewed_by', models.ForeignKey(
                    blank=True,
                    limit_choices_to={'is_staff': True},
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='reviewed_payments',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='بررسی‌کننده',
                )),
            ],
            options={
                'verbose_name': 'پرداخت',
                'verbose_name_plural': 'پرداخت‌ها',
                'ordering': ['-submitted_at'],
            },
        ),
    ]
