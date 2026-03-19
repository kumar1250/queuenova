from django.urls import path
from . import views

app_name = 'tokens'

urlpatterns = [
    path('service/<int:service_id>/', views.ServiceFormView.as_view(), name='service_form'),
    path('generate/<int:service_id>/', views.GenerateTokenView.as_view(), name='generate_token'),
    path('detail/<int:token_id>/', views.TokenDetailView.as_view(), name='token_detail'),
    path('dashboard/', views.QueueDashboardView.as_view(), name='queue_dashboard'),
    path('update-status/<int:token_id>/', views.UpdateTokenStatusView.as_view(), name='update_token_status'),
    path('analytics/', views.QueueAnalyticsView.as_view(), name='queue_analytics'),
    path('notifications/<int:token_id>/', views.NotificationListView.as_view(), name='notification_list'),
    path('display/', views.QueueDisplayView.as_view(), name='queue_display'),
    path('cancel/<int:token_id>/', views.CancelTokenView.as_view(), name='cancel_token'),
    path('my-tokens/', views.MyTokensView.as_view(), name='my_tokens'),
    path('export-data/<int:token_id>/', views.ExportTokenFormDataView.as_view(), name='export_token_data'),
]
