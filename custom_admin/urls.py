from django.urls import path
from . import views

app_name = 'custom_admin'

urlpatterns = [
    path('dashboard/', views.AdminDashboardView.as_view(), name='dashboard'),
    
    # Organizations
    path('organizations/', views.ManageOrganizationsView.as_view(), name='manage_organizations'),
    path('organizations/add/', views.CreateOrganizationView.as_view(), name='organization_add'),
    path('organizations/<int:pk>/edit/', views.UpdateOrganizationView.as_view(), name='organization_edit'),
    path('organizations/<int:pk>/delete/', views.DeleteOrganizationView.as_view(), name='organization_delete'),
    
    # Services
    path('services/', views.ManageServicesView.as_view(), name='manage_services'),
    path('services/add/', views.CreateServiceView.as_view(), name='service_add'),
    path('services/<int:pk>/edit/', views.UpdateServiceView.as_view(), name='service_edit'),
    path('services/<int:pk>/delete/', views.DeleteServiceView.as_view(), name='service_delete'),
    path('services/toggle/<int:service_id>/', views.ServiceToggleView.as_view(), name='service_toggle'),
    
    # Payments
    path('payments/', views.ManagePaymentsView.as_view(), name='manage_payments'),
    path('payments/approve/<int:payment_id>/', views.ApprovePaymentView.as_view(), name='approve_payment'),
    path('payments/reject/<int:payment_id>/', views.RejectPaymentView.as_view(), name='reject_payment'),
    
    # User Management
    path('users/', views.UserListView.as_view(), name='manage_users'),
    path('users/<int:pk>/edit/', views.AdminUserUpdateView.as_view(), name='user_edit'),
]
