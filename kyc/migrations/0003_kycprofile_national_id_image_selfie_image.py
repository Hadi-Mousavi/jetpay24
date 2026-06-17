from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kyc', '0002_alter_kycprofile_national_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='kycprofile',
            name='national_id_image',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='kyc/documents/',
                verbose_name='تصویر کارت ملی',
            ),
        ),
        migrations.AddField(
            model_name='kycprofile',
            name='selfie_image',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='kyc/selfies/',
                verbose_name='سلفی با کارت ملی',
            ),
        ),
    ]
