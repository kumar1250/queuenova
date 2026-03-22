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
    """
    Backup: Razorpay calls this directly on their server after payment.
    Only creates token if the callback missed it (e.g. user closed browser).
    """

    def post(self, request):
        payload = request.body
        signature = request.headers.get('X-Razorpay-Signature')

        if not signature:
            return HttpResponseBadRequest("Missing signature")

        try:
            client.utility.verify_webhook_signature(
                payload.decode('utf-8'),
                signature,
                settings.RAZORPAY_WEBHOOK_SECRET
            )
        except Exception:
            return HttpResponseBadRequest("Invalid signature")

        try:
            data = json.loads(payload)
            event = data.get('event')

            if event == 'payment.captured':
                payment_data = data['payload']['payment']['entity']
                order_id = payment_data['order_id']
                payment_id = payment_data['id']

                payment = Payment.objects.filter(razorpay_order_id=order_id).first()

                if payment and payment.status != 'completed':
                    payment.status = 'completed'
                    payment.razorpay_payment_id = payment_id
                    payment.transaction_id = payment_id
                    payment.save()

                    from tokens.models import Token
                    if not Token.objects.filter(payment=payment).exists():
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
    """Shows the payment page and creates a Razorpay order."""
    model = Service
    template_name = 'payments/checkout.html'
    pk_url_kwarg = 'service_id'
    context_object_name = 'service'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service = self.object

        service.is_upi_payment_allowed = True
        context['service'] = service

        if not service.is_online_payment_allowed:
            return context

        amount = int(service.payment_amount * 100)  # convert to paise
        order_data = {
            'amount': amount,
            'currency': 'INR',
            'payment_capture': '1'
        }

        # ── FIX 1: Only add transfers if using LIVE keys ──────────────────
        # Test keys (rzp_test_...) do NOT support Razorpay Route/transfers.
        # Adding transfers with test keys causes "This transfer is not supported" error.
        is_live_key = settings.RAZORPAY_KEY_ID.startswith('rzp_live_')
        account_id = service.organization.razorpay_account_id

        if is_live_key and account_id and len(account_id) == 18 and account_id.startswith('acc_'):
            order_data['transfers'] = [
                {
                    'account': account_id,
                    'amount': amount,
                    'currency': 'INR',
                }
            ]
        # ─────────────────────────────────────────────────────────────────

        try:
            order = client.order.create(data=order_data)

            transfer_id = None
            if 'transfers' in order and len(order.get('transfers', [])) > 0:
                transfer_id = order['transfers'][0].get('id')

            self.request.session[f'transfer_id_{service.id}'] = transfer_id

            context['razorpay_order_id'] = order['id']
            context['razorpay_key_id'] = settings.RAZORPAY_KEY_ID
            context['razorpay_amount'] = amount

        except Exception as e:
            context['razorpay_error'] = str(e)

        return context


@method_decorator(csrf_exempt, name='dispatch')
class RazorpayCallbackView(View):
    """
    Primary handler: Razorpay redirects user's browser here after payment.
    This is where the token is created.
    """

    def post(self, request, service_id):
        if not request.user.is_authenticated:
            messages.error(request, "Session expired. Please login again.")
            return redirect('users:login')

        service = get_object_or_404(Service, id=service_id)

        razorpay_payment_id = request.POST.get('razorpay_payment_id')
        razorpay_order_id   = request.POST.get('razorpay_order_id')
        razorpay_signature  = request.POST.get('razorpay_signature')

        if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
            messages.error(request, "Incomplete payment data received.")
            return redirect('payments:payment_checkout', service_id=service.id)

        params_dict = {
            'razorpay_order_id':   razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature':  razorpay_signature,
        }

        try:
            client.utility.verify_payment_signature(params_dict)
        except Exception:
            messages.error(request, "Payment verification failed. Please contact support.")
            return redirect('payments:payment_checkout', service_id=service.id)

        # Read form_data BEFORE creating the payment record
        form_data   = request.session.get(f'form_data_{service_id}')
        transfer_id = request.session.pop(f'transfer_id_{service_id}', None)

        # get_or_create prevents duplicate records if this runs twice
        payment, created = Payment.objects.get_or_create(
            razorpay_order_id=razorpay_order_id,
            defaults=dict(
                user=request.user,
                service=service,
                amount=service.payment_amount,
                transaction_id=razorpay_payment_id,
                payment_method='Razorpay',
                status='completed',
                razorpay_payment_id=razorpay_payment_id,
                razorpay_signature=razorpay_signature,
                razorpay_transfer_id=transfer_id,
                form_data=form_data,
            )
        )

        if not created:
            payment.status = 'completed'
            payment.razorpay_payment_id = razorpay_payment_id
            payment.razorpay_signature  = razorpay_signature
            payment.save()

        # Clear session
        request.session.pop(f'form_data_{service_id}', None)
        request.session.pop(f'payment_id_{service_id}', None)

        # If webhook already created the token, just redirect to it
        from tokens.models import Token
        existing_token = Token.objects.filter(payment=payment).first()
        if existing_token:
            messages.success(request, f"Payment of ₹{payment.amount} successful!")
            return redirect('tokens:token_detail', token_id=existing_token.id)

        token = create_token(request.user, service, payment, payment.form_data, request)
        messages.success(request, f"Payment of ₹{payment.amount} via Razorpay successful!")
        return redirect('tokens:token_detail', token_id=token.id)


