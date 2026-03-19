from django import forms
from .models import FormField

def get_dynamic_form_class(service):
    fields = FormField.objects.filter(service=service)
    
    class DynamicForm(forms.Form):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            for field in fields:
                field_kwargs = {
                    'label': field.label,
                    'required': field.is_required,
                    'widget': forms.TextInput(attrs={'class': 'form-control'})
                }
                
                if field.field_type == 'text':
                    self.fields[field.label] = forms.CharField(**field_kwargs)
                elif field.field_type == 'number':
                    self.fields[field.label] = forms.IntegerField(**field_kwargs)
                elif field.field_type == 'email':
                    self.fields[field.label] = forms.EmailField(**field_kwargs)
                elif field.field_type == 'phone':
                    field_kwargs['widget'] = forms.TextInput(attrs={'class': 'form-control', 'type': 'tel'})
                    self.fields[field.label] = forms.CharField(**field_kwargs)
                elif field.field_type == 'textarea':
                    field_kwargs['widget'] = forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
                    self.fields[field.label] = forms.CharField(**field_kwargs)
                elif field.field_type == 'date':
                    field_kwargs['widget'] = forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
                    self.fields[field.label] = forms.DateField(**field_kwargs)
                elif field.field_type == 'time':
                    field_kwargs['widget'] = forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'})
                    self.fields[field.label] = forms.TimeField(**field_kwargs)
                elif field.field_type == 'url':
                    field_kwargs['widget'] = forms.URLInput(attrs={'class': 'form-control', 'type': 'url'})
                    self.fields[field.label] = forms.URLField(**field_kwargs)
                elif field.field_type == 'select':
                    choices = [('', 'Choose an option')]
                    if field.options:
                        choices += [(opt.strip(), opt.strip()) for opt in field.options.split(',')]
                    
                    field_kwargs['choices'] = choices
                    field_kwargs['widget'] = forms.Select(attrs={'class': 'form-select'})
                    self.fields[field.label] = forms.ChoiceField(**field_kwargs)
                elif field.field_type == 'radio':
                    choices = []
                    if field.options:
                        choices = [(opt.strip(), opt.strip()) for opt in field.options.split(',')]
                    
                    field_kwargs['choices'] = choices
                    field_kwargs['widget'] = forms.RadioSelect(attrs={'class': 'form-check-input'})
                    self.fields[field.label] = forms.ChoiceField(**field_kwargs)
                    
    return DynamicForm
