from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id',            models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title',         models.CharField(max_length=200, verbose_name='عنوان')),
                ('slug',          models.SlugField(allow_unicode=True, max_length=200, unique=True, verbose_name='اسلاگ')),
                ('is_active',     models.BooleanField(default=True, verbose_name='فعال')),
                ('display_order', models.PositiveSmallIntegerField(default=0, verbose_name='ترتیب نمایش')),
                ('created_at',    models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')),
            ],
            options={
                'verbose_name':        'دسته‌بندی',
                'verbose_name_plural': 'دسته‌بندی‌ها',
                'ordering':            ['display_order', 'title'],
            },
        ),
        migrations.CreateModel(
            name='SubCategory',
            fields=[
                ('id',            models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title',         models.CharField(max_length=200, verbose_name='عنوان')),
                ('description',   models.TextField(blank=True, verbose_name='توضیحات')),
                ('is_active',     models.BooleanField(default=True, verbose_name='فعال')),
                ('display_order', models.PositiveSmallIntegerField(default=0, verbose_name='ترتیب نمایش')),
                ('category',      models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='subcategories',
                    to='orders.category',
                    verbose_name='دسته‌بندی',
                )),
            ],
            options={
                'verbose_name':        'زیر دسته‌بندی',
                'verbose_name_plural': 'زیر دسته‌بندی‌ها',
                'ordering':            ['display_order', 'title'],
            },
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id',                models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order_number',      models.CharField(editable=False, max_length=20, unique=True, verbose_name='شماره سفارش')),
                ('organization_name', models.CharField(blank=True, max_length=300, verbose_name='نام سازمان / دانشگاه')),
                ('amount',            models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True, verbose_name='مبلغ')),
                ('currency',          models.CharField(blank=True, help_text='مثال: USD, EUR, CAD', max_length=10, verbose_name='ارز')),
                ('deadline',          models.DateField(blank=True, null=True, verbose_name='ددلاین')),
                ('description',       models.TextField(verbose_name='توضیحات')),
                ('status',            models.CharField(
                    choices=[
                        ('draft',                    'پیش‌نویس'),
                        ('submitted',               'ثبت شده'),
                        ('under_review',            'در حال بررسی'),
                        ('waiting_customer_payment','در انتظار پرداخت'),
                        ('in_progress',             'در حال انجام'),
                        ('completed',               'تکمیل شده'),
                        ('rejected',                'رد شده'),
                        ('cancelled',               'لغو شده'),
                    ],
                    db_index=True, default='submitted', max_length=30, verbose_name='وضعیت',
                )),
                ('admin_note',  models.TextField(blank=True, verbose_name='یادداشت ادمین')),
                ('created_at',  models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')),
                ('updated_at',  models.DateTimeField(auto_now=True, verbose_name='آخرین بروزرسانی')),
                ('category',    models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    to='orders.category', verbose_name='دسته‌بندی',
                )),
                ('subcategory', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    to='orders.subcategory', verbose_name='زیر دسته‌بندی',
                )),
                ('user',        models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='orders',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='کاربر',
                )),
            ],
            options={
                'verbose_name':        'سفارش',
                'verbose_name_plural': 'سفارش‌ها',
                'ordering':            ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='OrderAttachment',
            fields=[
                ('id',         models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file',       models.FileField(upload_to='orders/attachments/%Y/%m/', verbose_name='فایل')),
                ('title',      models.CharField(blank=True, max_length=200, verbose_name='عنوان')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاریخ بارگذاری')),
                ('order',      models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='attachments',
                    to='orders.order', verbose_name='سفارش',
                )),
                ('uploaded_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='بارگذاری توسط',
                )),
            ],
            options={
                'verbose_name':        'پیوست سفارش',
                'verbose_name_plural': 'پیوست‌های سفارش',
                'ordering':            ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='OrderMessage',
            fields=[
                ('id',         models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message',    models.TextField(verbose_name='پیام')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ارسال')),
                ('order',      models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='messages',
                    to='orders.order', verbose_name='سفارش',
                )),
                ('sender',     models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='فرستنده',
                )),
            ],
            options={
                'verbose_name':        'پیام سفارش',
                'verbose_name_plural': 'پیام‌های سفارش',
                'ordering':            ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='OrderMessageAttachment',
            fields=[
                ('id',          models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file',        models.FileField(upload_to='orders/messages/%Y/%m/', verbose_name='فایل')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True, verbose_name='تاریخ بارگذاری')),
                ('message',     models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='attachments',
                    to='orders.ordermessage', verbose_name='پیام',
                )),
            ],
            options={
                'verbose_name':        'پیوست پیام',
                'verbose_name_plural': 'پیوست‌های پیام',
            },
        ),
    ]
