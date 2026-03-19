from django.contrib import admin, messages
from .models import Payment
from tokens.utils import create_token
from tokens.models import Token

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'service', 'amount', 'transaction_id', 'payment_method', 'status', 'created_at')
    list_filter = ('status', 'service', 'payment_method')
    search_fields = ('user__email', 'user__full_name', 'transaction_id', 'razorpay_order_id')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['approve_payment']

    @admin.action(description="Approve payment and generate token")
    def approve_payment(self, request, queryset):
        approved_count = 0
        for payment in queryset:
            if payment.status == 'pending' and payment.payment_method in ['Offline', 'UPI']:
                # Check if a token already exists for this payment
                if Token.objects.filter(payment=payment).exists():
                    self.message_user(request, f"Token already exists for payment {payment.id}", messages.WARNING)
                    continue
                    
                # Generate token using stored form data
                create_token(
                    user=payment.user,
                    service=payment.service,
                    payment=payment,
                    form_data=payment.form_data,
                    request=request
                )
                
                # Update payment status
                payment.status = 'completed'
                payment.save()
                approved_count += 1
            else:
                self.message_user(request, f"Payment {payment.id} is not a pending offline/UPI payment.", messages.WARNING)
        
        if approved_count > 0:
            self.message_user(request, f"Successfully approved {approved_count} payments and generated tokens.", messages.SUCCESS)