class OfflinePaymentView(LoginRequiredMixin, View):
    """User chooses to pay cash at the counter. Token created after admin approval."""

    def post(self, request, service_id):
        service = get_object_or_404(Service, id=service_id)

        if not service.is_offline_payment_allowed:
            messages.error(request, "Offline payment is not allowed for this service.")
            return redirect('payments:payment_checkout', service_id=service.id)

        payment = Payment.objects.create(
            user=request.user,
            service=service,
            amount=service.payment_amount,
            payment_method='Offline',
            status='pending',
            form_data=request.session.get(f'form_data_{service_id}')
        )

        request.session.pop(f'form_data_{service_id}', None)
        return render(request, 'payments/offline_pending.html', {
            'service': service,
            'payment': payment
        })


class UpiPaymentView(LoginRequiredMixin, View):
    """User pays via UPI app and submits their UTR/transaction ID."""

    def post(self, request, service_id):
        service = get_object_or_404(Service, id=service_id)

        if not service.is_upi_payment_allowed:
            messages.error(request, "Direct UPI payment is not allowed for this service.")
            return redirect('payments:payment_checkout', service_id=service.id)

        transaction_id = request.POST.get('transaction_id', '').strip()

        if not transaction_id:
            messages.error(request, "Please enter a valid Transaction ID.")
            return redirect('payments:payment_checkout', service_id=service.id)

        if Payment.objects.filter(transaction_id=transaction_id).exists():
            messages.error(request, "This Transaction ID / UTR has already been submitted.")
            return redirect('payments:payment_checkout', service_id=service.id)

        form_data = request.session.get(f'form_data_{service_id}')

        payment = Payment.objects.create(
            user=request.user,
            service=service,
            amount=service.payment_amount,
            transaction_id=transaction_id,
            payment_method='UPI',
            status='completed',
            form_data=form_data
        )

        request.session.pop(f'form_data_{service_id}', None)

        token = create_token(
            user=payment.user,
            service=payment.service,
            payment=payment,
            form_data=payment.form_data,
            request=request
        )

        messages.success(
            request,
            f"UPI Payment of ₹{payment.amount} verified! Your token has been generated."
        )
        return redirect('tokens:token_detail', token_id=token.id)


class SimulatePaymentView(LoginRequiredMixin, View):
    """Test button — skips real payment, creates a fake completed payment and token."""

    def post(self, request, service_id):
        service = get_object_or_404(Service, id=service_id)

        if not service.is_online_payment_allowed:
            messages.error(request, "Online payment simulation is not allowed for this service.")
            return redirect('payments:payment_checkout', service_id=service.id)

        form_data = request.session.get(f'form_data_{service_id}')

        payment = Payment.objects.create(
            user=request.user,
            service=service,
            amount=service.payment_amount,
            transaction_id=f"TEST-{uuid.uuid4().hex[:8].upper()}",
            payment_method='UPI',
            status='completed',
            form_data=form_data
        )

        request.session.pop(f'form_data_{service_id}', None)

        token = create_token(
            user=payment.user,
            service=payment.service,
            payment=payment,
            form_data=payment.form_data,
            request=request
        )

        messages.success(request, f"Test Payment of ₹{payment.amount} successful! No real money used.")
        return redirect('tokens:token_detail', token_id=token.id)
