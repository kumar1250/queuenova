import csv
import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Count, Q, Prefetch
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.generic import View, DetailView, ListView, TemplateView

from organizations.models import Service
from dynamic_forms.forms import get_dynamic_form_class
from payments.models import Payment
from .models import Token, TokenFormData, Notification
from .utils import create_token

logger = logging.getLogger(__name__)


# ─── Mixins ───────────────────────────────────────────────────────────────────

class StaffRequiredMixin(UserPassesTestMixin):
    """Allow access only to staff (organization owners)."""

    def test_func(self):
        return self.request.user.is_staff


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_today():
    return timezone.now().date()


def _parse_date(date_str, fallback=None):
    """Safely parse a YYYY-MM-DD string; return fallback on error."""
    if not date_str:
        return fallback or _get_today()
    try:
        return timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return fallback or _get_today()


def _annotate_queue_position(tokens, today):
    """
    Attach .people_ahead and .estimated_wait to each token in the iterable.

    Does ONE bulk query per service (not one per token) to avoid N+1.
    """
    # Group tokens by service so we can batch the lookups
    service_ids = {t.service_id for t in tokens if t.status in ('waiting', 'near')}

    # Single query: for each service, is anyone currently being served today?
    serving_service_ids = set(
        Token.objects.filter(
            service_id__in=service_ids,
            status='serving',
            date=today,
        ).values_list('service_id', flat=True).distinct()
    )

    for token in tokens:
        if token.status not in ('waiting', 'near'):
            token.people_ahead = None
            token.estimated_wait = None
            continue

        people_ahead = Token.objects.filter(
            service=token.service,
            status__in=('waiting', 'near'),
            date=today,
            created_at__lt=token.created_at,
        ).count()

        serving_exists = token.service_id in serving_service_ids
        wait_intervals = people_ahead + 1 if serving_exists else people_ahead
        token.people_ahead = people_ahead
        token.estimated_wait = wait_intervals * token.service.average_service_time

    return tokens


def _send_status_email(token, status, custom_msg=None):
    """
    Send a status-update email to the token holder.
    Logs success/failure — never silently swallows errors.
    """
    if not token.user or not token.user.email:
        return

    subject = f"Queue Update – Token #{token.token_number} is {status.capitalize()}"
    message = custom_msg or (
        f"Hello,\n\n"
        f"The status of your token #{token.token_number} "
        f"for {token.service.name} has been updated to: {status.capitalize()}.\n\n"
        f"Thank you,\nQueueNova Team"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[token.user.email],
            fail_silently=False,   # raise so we can log the real error
        )
        logger.info(
            "Status email sent to %s for token #%s (status=%s)",
            token.user.email, token.token_number, status,
        )
    except Exception as exc:
        logger.error(
            "Failed to send status email to %s for token #%s: %s",
            token.user.email, token.token_number, exc,
        )


# ─── Public / User Views ──────────────────────────────────────────────────────

class ServiceFormView(LoginRequiredMixin, View):
    """Render and process the dynamic form for a service."""

    template_name = 'tokens/service_form.html'

    def get(self, request, service_id):
        service = get_object_or_404(Service, id=service_id)
        if not service.is_active:
            messages.error(request, "This service is currently unavailable.")
            return redirect('organizations:organization_list')

        form = get_dynamic_form_class(service)()
        return render(request, self.template_name, {'service': service, 'form': form})

    def post(self, request, service_id):
        service = get_object_or_404(Service, id=service_id)
        form = get_dynamic_form_class(service)(request.POST)

        if form.is_valid():
            request.session[f'form_data_{service_id}'] = form.cleaned_data
            if service.is_payment_required:
                return redirect('payments:payment_checkout', service_id=service.id)
            return redirect('tokens:generate_token', service_id=service.id)

        return render(request, self.template_name, {'service': service, 'form': form})


class GenerateTokenView(LoginRequiredMixin, View):
    """Create a token after the form (and optional payment) is complete."""

    def get(self, request, service_id):
        service = get_object_or_404(Service, id=service_id)
        form_data = request.session.get(f'form_data_{service_id}')

        if not form_data:
            return redirect('tokens:service_form', service_id=service.id)

        payment = None
        if service.is_payment_required:
            payment_id = request.session.get(f'payment_id_{service_id}')
            if not payment_id:
                messages.error(request, "Payment not verified.")
                return redirect('tokens:service_form', service_id=service.id)

            payment = get_object_or_404(Payment, id=payment_id)
            if payment.status != 'completed':
                messages.error(request, "Payment failed or still pending.")
                return redirect('tokens:service_form', service_id=service.id)

        token = create_token(request.user, service, payment, form_data, request)

        # Clear session data for this service
        request.session.pop(f'form_data_{service_id}', None)
        request.session.pop(f'payment_id_{service_id}', None)

        return redirect('tokens:token_detail', token_id=token.id)


