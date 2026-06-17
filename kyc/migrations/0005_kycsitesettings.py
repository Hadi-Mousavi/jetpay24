from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kyc', '0004_kycprofile_status_not_submitted'),
    ]

    operations = [
        migrations.CreateModel(
            name='KYCSiteSettings',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID',
                )),
                ('guide_image', models.ImageField(
                    blank=True,
                    help_text='این تصویر در صفحه احراز هویت کاربران نمایش داده می‌شود.',
                    null=True,
                    upload_to='kyc/guide/',
                    verbose_name='تصویر راهنما',
                )),
            ],
            options={
                'verbose_name': 'تنظیمات KYC',
                'verbose_name_plural': 'تنظیمات KYC',
            },
        ),
    ]
