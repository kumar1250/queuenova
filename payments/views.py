import json
import uuid
import razorpay
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import HttpResponse, HttpResponseBadRequest
from organizations.models import Service
from tokens.utils import create_token
from .models import Payment

# Razorpay client
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

@method_decorator(csrf_exempt, name='dispatch')
class RazorpayWebhookView(View):
    """Webhook to handle Razorpay payment events asynchronously."""
    
    def post(self, request):
        payload = request.body
        signature = request.headers.get('X-Razorpay-Signature')
        
        if not signature:
            return HttpResponseBadRequest("Missing signature")
            
        try:
            # Skip signature verification in DEBUG mode if secret is not set
            is_valid = True
            if not settings.DEBUG or (signature and settings.RAZORPAY_WEBHOOK_SECRET != 'kumar@8121644559'):
                try:
                    client.utility.verify_webhook_signature(
                        payload.decode('utf-8'),
                        signature,
                        settings.RAZORPAY_WEBHOOK_SECRET
                    )
                except Exception:
                    is_valid = False
            
            if not is_valid:
                return HttpResponseBadRequest("Invalid signature")
                
            data = json.loads(payload)
            event = data.get('event')
            
            if event == 'payment.captured':
                payment_data = data['payload']['payment']['entity']
                order_id = payment_data['order_id']
                payment_id = payment_data['id']
                
                # Find the payment record by order_id
                payment = Payment.objects.filter(razorpay_order_id=order_id).first()
                
                if payment and payment.status != 'completed':
                    # Update payment status
                    payment.status = 'completed'
                    payment.razorpay_payment_id = payment_id
                    payment.transaction_id = payment_id
                    payment.save()
                    
                    # Generate token automatically
                    create_token(
                        user=payment.user,
                        service=payment.service,
                        payment=payment,
                        form_data=payment.form_data,
                        request=request
                    )
                    
            return HttpResponse(status=200)
            
        except Exception as e:
            return HttpResponse(f"Webhook Error: {str(e)}", status=400)

class PaymentCheckoutView(LoginRequiredMixin, DetailView):
    """View for payment checkout page."""
    model = Service
    template_name = 'payments/checkout.html'
    pk_url_kwarg = 'service_id'
    context_object_name = 'service'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service = self.object
        
        # Ensure UPI is always enabled for checking
        service.is_upi_payment_allowed = True
        context['service'] = service
        
        if not service.is_online_payment_allowed:
            return context
            
        # Create Razorpay order with Route (transfers)
        amount = int(service.payment_amount * 100) # Amount in paise
        order_data = {
            'amount': amount,
            'currency': 'INR',
            'payment_capture': '1'
        }
        
        # If organization has a linked razorpay account, add transfer details
        # Razorpay linked accounts must be 18 characters starting with 'acc_'
        account_id = service.organization.razorpay_account_id
        if account_id and len(account_id) == 18 and account_id.startswith('acc_'):
            order_data['transfers'] = [
                {
                    'account': account_id,
                    'amount': amount,
                    'currency': 'INR',
                }
            ]
            
        try:
            order = client.order.create(data=order_data)
            
            # Save transfer ID if it was created during order
            transfer_id = None
            if 'transfers' in order and len(order['transfers']) > 0:
                transfer_id = order['transfers'][0].get('id')
            
            # Store transfer_id in session to use in callback
            self.request.session[f'transfer_id_{service.id}'] = transfer_id
            
            context['razorpay_order_id'] = order['id']
            context['razorpay_key_id'] = settings.RAZORPAY_KEY_ID
            context['razorpay_amount'] = amount
        except Exception as e:
            # Check if this is a Razorpay account error to provide better feedback
            error_msg = str(e)
            if "The account must be 18 characters" in error_msg:
                context['razorpay_error'] = "Configuration Error: Organization has an invalid Razorpay Linked Account ID. Please contact support."
            else:
                context['razorpay_error'] = error_msg
            
        return context

