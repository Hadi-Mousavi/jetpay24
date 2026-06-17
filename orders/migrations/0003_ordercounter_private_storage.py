"""
Migration 0003

Changes:
  1. Create OrderCounter model — per-year sequence counter used by the
     concurrency-safe _generate_order_number() function.

  2. Alter OrderAttachment.file storage from the default FileSystemStorage
     (public MEDIA_ROOT) to PrivateFileSystemStorage (private PRIVATE_MEDIA_ROOT).

  3. Alter OrderMessageAttachment.file storage — same reason.

Security note:
  Existing files on disk are NOT moved by this migration.
  If you have production data, manually move:
    MEDIA_ROOT/orders/attachments/  →  PRIVATE_MEDIA_ROOT/orders/attachments/
    MEDIA_ROOT/orders/messages/     →  PRIVATE_MEDIA_ROOT/orders/messages/
  Then update the file paths stored in OrderAttachment.file and
  OrderMessageAttachment.file if they differ.
"""

from django.db import migrations, models

import orders.storage


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_order_customer_note_assigned_admin'),
    ]

    operations = [
        # ── 1. Order counter ───────────────────────────────────────────────
        migrations.CreateModel(
            name='OrderCounter',
            fields=[
                ('id',       models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID',
                )),
                ('year',     models.IntegerField(unique=True, verbose_name='سال')),
                ('last_seq', models.IntegerField(default=0,   verbose_name='آخرین شماره')),
            ],
            options={
                'verbose_name':        'شمارنده سفارش',
                'verbose_name_plural': 'شمارنده‌های سفارش',
            },
        ),

        # ── 2. OrderAttachment — move to private storage ───────────────────
        migrations.AlterField(
            model_name='orderattachment',
            name='file',
            field=models.FileField(
                storage=orders.storage.PrivateFileSystemStorage(),
                upload_to='orders/attachments/%Y/%m/',
                verbose_name='فایل',
            ),
        ),

        # ── 3. OrderMessageAttachment — move to private storage ────────────
        migrations.AlterField(
            model_name='ordermessageattachment',
            name='file',
            field=models.FileField(
                storage=orders.storage.PrivateFileSystemStorage(),
                upload_to='orders/messages/%Y/%m/',
                verbose_name='فایل',
            ),
        ),
    ]
