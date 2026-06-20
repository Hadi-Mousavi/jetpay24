"""
KYC Phase 2: banking information, bank-card image, admin note,
needs_correction status, and status field max_length expansion.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kyc', '0006_alter_kycprofile_options_and_more'),
    ]

    operations = [
        # Expand status max_length: 'needs_correction' = 16 chars (was 13)
        migrations.AlterField(
            model_name='kycprofile',
            name='status',
            field=models.CharField(
                choices=[
                    ('not_submitted',    'تکمیل نشده'),
                    ('pending',          'در انتظار بررسی'),
                    ('approved',         'تأیید شده'),
                    ('rejected',         'رد شده'),
                    ('needs_correction', 'نیاز به اصلاح'),
                ],
                db_index=True,
                default='not_submitted',
                max_length=20,
                verbose_name='وضعیت',
            ),
        ),

        # Banking information fields
        migrations.AddField(
            model_name='kycprofile',
            name='card_holder_name',
            field=models.CharField(blank=True, max_length=150, verbose_name='نام صاحب کارت'),
        ),
        migrations.AddField(
            model_name='kycprofile',
            name='bank_name',
            field=models.CharField(blank=True, max_length=100, verbose_name='نام بانک'),
        ),
        migrations.AddField(
            model_name='kycprofile',
            name='card_last4',
            field=models.CharField(blank=True, max_length=4, verbose_name='چهار رقم آخر کارت'),
        ),
        migrations.AddField(
            model_name='kycprofile',
            name='bank_card_image',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='kyc/bank_cards/',
                verbose_name='تصویر کارت بانکی',
            ),
        ),

        # Admin review note
        migrations.AddField(
            model_name='kycprofile',
            name='admin_note',
            field=models.TextField(
                blank=True,
                help_text='این یادداشت هنگام رد یا درخواست اصلاح به مشتری نمایش داده می‌شود.',
                verbose_name='یادداشت ادمین',
            ),
        ),
    ]
