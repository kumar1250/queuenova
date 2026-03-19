#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# Fix site domain for allauth
python manage.py shell -c "
from django.contrib.sites.models import Site
Site.objects.update_or_create(id=2, defaults={'domain': 'queuenova.onrender.com', 'name': 'QueueNova'})
print('Site configured successfully')
"

# Create superuser if not exists
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser(email='admin@queuenova.com', password='Admin@1234')
    print('Superuser created: admin@queuenova.com / Admin@1234')
else:
    print('Superuser already exists')
"
