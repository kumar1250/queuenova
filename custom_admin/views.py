from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView, ListView, View, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib import messages
from django.utils import timezone
from organizations.models import Organization, Service
from tokens.models import Token
from tokens.utils import create_token
from payments.models import Payment
from users.models import User
from users.forms import UserProfileForm
from .forms import OrganizationForm, ServiceForm, FormFieldFormSet

class StaffRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure user is staff."""
    def test_func(self):
        return self.request.user.is_staff

class SuperuserRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure user is superuser."""
    def test_func(self):
        return self.request.user.is_superuser

class AdminDashboardView(StaffRequiredMixin, TemplateView):
    """View for admin dashboard overview."""
    template_name = 'custom_admin/dashboard.html'

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
        # Filter by current admin user and date
        context['org_count'] = Organization.objects.filter(owner=self.request.user).count()
        context['service_count'] = Service.objects.filter(organization__owner=self.request.user).count()
        
        base_tokens = Token.objects.filter(
            service__organization__owner=self.request.user,
            created_at__date=today
        )
        context['total_tokens'] = base_tokens.count()
        context['waiting_tokens'] = base_tokens.filter(status='waiting').count()
        return context

# Organization Views
class ManageOrganizationsView(StaffRequiredMixin, ListView):
    """View to manage all organizations."""
    model = Organization
    template_name = 'custom_admin/organizations.html'
    context_object_name = 'organizations'
    
    def get_queryset(self):
        return Organization.objects.filter(owner=self.request.user)

class CreateOrganizationView(StaffRequiredMixin, CreateView):
    model = Organization
    form_class = OrganizationForm
    template_name = 'custom_admin/org_form.html'
    success_url = reverse_lazy('custom_admin:manage_organizations')
    
    def form_valid(self, form):
        form.instance.owner = self.request.user
        messages.success(self.request, f"Organization '{form.cleaned_data['name']}' created.")
        return super().form_valid(form)

class UpdateOrganizationView(StaffRequiredMixin, UpdateView):
    model = Organization
    form_class = OrganizationForm
    template_name = 'custom_admin/org_form.html'
    success_url = reverse_lazy('custom_admin:manage_organizations')
    
    def get_queryset(self):
        return Organization.objects.filter(owner=self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, f"Organization '{form.cleaned_data['name']}' updated.")
        return super().form_valid(form)

class DeleteOrganizationView(StaffRequiredMixin, DeleteView):
    model = Organization
    template_name = 'custom_admin/org_confirm_delete.html'
    success_url = reverse_lazy('custom_admin:manage_organizations')
    
    def get_queryset(self):
        return Organization.objects.filter(owner=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        messages.success(self.request, f"Organization '{obj.name}' deleted.")
        return super().delete(request, *args, **kwargs)

# Service Views
class ManageServicesView(StaffRequiredMixin, ListView):
    """View to manage all services."""
    model = Service
    template_name = 'custom_admin/services.html'
    context_object_name = 'services'
    
    def get_queryset(self):
        return Service.objects.filter(organization__owner=self.request.user)

class CreateServiceView(StaffRequiredMixin, CreateView):
    model = Service
    form_class = ServiceForm
    template_name = 'custom_admin/service_form.html'
    success_url = reverse_lazy('custom_admin:manage_services')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Limit organizations to those owned by the user
        org_qs = Organization.objects.filter(owner=self.request.user)
        form.fields['organization'].queryset = org_qs
        # Update widget queryset too to ensure our custom widget uses the filtered list
        form.fields['organization'].widget.queryset = org_qs
        return form
    
    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['formset'] = FormFieldFormSet(self.request.POST, self.request.FILES, prefix='fields')
        else:
            data['formset'] = FormFieldFormSet(prefix='fields')
        
        # Add organization offline availability mapping
        orgs = Organization.objects.filter(owner=self.request.user)
        data['offline_availability'] = {org.id: org.is_offline_payment_available for org in orgs}
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        if formset.is_valid():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
            messages.success(self.request, f"Service '{form.cleaned_data['name']}' created.")
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))

