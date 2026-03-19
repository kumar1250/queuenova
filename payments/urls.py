from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('webhook/', views.RazorpayWebhookView.as_view(), name='razorpay_webhook'),
    path('checkout/<int:service_id>/', views.PaymentCheckoutView.as_view(), name='payment_checkout'),
    path('callback/<int:service_id>/', views.RazorpayCallbackView.as_view(), name='razorpay_callback'),
    path('offline/<int:service_id>/', views.OfflinePaymentView.as_view(), name='offline_payment'),
    path('upi/<int:service_id>/', views.UpiPaymentView.as_view(), name='upi_payment'),
    path('simulate/<int:service_id>/', views.SimulatePaymentView.as_view(), name='simulate_payment'),
]
