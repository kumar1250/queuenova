from django.db import models
from django.conf import settings
from django.utils import timezone
from organizations.models import Service
from payments.models import Payment

class Token(models.Model):
    STATUS_CHOICES = (
        ('waiting', 'Waiting'),
        ('near', 'Near'),
        ('serving', 'Serving'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='tokens')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='tokens')
    payment = models.OneToOneField(Payment, on_delete=models.SET_NULL, null=True, blank=True)
    token_number = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        unique_together = ['service', 'token_number', 'date']

    def __str__(self):
        return f"{self.service.name} - {self.token_number} ({self.status})"

class TokenFormData(models.Model):
    token = models.ForeignKey(Token, on_delete=models.CASCADE, related_name='form_data')
    field_label = models.CharField(max_length=255)
    field_value = models.TextField()

    def __str__(self):
        return f"{self.token.token_number} - {self.field_label}: {self.field_value}"

class Notification(models.Model):
    token = models.ForeignKey(Token, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for Token #{self.token.token_number}"