class UpdateServiceView(StaffRequiredMixin, UpdateView):
    model = Service
    form_class = ServiceForm
    template_name = 'custom_admin/service_form.html'
    success_url = reverse_lazy('custom_admin:manage_services')
    
    def get_queryset(self):
        return Service.objects.filter(organization__owner=self.request.user)
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Limit organizations to those owned by the user
        org_qs = Organization.objects.filter(owner=self.request.user)
        form.fields['organization'].queryset = org_qs
        # Update widget queryset too to ensure our custom widget uses the filtered list
        form.fields['organization'].widget.queryset = org_qs
        return form
    
    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['formset'] = FormFieldFormSet(self.request.POST, self.request.FILES, instance=self.object, prefix='fields')
        else:
            data['formset'] = FormFieldFormSet(instance=self.object, prefix='fields')
            
        # Add organization offline availability mapping
        orgs = Organization.objects.filter(owner=self.request.user)
        data['offline_availability'] = {org.id: org.is_offline_payment_available for org in orgs}
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        if formset.is_valid():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
            messages.success(self.request, f"Service '{form.cleaned_data['name']}' updated.")
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))

class DeleteServiceView(StaffRequiredMixin, DeleteView):
    model = Service
    template_name = 'custom_admin/service_confirm_delete.html'
    success_url = reverse_lazy('custom_admin:manage_services')
    
    def get_queryset(self):
        return Service.objects.filter(organization__owner=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        messages.success(self.request, f"Service '{obj.name}' deleted.")
        return super().delete(request, *args, **kwargs)

class ServiceToggleView(StaffRequiredMixin, View):
    """View to toggle service active status."""
    
    def get(self, request, service_id):
        service = get_object_or_404(Service, id=service_id, organization__owner=request.user)
        service.is_active = not service.is_active
        service.save()
        messages.success(request, f"Service '{service.name}' updated.")
        return redirect('custom_admin:manage_services')

class ManagePaymentsView(StaffRequiredMixin, ListView):
    """View to manage all payments, especially offline ones."""
    model = Payment
    template_name = 'custom_admin/payments.html'
    context_object_name = 'payments'
    
    def get_queryset(self):
        queryset = Payment.objects.filter(service__organization__owner=self.request.user)
        
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
        return context

class ApprovePaymentView(StaffRequiredMixin, View):
    """View to approve an offline payment and generate a token."""
    
    def post(self, request, payment_id):
        payment = get_object_or_404(Payment, id=payment_id, service__organization__owner=request.user)
        if payment.status == 'pending' and payment.payment_method == 'Offline':
            payment.status = 'completed'
            payment.admin_notes = request.POST.get('admin_notes', '')
            payment.save()
            
            # Generate token
            token = create_token(
                user=payment.user,
                service=payment.service,
                payment=payment,
                form_data=payment.form_data,
                request=request
            )
            
            messages.success(request, f"Payment approved and Token #{token.token_number} generated for {payment.user.username}.")
        else:
            messages.error(request, "This payment cannot be approved.")
            
        return redirect('custom_admin:manage_payments')

class RejectPaymentView(StaffRequiredMixin, View):
    """View to reject an offline payment request."""
    
    def post(self, request, payment_id):
        payment = get_object_or_404(Payment, id=payment_id, service__organization__owner=request.user)
        if payment.status == 'pending' and payment.payment_method == 'Offline':
            payment.status = 'failed'
            payment.admin_notes = request.POST.get('admin_notes', '')
            payment.save()
            messages.warning(request, f"Payment request from {payment.user.username} has been rejected. Reason: {payment.admin_notes}")
        else:
            messages.error(request, "This payment cannot be rejected.")
            
        return redirect('custom_admin:manage_payments')

class UserListView(StaffRequiredMixin, ListView):
    """View to list all users for admin."""
    model = User
    template_name = 'custom_admin/users.html'
    context_object_name = 'users_list'
    paginate_by = 10

    def get_queryset(self):
        return User.objects.all().order_by('-date_joined')

class AdminUserUpdateView(SuperuserRequiredMixin, UpdateView):
    """View for admin to update any user's profile."""
    model = User
    form_class = UserProfileForm
    template_name = 'custom_admin/user_edit.html'
    success_url = reverse_lazy('custom_admin:manage_users')

    def form_valid(self, form):
        messages.success(self.request, f"Profile for {self.object.email} updated.")
        return super().form_valid(form)