class TokenDetailView(LoginRequiredMixin, DetailView):
    """Display a single token with live queue position."""

    model = Token
    template_name = 'tokens/token_detail.html'
    pk_url_kwarg = 'token_id'
    context_object_name = 'token'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        token = self.object
        today = _get_today()

        if token.status in ('waiting', 'near'):
            people_ahead = Token.objects.filter(
                service=token.service,
                status__in=('waiting', 'near'),
                date=today,
                created_at__lt=token.created_at,
            ).count()

            serving_exists = Token.objects.filter(
                service=token.service,
                status='serving',
                date=today,
            ).exists()

            wait_intervals = people_ahead + 1 if serving_exists else people_ahead
            context['people_ahead'] = people_ahead
            context['current_position'] = people_ahead + 1
            context['estimated_wait'] = wait_intervals * token.service.average_service_time

        return context


class MyTokensView(LoginRequiredMixin, ListView):
    """List all tokens belonging to the logged-in user."""

    model = Token
    template_name = 'tokens/my_tokens.html'
    context_object_name = 'tokens'

    def get_queryset(self):
        today = _get_today()
        tokens = list(
            Token.objects.filter(user=self.request.user)
            .select_related('service', 'service__organization')
            .order_by('-created_at')
        )
        return _annotate_queue_position(tokens, today)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pending_payments'] = Payment.objects.filter(
            user=self.request.user,
            status='pending',
            payment_method='Offline',
        ).order_by('-created_at')
        return context


class CancelTokenView(LoginRequiredMixin, View):
    """Allow a user to cancel their own waiting token."""

    def post(self, request, token_id):
        token = get_object_or_404(Token, id=token_id, user=request.user)

        if token.status == 'waiting':
            token.status = 'cancelled'
            token.save()
            messages.success(request, f"Token #{token.token_number} has been cancelled.")
        else:
            messages.error(request, "Only waiting tokens can be cancelled.")

        return redirect('tokens:my_tokens')


class NotificationListView(LoginRequiredMixin, ListView):
    """Show all notifications for a specific token and mark them read."""

    model = Notification
    template_name = 'tokens/notifications.html'
    context_object_name = 'notifications'

    def get_queryset(self):
        token = get_object_or_404(Token, id=self.kwargs['token_id'])
        qs = token.notifications.all().order_by('-created_at')
        qs.update(is_read=True)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['token'] = get_object_or_404(Token, id=self.kwargs['token_id'])
        return context


class QueueDisplayView(TemplateView):
    """
    Public board showing live queue status per service.
    Authenticated users only see services they have active tokens for.
    """

    template_name = 'tokens/display.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = _get_today()

        if self.request.user.is_authenticated:
            active_service_ids = Token.objects.filter(
                user=self.request.user,
                date=today,
                status__in=('waiting', 'near', 'serving'),
            ).values_list('service_id', flat=True).distinct()

            services = Service.objects.filter(
                id__in=active_service_ids, is_active=True
            )
        else:
            services = Service.objects.filter(
                is_active=True,
                tokens__date=today,
                tokens__status__in=('waiting', 'near', 'serving'),
            ).distinct()

        display_data = []

        for service in services:
            tokens_today = (
                Token.objects.filter(service=service, date=today)
                .select_related('user')
            )

            serving = tokens_today.filter(status='serving').order_by('created_at').first()
            near = tokens_today.filter(status='near').order_by('created_at').first()
            waiting_qs = tokens_today.filter(status='waiting').order_by('created_at')

            # Build the live queue list (near + waiting in order)
            queue_list = list(
                tokens_today.filter(status__in=('near', 'waiting')).order_by('created_at')
            )

            # Attach expected wait to every queued token in one pass
            serving_exists = serving is not None
            for idx, t in enumerate(queue_list):
                wait_intervals = idx + 1 if serving_exists else idx
                t.expected_wait = wait_intervals * service.average_service_time

            # "Next" slot: near token if one exists, else first waiting
            next_token = near or waiting_qs.first()

            # "After next" slot
            if near:
                after_next = waiting_qs.first()
            else:
                after_next = waiting_qs[1] if waiting_qs.count() > 1 else None

            # Expected wait for the next_token shown on the board
            expected_wait = 0
            if next_token:
                # next_token is at position 0 in queue_list if near, else 0 too
                # Just look it up from the annotated list
                match = next((t for t in queue_list if t.pk == next_token.pk), None)
                expected_wait = match.expected_wait if match else 0

            display_data.append({
                'service': service,
                'serving': serving,
                'near': near,
                'next': next_token,
                'waiting_after': after_next,
                'queue_list': queue_list,
                'expected_wait': expected_wait,
            })

        context['display_data'] = display_data
        return context


