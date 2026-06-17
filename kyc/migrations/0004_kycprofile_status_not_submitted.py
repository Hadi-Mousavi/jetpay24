from django.db import migrations, models


def migrate_empty_pending_to_not_submitted(apps, schema_editor):
    """
    Profiles that were created by get_or_create() but never actually submitted
    (no national_id) inherited the old default status='pending'.
    Re-classify them as 'not_submitted' so they are editable again.
    """
    KYCProfile = apps.get_model('kyc', 'KYCProfile')
    KYCProfile.objects.filter(
        status='pending',
        national_id__isnull=True,
    ).update(status='not_submitted')


class Migration(migrations.Migration):

    dependencies = [
        ('kyc', '0003_kycprofile_national_id_image_selfie_image'),
    ]

    operations = [
        migrations.AlterField(
            model_name='kycprofile',
            name='status',
            field=models.CharField(
                choices=[
                    ('not_submitted', 'تکمیل نشده'),
                    ('pending',       'در انتظار بررسی'),
                    ('approved',      'تأیید شده'),
                    ('rejected',      'رد شده'),
                ],
                default='not_submitted',
                db_index=True,
                max_length=13,
                verbose_name='وضعیت',
            ),
        ),
        migrations.RunPython(
            migrate_empty_pending_to_not_submitted,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
