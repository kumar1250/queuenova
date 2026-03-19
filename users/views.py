from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import CreateView, DetailView, UpdateView
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.conf import settings
import random
from .forms import CustomUserCreationForm, AdminUserCreationForm, CustomAuthenticationForm, UserProfileForm
from .models import User, UserOTP

class PasswordResetRequestView(View):
    def get(self, request):
        return render(request, 'users/password_reset_form.html')

    def post(self, request):
        email = request.POST.get('email', '').strip()
        user = User.objects.filter(email=email).first()
        if user:
            otp = str(random.randint(100000, 999999))
            UserOTP.objects.update_or_create(user=user, defaults={'otp': otp})
            
            try:
                send_mail(
                    'Password Reset OTP',
                    f'Your OTP for password reset is: {otp}. It is valid for 10 minutes.',
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False,
                )
                request.session['reset_email'] = user.email
                messages.success(request, f"OTP has been sent to {user.email}.")
                return redirect('users:password_reset_verify')
            except Exception as e:
                messages.error(request, f"Failed to send email: {str(e)}")
        else:
            messages.error(request, "No account found with this email.")
        return render(request, 'users/password_reset_form.html')

class PasswordResetVerifyOTPView(View):
    def get(self, request):
        if 'reset_email' not in request.session:
            return redirect('users:password_reset')
        return render(request, 'users/verify_otp.html')

    def post(self, request):
        email = request.session.get('reset_email')
        otp_input = request.POST.get('otp', '').strip()
        
        if not email:
            return redirect('users:password_reset')
            
        user = User.objects.filter(email=email).first()
        if not user:
            messages.error(request, "User session invalid. Please restart the process.")
            return redirect('users:password_reset')
            
        otp_obj = UserOTP.objects.filter(user=user).first()
        
        if otp_obj:
            if otp_obj.otp == otp_input:
                if otp_obj.is_valid():
                    request.session['otp_verified'] = True
                    return redirect('users:password_reset_confirm_otp')
                else:
                    messages.error(request, "OTP has expired (valid for 10 mins). Please request a new one.")
            else:
                messages.error(request, "Invalid OTP. Please check and try again.")
        else:
            messages.error(request, "No OTP request found for this email.")
            
        return render(request, 'users/verify_otp.html')

class PasswordResetSetNewPasswordView(View):
    def get(self, request):
        if not request.session.get('otp_verified'):
            return redirect('users:password_reset')
        return render(request, 'users/password_reset_confirm.html')

    def post(self, request):
        if not request.session.get('otp_verified'):
            return redirect('users:password_reset')
        
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'users/password_reset_confirm.html')
        
        email = request.session.get('reset_email')
        user = User.objects.filter(email=email).first()
        if user:
            user.password = make_password(password)
            user.save()
            user.otp.delete()
            del request.session['reset_email']
            del request.session['otp_verified']
            messages.success(request, "Password reset successful. You can now login.")
            return redirect('users:login')
        
        return redirect('users:password_reset')

class CustomLoginView(LoginView):
    """View for user login with role-based redirection."""
    template_name = 'users/login.html'
    authentication_form = CustomAuthenticationForm

    def get_success_url(self):
        """Redirect based on user role."""
        user = self.request.user
        if user.is_staff:
            return reverse_lazy('custom_admin:dashboard')
        return reverse_lazy('organizations:organization_list')

class RegisterView(CreateView):
    """View for user registration."""
    form_class = CustomUserCreationForm
    template_name = 'users/register.html'
    success_url = reverse_lazy('users:login')

    def form_valid(self, form):
        user = form.save()
        user.is_verified = True
        user.save()
        messages.success(self.request, f"Registration successful. You can now login.")
        return redirect(self.success_url)

class AdminRegisterView(CreateView):
    """View for admin (staff) registration."""
    form_class = AdminUserCreationForm
    template_name = 'users/admin_register.html'
    success_url = reverse_lazy('users:login')

    def form_valid(self, form):
        user = form.save()
        user.is_verified = True
        user.save()
        messages.success(self.request, f"Admin account created. You can now login.")
        return redirect(self.success_url)

class ProfileView(LoginRequiredMixin, DetailView):
    model = User
    template_name = 'users/profile.html'
    context_object_name = 'profile_user'

    def get_object(self, queryset=None):
        return self.request.user

class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserProfileForm
    template_name = 'users/profile_edit.html'
    success_url = reverse_lazy('users:profile')

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Profile updated successfully!")
        return super().form_valid(form)
