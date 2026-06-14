from django.db import models


class Order(models.Model):

    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    SERVICE_CHOICES = [
        ('APPLICATION_FEE', 'Application Fee'),
        ('TUITION', 'Tuition'),
        ('TOEFL', 'TOEFL'),
        ('GRE', 'GRE'),
        ('VISA', 'Visa'),
        ('OTHER', 'Other'),
    ]

    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField()

    service_type = models.CharField(
        max_length=30,
        choices=SERVICE_CHOICES
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    description = models.TextField(blank=True)

    document = models.FileField(
        upload_to='orders/',
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='NEW'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.name} - {self.service_type}'