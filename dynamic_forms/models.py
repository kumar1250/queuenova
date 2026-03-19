from django.db import models
from organizations.models import Service

class FormField(models.Model):
    FIELD_TYPES = (
        ('text', 'Text'),
        ('number', 'Number'),
        ('email', 'Email'),
        ('phone', 'Phone Number'),
        ('textarea', 'Textarea'),
        ('select', 'Select Menu'),
        ('radio', 'Radio Buttons'),
        ('date', 'Date Picker'),
        ('time', 'Time Picker'),
        ('url', 'Website URL'),
    )
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='fields')
    label = models.CharField(max_length=255)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES)
    options = models.TextField(blank=True, null=True, help_text="Comma-separated options for Select or Radio fields")
    is_required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.service.name} - {self.label}"