# ─── Staff / Dashboard Views ──────────────────────────────────────────────────

class QueueDashboardView(StaffRequiredMixin, ListView):
    """Live queue management dashboard for staff."""

    model = Token
    template_name = 'tokens/dashboard.html'
    context_object_name = 'tokens'
    paginate_by = 20

    def _get_filters(self):
        date_str = self.request.GET.get('date')
        service_id = self.request.GET.get('service_id')
        return _parse_date(date_str), service_id

    def get_queryset(self):
        today, service_id = self._get_filters()

        qs = (
            Token.objects.filter(service__organization__owner=self.request.user)
            .select_related('service', 'service__organization', 'user')
            .filter(date=today)          # use token.date (the canonical date field)
        )

        if service_id:
            qs = qs.filter(service_id=service_id)

        tokens = list(qs.order_by('-created_at'))
        return _annotate_queue_position(tokens, today)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today, service_id = self._get_filters()
        context['selected_date'] = today
        context['services'] = Service.objects.filter(
            organization__owner=self.request.user
        )
        context['selected_service_id'] = int(service_id) if service_id else None
        return context


class UpdateTokenStatusView(StaffRequiredMixin, View):
    """Staff view to change a token's status and notify the user."""

    # Maps status → notification message
    STATUS_MESSAGES = {
        'near': "Please be ready! Your token #{num} is near. You are next in line.",
        'serving': "It's your turn! Your token #{num} is now being served at the counter.",
    }

    def post(self, request, token_id):
        token = get_object_or_404(
            Token, id=token_id, service__organization__owner=request.user
        )
        new_status = request.POST.get('status')

        if new_status not in dict(Token.STATUS_CHOICES):
            messages.error(request, "Invalid status.")
            return redirect(request.META.get('HTTP_REFERER', 'tokens:queue_dashboard'))

        token.status = new_status
        token.save()

        # Build notification message
        template = self.STATUS_MESSAGES.get(
            new_status,
            "Your token #{num} status is now: " + new_status.capitalize() + ".",
        )
        msg = template.format(num=token.token_number)

        Notification.objects.create(token=token, message=msg)
        _send_status_email(token, new_status, msg)

        messages.success(
            request,
            f"Token #{token.token_number} updated to {new_status}.",
        )
        return redirect(request.META.get('HTTP_REFERER', 'tokens:queue_dashboard'))


class QueueAnalyticsView(StaffRequiredMixin, TemplateView):
    """Analytics / reporting view for the queue owner."""

    template_name = 'tokens/analytics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = _parse_date(self.request.GET.get('date'))
        context['selected_date'] = today

        base_qs = Token.objects.filter(
            service__organization__owner=self.request.user,
            date=today,
        )

        context['total_tokens'] = base_qs.count()
        context['completed_tokens'] = base_qs.filter(status='completed').count()
        context['waiting_tokens'] = base_qs.filter(status='waiting').count()

        # Average wait time across completed tokens
        completed = base_qs.filter(status='completed')
        durations = [
            (t.updated_at - t.created_at).total_seconds() / 60
            for t in completed
        ]
        avg = round(sum(durations) / len(durations)) if durations else 0
        context['avg_wait'] = f"{avg} min"

        context['service_stats'] = (
            Service.objects.filter(organization__owner=self.request.user)
            .annotate(
                total=Count('tokens', filter=Q(tokens__date=today)),
                completed=Count(
                    'tokens',
                    filter=Q(tokens__status='completed', tokens__date=today),
                ),
                waiting=Count(
                    'tokens',
                    filter=Q(tokens__status='waiting', tokens__date=today),
                ),
            )
        )
        return context


# ─── Export ───────────────────────────────────────────────────────────────────

class ExportTokenFormDataView(StaffRequiredMixin, View):
    """Download all dynamic-form answers for a token as CSV."""

    def get(self, request, token_id):
        token = get_object_or_404(
            Token, id=token_id, service__organization__owner=request.user
        )

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = (
            f'attachment; filename="token_{token.token_number}_data.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(['Field Label', 'Field Value'])
        for entry in token.form_data.all():
            writer.writerow([entry.field_label, entry.field_value])

        return response
