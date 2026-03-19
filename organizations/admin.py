from django.contrib import admin
from .models import Organization, Service

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_number', 'upi_id', 'created_at')
    search_fields = ('name', 'upi_id')

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'is_payment_required', 'payment_amount', 'is_online_payment_allowed', 'is_offline_payment_allowed', 'is_upi_payment_allowed')
    list_filter = ('organization', 'is_payment_required', 'is_online_payment_allowed', 'is_offline_payment_allowed', 'is_upi_payment_allowed')
