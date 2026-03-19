from django.urls import path
from . import views

app_name = 'organizations'

urlpatterns = [
    path('', views.OrganizationListView.as_view(), name='organization_list'),
    path('service/<int:service_id>/', views.ServiceDetailView.as_view(), name='service_detail'),
]
