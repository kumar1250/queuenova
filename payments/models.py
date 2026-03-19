from django.db import models
from django.conf import settings
from organizations.models import Service

class Payment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    METHOD_CHOICES = (
        ('UPI', 'UPI'),
        ('Razorpay', 'Razorpay'),
        ('Offline', 'Offline'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments', null=True, blank=True)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    payment_method = models.CharField(max_length=50, choices=METHOD_CHOICES, default='UPI')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)
    razorpay_transfer_id = models.CharField(max_length=100, blank=True, null=True, help_text="ID of the transfer to the linked account")
    
    form_data = models.JSONField(blank=True, null=True, help_text="Stored form data for offline payments")
    admin_notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.service.name} - {self.amount} - {self.status}"
