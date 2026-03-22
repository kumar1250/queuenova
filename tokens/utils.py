import logging
import qrcode
from io import BytesIO
from django.core.files import File
from django.core.mail import send_mail, EmailMessage
from django.conf import settings
from django.urls import reverse
from django.db import transaction
from django.utils import timezone
from .models import Token, TokenFormData

logger = logging.getLogger(__name__)


def generate_qr_code(data: str) -> BytesIO:
    """Generate a QR code image and return it as a BytesIO buffer."""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


def send_token_email(user, token, request=None):
    """
    Send token confirmation email.
    Returns True on success, False on failure.
    Logs the actual error so you can see it in Render logs.
    """
    if not user or not user.email:
        return False

    # ── FIX 2: fail_silently=True was hiding ALL email errors ────────────
    # Now we catch the exception ourselves and LOG it properly.
    # Go to Render Dashboard → Logs to see exactly what went wrong.
    # ─────────────────────────────────────────────────────────────────────
    try:
        url = ""
        if request:
            url = request.build_absolute_uri(
                reverse('tokens:token_detail', args=[token.id])
            )

        subject = f"Your Token for {token.service.name} - #{token.token_number}"

        message = (
            f"Hello,\n\n"
            f"Your token for {token.service.name} at "
            f"{token.service.organization.name} has been generated.\n\n"
            f"Token Number : #{token.token_number}\n"
            f"Status       : Waiting\n"
            f"Date         : {token.date}\n\n"
            f"Track your status here:\n{url}\n\n"
            f"Thank you,\nQueueNova Team"
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,   # ← raises exception so we can log it
        )
        logger.info(f"Token email sent to {user.email} for token #{token.token_number}")
        return True

    except Exception as e:
        # You will now SEE this error in Render logs
        logger.error(f"Failed to send token email to {user.email}: {str(e)}")
        return False


def create_token(user, service, payment, form_data, request=None):
    """
    Create a token with QR code, save form data, and send confirmation email.
    Token numbers reset daily per service.
    """
    with transaction.atomic():
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

    # Generate and save QR code
    qr_data = (
        f"Token: {token.token_number} | "
        f"Service: {service.name} | "
        f"Org: {service.organization.name}"
    )
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

    # Send confirmation email (errors logged, not silenced)
    send_token_email(user, token, request)

    return token
