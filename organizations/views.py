from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Organization, Service

class OrganizationListView(LoginRequiredMixin, ListView):
    """View to list all organizations."""
    model = Organization
    template_name = 'organizations/home.html'
    context_object_name = 'organizations'

class ServiceDetailView(LoginRequiredMixin, DetailView):
    """View to show service details."""
    model = Service
    template_name = 'organizations/service_detail.html'
    pk_url_kwarg = 'service_id'
    context_object_name = 'service'
