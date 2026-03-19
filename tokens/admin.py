from django.contrib import admin
from .models import Token, TokenFormData

class TokenFormDataInline(admin.TabularInline):
    model = TokenFormData
    extra = 0

@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ('token_number', 'service', 'status', 'created_at')
    list_filter = ('service', 'status')
    inlines = [TokenFormDataInline]
