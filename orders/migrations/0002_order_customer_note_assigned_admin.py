from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='customer_note',
            field=models.TextField(blank=True, verbose_name='یادداشت مشتری'),
        ),
        migrations.AddField(
            model_name='order',
            name='assigned_admin',
            field=models.ForeignKey(
                blank=True,
                null=True,
                limit_choices_to={'is_staff': True},
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='assigned_orders',
                to=settings.AUTH_USER_MODEL,
                verbose_name='مسئول سفارش',
            ),
        ),
    ]
