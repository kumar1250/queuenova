from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0010_alter_service_is_upi_payment_allowed'),
    ]

    operations = [
        # Add new base64 field to store image data directly in database
        migrations.AddField(
            model_name='organization',
            name='upi_qr_code_data',
            field=models.TextField(
                blank=True,
                null=True,
                help_text='Base64-encoded UPI QR code image (stored in DB, no disk needed)'
            ),
        ),
        # Remove the old ImageField that required disk storage
        migrations.RemoveField(
            model_name='organization',
            name='upi_qr_code',
        ),
    ]
