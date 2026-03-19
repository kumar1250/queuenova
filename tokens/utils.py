import qrcode
from io import BytesIO
from django.core.files import File
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.db import transaction
from django.utils import timezone
from .models import Token, TokenFormData

def generate_qr_code(data: str) -> BytesIO:
    """Utility to generate QR code as a BytesIO buffer."""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer

def create_token(user, service, payment, form_data, request=None):
    """
    Utility function to create a token, its form data, and QR code.
    Resets token number daily for each service.
    """
    with transaction.atomic():
        # Calculate token number for today
        today = timezone.now().date()
        last_token = Token.objects.select_for_update().filter(
            service=service,
            date=today
        ).order_by('-token_number').first()
        
        token_number = (last_token.token_number + 1) if last_token else 1
        
        token = Token.objects.create(
            user=user,
            service=service,
            payment=payment,
            token_number=token_number,
            date=today,
            status='waiting'
        )
    
    # Generate and save QR Code
    qr_data = f"Token: {token.token_number} | Service: {service.name} | Org: {service.organization.name}"
    qr_buffer = generate_qr_code(qr_data)
    token.qr_code.save(f'token_{token.id}.png', File(qr_buffer), save=True)
    
    # Save dynamic form data
    if form_data:
        for label, value in form_data.items():
            TokenFormData.objects.create(
                token=token,
                field_label=label,
                field_value=str(value)
            )
            
    # Send confirmation email
    if user and user.email:
        try:
            subject = f"Your Token for {token.service.name} - #{token.token_number}"
            url = ""
            if request:
                url = request.build_absolute_uri(reverse('tokens:token_detail', args=[token.id]))
            
            message = (
                f"Hello,\n\nYour token for {token.service.name} at {token.service.organization.name} has been generated.\n"
                f"Token Number: #{token.token_number}\nStatus: Waiting\n\n"
                f"You can track your status here: {url}"
            )
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
        except Exception:
            pass
            
    return token
