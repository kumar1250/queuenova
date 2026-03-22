from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator


class Organization(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_organizations',
        null=True, blank=True
    )
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
        validators=[RegexValidator(
            regex='^acc_[a-zA-Z0-9]{14}$',
            message="Razorpay account ID must be 18 characters starting with 'acc_'"
        )]
    )
    is_offline_payment_available = models.BooleanField(default=False)
    upi_id = models.CharField(
        max_length=100, blank=True, null=True,
        help_text="VPA / UPI ID for direct payments"
    )

    # ── Stores image as base64 text directly in the database ──────────────
    # This replaces the old ImageField (upi_qr_code) which required disk
    # storage. Render free tier has NO persistent disk — files uploaded via
    # ImageField disappear on every restart/redeploy. Storing as base64 in
    # the database means the image is permanent, just like any other field.
    upi_qr_code_data = models.TextField(
        blank=True,
        null=True,
        help_text="UPI QR code image (stored as base64 in database — no disk needed)"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Service(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='services'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_payment_required = models.BooleanField(default=False)
    is_online_payment_allowed = models.BooleanField(default=True)
    is_offline_payment_allowed = models.BooleanField(default=False)
    is_upi_payment_allowed = models.BooleanField(
        default=True,
        help_text="Allow direct UPI ID/QR payment"
    )
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    average_service_time = models.PositiveIntegerField(
        default=5, help_text="Average time in minutes per token"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.organization.name} - {self.name}"