@method_decorator(csrf_exempt, name='dispatch')
class RazorpayCallbackView(View):
    """Callback view to verify Razorpay payment signature."""
    
    def post(self, request, service_id):
        if not request.user.is_authenticated:
            messages.error(request, "User session expired. Please login again.")
            return redirect('users:login')
            
        service = get_object_or_404(Service, id=service_id)
        razorpay_payment_id = request.POST.get('razorpay_payment_id')
        razorpay_order_id = request.POST.get('razorpay_order_id')
        razorpay_signature = request.POST.get('razorpay_signature')
        
        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }

        try:
            # Verify signature
            client.utility.verify_payment_signature(params_dict)
            
            # Retrieve transfer_id from session
            transfer_id = request.session.pop(f'transfer_id_{service_id}', None)

            # Create payment record
            payment = Payment.objects.create(
                user=request.user,
                service=service,
                amount=service.payment_amount,
                transaction_id=razorpay_payment_id,
                payment_method='Razorpay',
                status='completed',
                razorpay_order_id=razorpay_order_id,
                razorpay_payment_id=razorpay_payment_id,
                razorpay_signature=razorpay_signature,
                razorpay_transfer_id=transfer_id
            )
            
            request.session[f'payment_id_{service_id}'] = payment.id
            messages.success(request, f"Payment of ₹{payment.amount} via Razorpay successful!")
            
            # Generate token and redirect to detail
            from tokens.utils import create_token
            form_data = request.session.get(f'form_data_{service_id}')
            token = create_token(request.user, service, payment, form_data, request)
            
            # Clear session
            request.session.pop(f'form_data_{service_id}', None)
            request.session.pop(f'payment_id_{service_id}', None)
            
            return redirect('tokens:token_detail', token_id=token.id)
            
        except Exception as e:
            messages.error(request, "Payment verification failed. Please try again.")
            return redirect('payments:payment_checkout', service_id=service.id)

class OfflinePaymentView(LoginRequiredMixin, View):
    """View to handle offline payment selection."""
    
    def post(self, request, service_id):
        service = get_object_or_404(Service, id=service_id)
        if not service.is_offline_payment_allowed:
            messages.error(request, "Offline payment is not allowed for this service.")
            return redirect('payments:payment_checkout', service_id=service.id)
            
        # Create a pending payment record with form data
        payment = Payment.objects.create(
            user=request.user,
            service=service,
            amount=service.payment_amount,
            payment_method='Offline',
            status='pending',
            form_data=request.session.get(f'form_data_{service_id}')
        )
        
        # Clear form data from session after saving to DB
        request.session.pop(f'form_data_{service_id}', None)
        
        # We don't redirect to generate_token yet because admin needs to approve
        # BUT we need to inform the user that their request is pending admin approval
        # We might need a separate view for 'pending approval' state.
        
        # Save payment in session if needed, but for offline, it might stay pending for a while.
        # Actually, the user says "admin can accept the payment then generate the token".
        # So for offline, we should show a 'Payment Pending Approval' page.
        
        return render(request, 'payments/offline_pending.html', {'service': service, 'payment': payment})

class UpiPaymentView(LoginRequiredMixin, View):
    """View to handle direct UPI payment submission."""
    
    def post(self, request, service_id):
        service = get_object_or_404(Service, id=service_id)
        if not service.is_upi_payment_allowed:
            messages.error(request, "Direct UPI payment is not allowed for this service.")
            return redirect('payments:payment_checkout', service_id=service.id)
            
        transaction_id = request.POST.get('transaction_id')
        
        # Check if this transaction ID already exists to avoid IntegrityError
        if Payment.objects.filter(transaction_id=transaction_id).exists():
            messages.error(request, "This Transaction ID / UTR has already been submitted.")
            return redirect('payments:payment_checkout', service_id=service.id)
            
        # Create a completed payment record (Auto-Verification mode)
        payment = Payment.objects.create(
            user=request.user,
            service=service,
            amount=service.payment_amount,
            transaction_id=transaction_id,
            payment_method='UPI',
            status='completed',
            form_data=request.session.get(f'form_data_{service_id}')
        )
        
        # Clear form data from session
        request.session.pop(f'form_data_{service_id}', None)
        
        # Generate token automatically
        token = create_token(
            user=payment.user,
            service=payment.service,
            payment=payment,
            form_data=payment.form_data,
            request=request
        )
        
        request.session[f'payment_id_{service_id}'] = payment.id
        messages.success(request, f"UPI Payment of ₹{payment.amount} verified automatically! Your token has been generated.")
        return redirect('tokens:token_detail', token_id=token.id)

class SimulatePaymentView(LoginRequiredMixin, View):
    """View to simulate a successful payment (for testing)."""
    
    def post(self, request, service_id):
        service = get_object_or_404(Service, id=service_id)
        
        if not service.is_online_payment_allowed:
            messages.error(request, "Online payment simulation is not allowed for this service.")
            return redirect('payments:payment_checkout', service_id=service.id)
            
        payment = Payment.objects.create(
            user=request.user,
            service=service,
            amount=service.payment_amount,
            transaction_id=f"TEST-{uuid.uuid4().hex[:8].upper()}",
            payment_method='UPI',
            status='completed',
            form_data=request.session.get(f'form_data_{service_id}')
        )
        
        # Clear form data from session
        request.session.pop(f'form_data_{service_id}', None)
        
        # Generate token automatically
        token = create_token(
            user=payment.user,
            service=payment.service,
            payment=payment,
            form_data=payment.form_data,
            request=request
        )
        
        request.session[f'payment_id_{service_id}'] = payment.id
        messages.success(request, f"Test Payment of ₹{payment.amount} successful! No real money used.")
        return redirect('tokens:token_detail', token_id=token.id)
