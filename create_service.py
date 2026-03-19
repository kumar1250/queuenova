from organizations.models import Organization, Service
org = Organization.objects.first()
if org:
    service, created = Service.objects.get_or_create(
        organization=org, 
        name='Carhouse Mover', 
        defaults={
            'description': 'Service for moving car houses', 
            'is_payment_required': False, 
            'average_service_time': 30
        }
    )
    print(f'Service created: {created}')
else:
    print('No organization found')
