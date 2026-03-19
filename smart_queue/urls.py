from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('organizations.urls')),
    path('tokens/', include('tokens.urls')),
    path('payments/', include('payments.urls')),
    path('users/', include('users.urls')),
    path('custom-admin/', include('custom_admin.urls')),
    path('accounts/', include('allauth.urls')),
]

# Serve media files in development AND production (Render has no persistent disk on free tier)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
