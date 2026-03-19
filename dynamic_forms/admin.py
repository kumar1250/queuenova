from django.contrib import admin
from .models import FormField

@admin.register(FormField)
class FormFieldAdmin(admin.ModelAdmin):
    list_display = ('label', 'service', 'field_type', 'is_required', 'order')
    list_filter = ('service', 'field_type')
