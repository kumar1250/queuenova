import logging
import random

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, UpdateView

from .forms import (
    AdminUserCreationForm,
    CustomAuthenticationForm,
    CustomUserCreationForm,
    UserProfileForm,
)
from .models import User, UserOTP

logger = logging.getLogger(__name__)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _clear_reset_session(request):
    """Remove all password-reset keys from the session."""
    request.session.pop('reset_email', None)
    request.session.pop('otp_verified', None)


# ─── Password Reset Flow ──────────────────────────────────────────────────────

class PasswordResetRequestView(View):
    """Step 1 — user enters their email and receives a 6-digit OTP."""

    template_name = 'users/password_reset_form.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        email = request.POST.get('email', '').strip()
        user = User.objects.filter(email=email).first()

        if not user:
            messages.error(request, "No account found with this email.")
            return render(request, self.template_name)

        otp = str(random.randint(100000, 999999))
        UserOTP.objects.update_or_create(user=user, defaults={'otp': otp})

        try:
            send_mail(
                subject='Password Reset OTP',
                message=(
                    f'Your OTP for password reset is: {otp}\n'
                    f'It is valid for 10 minutes.\n\n'
                    f'If you did not request this, please ignore this email.'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
            logger.info("Password-reset OTP sent to %s", user.email)
        except Exception as exc:
            # Log the real error on the server; show a safe message to the user.
            logger.error("Failed to send OTP email to %s: %s", user.email, exc)
            messages.error(request, f"DEBUG EMAIL ERROR: {exc}")
            return render(request, self.template_name)

        request.session['reset_email'] = user.email
        messages.success(request, f"OTP has been sent to {user.email}.")
        return redirect('users:password_reset_verify')


class PasswordResetVerifyOTPView(View):
    """Step 2 — user enters the OTP from their email."""

    template_name = 'users/verify_otp.html'

    def get(self, request):
        if 'reset_email' not in request.session:
            return redirect('users:password_reset')
        return render(request, self.template_name)

    def post(self, request):
        email = request.session.get('reset_email')
        if not email:
            return redirect('users:password_reset')

        user = User.objects.filter(email=email).first()
        if not user:
            messages.error(request, "Session invalid. Please restart the process.")
            _clear_reset_session(request)
            return redirect('users:password_reset')

        otp_input = request.POST.get('otp', '').strip()
        otp_obj = UserOTP.objects.filter(user=user).first()

        if not otp_obj:
            messages.error(request, "No OTP request found. Please request a new one.")
            _clear_reset_session(request)
            return redirect('users:password_reset')

        if otp_obj.otp != otp_input:
            messages.error(request, "Invalid OTP. Please check and try again.")
            return render(request, self.template_name)

        if not otp_obj.is_valid():
            # Delete the stale OTP so a fresh request_otp starts clean
            otp_obj.delete()
            messages.error(
                request,
                "OTP has expired (valid for 10 minutes). Please request a new one.",
            )
            _clear_reset_session(request)
            return redirect('users:password_reset')

        request.session['otp_verified'] = True
        return redirect('users:password_reset_confirm_otp')


class PasswordResetSetNewPasswordView(View):
    """Step 3 — user sets a new password after OTP is verified."""

    template_name = 'users/password_reset_confirm.html'

    def get(self, request):
        if not request.session.get('otp_verified'):
            return redirect('users:password_reset')
        return render(request, self.template_name)

    def post(self, request):
        if not request.session.get('otp_verified'):
            return redirect('users:password_reset')

        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, self.template_name)

        # Run Django's built-in password validators (length, common-password, etc.)
        try:
            validate_password(password)
        except ValidationError as exc:
            for error in exc.messages:
                messages.error(request, error)
            return render(request, self.template_name)

        email = request.session.get('reset_email')
        user = User.objects.filter(email=email).first()

        if not user:
            messages.error(request, "Session expired. Please restart.")
            _clear_reset_session(request)
            return redirect('users:password_reset')

        user.password = make_password(password)
        user.save()

        # Clean up OTP record and session
        UserOTP.objects.filter(user=user).delete()
        _clear_reset_session(request)

        messages.success(request, "Password reset successful. You can now log in.")
        return redirect('users:login')


# ─── Auth ─────────────────────────────────────────────────────────────────────

class CustomLoginView(LoginView):
    """Login with role-based redirect after success."""

    template_name = 'users/login.html'
    authentication_form = CustomAuthenticationForm

    def get_success_url(self):
        user = self.request.user
        if user.is_staff:
            return reverse_lazy('custom_admin:dashboard')
        return reverse_lazy('organizations:organization_list')


# ─── Registration ─────────────────────────────────────────────────────────────

class RegisterView(CreateView):
    """Public user registration."""

    form_class = CustomUserCreationForm
    template_name = 'users/register.html'
    success_url = reverse_lazy('users:login')

    def form_valid(self, form):
        # Single DB write — set is_verified before saving
        user = form.save(commit=False)
        user.is_verified = True
        user.save()
        messages.success(self.request, "Registration successful. You can now log in.")
        return redirect(self.success_url)


class AdminRegisterView(CreateView):
    """Staff (admin/owner) registration."""

    form_class = AdminUserCreationForm
    template_name = 'users/admin_register.html'
    success_url = reverse_lazy('users:login')

    def form_valid(self, form):
        # Single DB write — AdminUserCreationForm.save() already sets is_staff=True
        user = form.save(commit=False)
        user.is_verified = True
        user.save()
        messages.success(self.request, "Admin account created. You can now log in.")
        return redirect(self.success_url)


# ─── Profile ──────────────────────────────────────────────────────────────────

class ProfileView(LoginRequiredMixin, DetailView):
    """Display the logged-in user's profile."""

    model = User
    template_name = 'users/profile.html'
    context_object_name = 'profile_user'

    def get_object(self, queryset=None):
        return self.request.user


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Edit the logged-in user's profile."""

    model = User
    form_class = UserProfileForm
    template_name = 'users/profile_edit.html'
    success_url = reverse_lazy('users:profile')

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Profile updated successfully!")
        return super().form_valid(form)
