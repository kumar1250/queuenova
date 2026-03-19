from typing import Any
from django.db import models
from django.db.models import Count, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import View, DetailView, ListView, TemplateView, FormView
from django.core.mail import send_mail
from django.conf import settings
from django.core.files import File
from django.urls import reverse
from django.utils import timezone
from io import BytesIO
import qrcode
import csv
from django.http import HttpResponse

from organizations.models import Service
from dynamic_forms.forms import get_dynamic_form_class
from .models import Token, TokenFormData, Notification
from .utils import create_token
from payments.models import Payment

def generate_qr_code(data: str) -> BytesIO:
    """Utility to generate QR code as a BytesIO buffer."""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer

class StaffRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure user is staff."""
    def test_func(self):
        return self.request.user.is_staff

class ServiceFormView(LoginRequiredMixin, View):
    """View to handle dynamic service forms."""
    template_name = 'tokens/service_form.html'

    def get(self, request, service_id):
        service = get_object_or_404(Service, id=service_id)
        if not service.is_active:
            messages.error(request, "This service is currently unavailable.")
            return redirect('organizations:organization_list')
        
        DynamicForm = get_dynamic_form_class(service)
        form = DynamicForm()
        return render(request, self.template_name, {'service': service, 'form': form})

    def post(self, request, service_id):
        service = get_object_or_404(Service, id=service_id)
        DynamicForm = get_dynamic_form_class(service)
        form = DynamicForm(request.POST)
        
        if form.is_valid():
            request.session[f'form_data_{service_id}'] = form.cleaned_data
            if service.is_payment_required:
                return redirect('payments:payment_checkout', service_id=service.id)
            return redirect('tokens:generate_token', service_id=service.id)
            
        return render(request, self.template_name, {'service': service, 'form': form})

class GenerateTokenView(LoginRequiredMixin, View):
    """View to generate a new token after form submission and payment."""
    
    def get(self, request, service_id):
        service = get_object_or_404(Service, id=service_id)
        form_data = request.session.get(f'form_data_{service_id}')
        payment_id = request.session.get(f'payment_id_{service_id}')
        
        if not form_data:
            return redirect('tokens:service_form', service_id=service.id)
            
        payment = None
        if service.is_payment_required:
            if not payment_id:
                messages.error(request, "Payment not verified")
                return redirect('tokens:service_form', service_id=service.id)
            payment = get_object_or_404(Payment, id=payment_id)
            if payment.status != 'completed':
                messages.error(request, "Payment failed or pending")
                return redirect('tokens:service_form', service_id=service.id)

        token = create_token(request.user, service, payment, form_data, request)
            
        # Clear session
        request.session.pop(f'form_data_{service_id}', None)
        request.session.pop(f'payment_id_{service_id}', None)
                
        return redirect('tokens:token_detail', token_id=token.id)

class TokenDetailView(LoginRequiredMixin, DetailView):
    """View to display token details and queue status."""
    model = Token
    template_name = 'tokens/token_detail.html'
    pk_url_kwarg = 'token_id'
    context_object_name = 'token'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        token = self.object
        today = timezone.now().date()
        
        if token.status in ['waiting', 'near']:
            people_ahead = Token.objects.filter(
                service=token.service, 
                status__in=['waiting', 'near'],
                date=today,
                created_at__lt=token.created_at
            ).count()
            
            context['people_ahead'] = people_ahead
            context['current_position'] = people_ahead + 1
            
            # Check if someone is being served for this service
            serving_exists = Token.objects.filter(
                service=token.service,
                status='serving',
                date=today
            ).exists()
            
            wait_intervals = people_ahead + 1 if serving_exists else people_ahead
            context['estimated_wait'] = wait_intervals * token.service.average_service_time
        return context

class QueueDashboardView(StaffRequiredMixin, ListView):
    """Admin dashboard for live queue management."""
    model = Token
    template_name = 'tokens/dashboard.html'
    context_object_name = 'tokens'
    paginate_by = 20

    def get_queryset(self):
        queryset = Token.objects.filter(
            service__organization__owner=self.request.user
        )
        
        selected_date_str = self.request.GET.get('date')
        if selected_date_str:
            try:
                today = timezone.datetime.strptime(selected_date_str, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date=today)
            except ValueError:
                pass
        else:
            # Default to today
            today = timezone.now().date()
            queryset = queryset.filter(created_at__date=today)

        service_id = self.request.GET.get('service_id')
        if service_id:
            queryset = queryset.filter(service_id=service_id)
        
        # Calculate wait info for each token
        today = timezone.now().date()
        for token in queryset:
            if token.status in ['waiting', 'near']:
                people_ahead = Token.objects.filter(
                    service=token.service,
                    status__in=['waiting', 'near'],
                    date=today,
                    created_at__lt=token.created_at
                ).count()
                
                # Check if someone is being served for this service
                serving_exists = Token.objects.filter(
                    service=token.service,
                    status='serving',
                    date=today
                ).exists()
                
                wait_intervals = people_ahead + 1 if serving_exists else people_ahead
                token.people_ahead = people_ahead
                token.estimated_wait = wait_intervals * token.service.average_service_time
            else:
                token.people_ahead = None
                token.estimated_wait = None
                
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        today = timezone.now().date()
        selected_date_str = self.request.GET.get('date')
        if selected_date_str:
            try:
                today = timezone.datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        context['selected_date'] = today
        
        context['services'] = Service.objects.filter(organization__owner=self.request.user)
        selected_service_id = self.request.GET.get('service_id')
        context['selected_service_id'] = int(selected_service_id) if selected_service_id else None
        return context

class UpdateTokenStatusView(StaffRequiredMixin, View):
    """View to update token status by staff."""
    
    def post(self, request, token_id):
        token = get_object_or_404(Token, id=token_id, service__organization__owner=request.user)
        new_status = request.POST.get('status')
        
        if new_status in dict(Token.STATUS_CHOICES):
            old_status = token.status
            token.status = new_status
            token.save()
            
            # Create professional notifications
            msg = f"Your token #{token.token_number} status is now: {new_status.capitalize()}."
            if new_status == 'near':
                msg = f"Please be ready! Your token #{token.token_number} is near. You are next in line."
            elif new_status == 'serving':
                msg = f"It's your turn! Your token #{token.token_number} is now being served at the counter."
            
            Notification.objects.create(
                token=token,
                message=msg
            )
            
            self._send_status_email(token, new_status, msg)
            messages.success(request, f"Token #{token.token_number} status updated to {new_status}")
        
        return redirect(request.META.get('HTTP_REFERER', 'tokens:queue_dashboard'))

    def _send_status_email(self, token, status, custom_msg=None):
        """Helper to send status update email."""
        if token.user:
            try:
                subject = f"Queue Update - Token #{token.token_number} is {status.capitalize()}"
                message = custom_msg if custom_msg else f"Hello,\n\nThe status of your token #{token.token_number} for {token.service.name} has been updated to: {status.capitalize()}."
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [token.user.email], fail_silently=True)
            except Exception:
                pass

class QueueAnalyticsView(StaffRequiredMixin, TemplateView):
    """View for queue analytics and reporting."""
    template_name = 'tokens/analytics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        today = timezone.now().date()
        selected_date_str = self.request.GET.get('date')
        if selected_date_str:
            try:
                today = timezone.datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        context['selected_date'] = today

        base_tokens = Token.objects.filter(
            service__organization__owner=self.request.user,
            created_at__date=today
        )
        
        context['total_tokens'] = base_tokens.count()
        context['completed_tokens'] = base_tokens.filter(status='completed').count()
        context['waiting_tokens'] = base_tokens.filter(status='waiting').count()
        
        # Calculate actual average wait time
        completed_tokens_list = base_tokens.filter(status='completed')
        total_wait = 0
        count = 0
        for t in completed_tokens_list:
            duration = (t.updated_at - t.created_at).total_seconds() / 60
            total_wait += duration
            count += 1
        
        avg_wait_val = round(total_wait / count) if count > 0 else 0
        context['avg_wait'] = f"{avg_wait_val} min"
        
        context['service_stats'] = Service.objects.filter(
            organization__owner=self.request.user
        ).annotate(
            total=Count('tokens', filter=Q(tokens__created_at__date=today)),
            completed=Count('tokens', filter=Q(tokens__status='completed', tokens__created_at__date=today)),
            waiting=Count('tokens', filter=Q(tokens__status='waiting', tokens__created_at__date=today))
        )
        return context

class NotificationListView(LoginRequiredMixin, ListView):
    """View to list notifications for a specific token."""
    model = Notification
    template_name = 'tokens/notifications.html'
    context_object_name = 'notifications'

    def get_queryset(self):
        token_id = self.kwargs.get('token_id')
        token = get_object_or_404(Token, id=token_id)
        queryset = token.notifications.all().order_by('-created_at')
        queryset.update(is_read=True)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['token'] = get_object_or_404(Token, id=self.kwargs.get('token_id'))
        return context

class MyTokensView(LoginRequiredMixin, ListView):
    """View for users to see their tokens and pending payment requests."""
    model = Token
    template_name = 'tokens/my_tokens.html'
    context_object_name = 'tokens'

    def get_queryset(self):
        tokens = Token.objects.filter(user=self.request.user).order_by('-created_at')
        today = timezone.now().date()
        
        for token in tokens:
            if token.status in ['waiting', 'near']:
                # Calculate people ahead for each active token
                people_ahead = Token.objects.filter(
                    service=token.service,
                    status__in=['waiting', 'near'],
                    date=today,
                    created_at__lt=token.created_at
                ).count()
                
                # Check if someone is being served for this service
                serving_exists = Token.objects.filter(
                    service=token.service,
                    status='serving',
                    date=today
                ).exists()
                
                wait_intervals = people_ahead + 1 if serving_exists else people_ahead
                token.people_ahead = people_ahead
                token.estimated_wait = wait_intervals * token.service.average_service_time
            else:
                token.people_ahead = None
                token.estimated_wait = None
        return tokens

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pending_payments'] = Payment.objects.filter(
            user=self.request.user, 
            status='pending',
            payment_method='Offline'
        ).order_by('-created_at')
        return context

class QueueDisplayView(TemplateView):
    """Public view for live queue status display."""
    template_name = 'tokens/display.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        
        # If user is logged in, only show counters they have active tokens for
        if self.request.user.is_authenticated:
            user_services = Token.objects.filter(
                user=self.request.user,
                date=today,
                status__in=['waiting', 'near', 'serving']
            ).values_list('service_id', flat=True).distinct()
            services = Service.objects.filter(id__in=user_services, is_active=True)
        else:
            # For anonymous users, show all active services that have any active tokens
            services = Service.objects.filter(
                is_active=True,
                tokens__date=today,
                tokens__status__in=['waiting', 'near', 'serving']
            ).distinct()
            
        display_data = []
        
        for service in services:
            tokens_today = Token.objects.filter(service=service, created_at__date=today).select_related('user')
            serving = tokens_today.filter(status='serving').order_by('created_at').first()
            near = tokens_today.filter(status='near').order_by('created_at').first()
            waiting_tokens = tokens_today.filter(status='waiting').order_by('created_at')
            
            # All tokens currently in the queue (near + waiting)
            queue_list = list(tokens_today.filter(status__in=['near', 'waiting']).order_by('created_at'))
            
            # Calculate wait time for each token in the queue
            serving_exists = tokens_today.filter(status='serving').exists()
            for idx, token in enumerate(queue_list):
                # If someone is being served, idx 0 waits 1 interval.
                # If NO ONE is being served, idx 0 waits 0 intervals.
                wait_intervals = idx + 1 if serving_exists else idx
                token.expected_wait = wait_intervals * service.average_service_time

            # The 'Next' in display usually means the very next one (Near if exists, else first Waiting)
            next_token = waiting_tokens.first()
            
            # Second in line if no near exists, or first in line if near exists
            if near:
                waiting_after_next = next_token
            else:
                waiting_after_next = waiting_tokens[1] if waiting_tokens.count() > 1 else None

            # Calculate wait for next_token (the one shown in 'Next' slot)
            expected_wait = 0
            # If near exists, near is 'Next'. If not, waiting.first() is 'Next'.
            target_token = near if near else next_token
            
            if target_token:
                ahead_count = tokens_today.filter(
                    status__in=['near', 'waiting'],
                    created_at__lt=target_token.created_at
                ).count()
                
                # If someone is being served, add 1 interval.
                wait_intervals = ahead_count + 1 if serving_exists else ahead_count
                expected_wait = wait_intervals * service.average_service_time
            
            display_data.append({
                'service': service,
                'serving': serving,
                'near': near,
                'next': next_token,
                'waiting_after': waiting_after_next,
                'queue_list': queue_list,
                'expected_wait': expected_wait
            })
        
        context['display_data'] = display_data
        return context

class CancelTokenView(LoginRequiredMixin, View):
    """View to handle token cancellation."""
    
    def post(self, request, token_id):
        token = get_object_or_404(Token, id=token_id, user=request.user)
        if token.status == 'waiting':
            token.status = 'cancelled'
            token.save()
            messages.success(request, f"Token #{token.token_number} has been cancelled.")
        else:
            messages.error(request, "This token cannot be cancelled.")
            
        return redirect('tokens:my_tokens')

class ExportTokenFormDataView(StaffRequiredMixin, View):
    """View to export token form data as CSV."""
    
    def get(self, request, token_id):
        token = get_object_or_404(Token, id=token_id, service__organization__owner=request.user)
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="token_{token.token_number}_data.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Field Label', 'Field Value'])
        
        form_data = token.form_data.all()
        for data in form_data:
            writer.writerow([data.field_label, data.field_value])
            
        return response
