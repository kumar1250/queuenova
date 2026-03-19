from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator

class Organization(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_organizations', null=True, blank=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    address = models.TextField()
    contact_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    razorpay_account_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="Linked Razorpay account ID for transfers (must be 18 characters starting with 'acc_')",
        validators=[RegexValidator(regex='^acc_[a-zA-Z0-9]{14}$', message="Razorpay account ID must be 18 characters starting with 'acc_'")]
    )
    is_offline_payment_available = models.BooleanField(default=False)
    upi_id = models.CharField(max_length=100, blank=True, null=True, help_text="VPA / UPI ID for direct payments")
    upi_qr_code = models.ImageField(upload_to='upi_qrs/', blank=True, null=True, help_text="Static QR code for UPI payments")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Service(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='services')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_payment_required = models.BooleanField(default=False)
    is_online_payment_allowed = models.BooleanField(default=True)
    is_offline_payment_allowed = models.BooleanField(default=False)
    is_upi_payment_allowed = models.BooleanField(default=True, help_text="Allow direct UPI ID/QR payment")
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    average_service_time = models.PositiveIntegerField(default=5, help_text="Average time in minutes per token")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.organization.name} - {self.name}"
