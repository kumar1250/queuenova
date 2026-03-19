from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

app_name = 'users'

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('register/admin/', views.AdminRegisterView.as_view(), name='admin_register'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.ProfileUpdateView.as_view(), name='profile_edit'),
    
    # Password Reset (OTP Based)
    path('password-reset/', views.PasswordResetRequestView.as_view(), name='password_reset'),
    path('password-reset/verify/', views.PasswordResetVerifyOTPView.as_view(), name='password_reset_verify'),
    path('password-reset/confirm/', views.PasswordResetSetNewPasswordView.as_view(), name='password_reset_confirm_otp'),
]
