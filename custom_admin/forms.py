from django import forms
from organizations.models import Organization, Service
from dynamic_forms.models import FormField
from django.forms import inlineformset_factory

class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ['name', 'description', 'address', 'contact_number', 'email', 'phone', 'razorpay_account_id', 'upi_id', 'upi_qr_code', 'is_offline_payment_available']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter organization name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Brief description'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Physical address'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contact details'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone'}),
            'razorpay_account_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Razorpay Account ID'}),
            'upi_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'VPA / UPI ID (e.g. name@bank)'}),
            'upi_qr_code': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'is_offline_payment_available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class OrganizationSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value:
            try:
                # Handle ModelChoiceIteratorValue for Django 5.0+
                raw_value = value.value if hasattr(value, "value") else value
                
                # Try to convert to int, catch failures
                try:
                    val_id = int(str(raw_value))
                    if hasattr(self, 'queryset') and self.queryset is not None:
                        org = self.queryset.get(pk=val_id)
                        option["attrs"]["data-offline-available"] = "true" if org.is_offline_payment_available else "false"
                except (ValueError, TypeError):
                    pass
            except (Organization.DoesNotExist, AttributeError):
                pass
        return option

class ServiceForm(forms.ModelForm):
    # Additional fields to update organization's UPI info directly from service edit
    upi_id = forms.CharField(
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'VPA / UPI ID (e.g. name@bank)'})
    )
    upi_qr_code = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Service
        fields = ['organization', 'name', 'description', 'is_payment_required', 'is_online_payment_allowed', 'is_offline_payment_allowed', 'is_upi_payment_allowed', 'payment_amount', 'average_service_time', 'is_active']
        widgets = {
            'organization': OrganizationSelect(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Service name (e.g. General OPD)'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'is_payment_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_online_payment_allowed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_offline_payment_allowed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_upi_payment_allowed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'payment_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'average_service_time': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pass the queryset to the custom widget
        self.fields['organization'].widget.queryset = self.fields['organization'].queryset
        
        # Prepopulate UPI ID and QR code from the service's organization
        if self.instance and self.instance.pk and self.instance.organization:
            self.fields['upi_id'].initial = self.instance.organization.upi_id
            self.fields['upi_qr_code'].initial = self.instance.organization.upi_qr_code

    def clean(self):
        cleaned_data = super().clean()
        is_payment_required = cleaned_data.get('is_payment_required')
        is_online_allowed = cleaned_data.get('is_online_payment_allowed')
        is_offline_allowed = cleaned_data.get('is_offline_payment_allowed')
        is_upi_allowed = cleaned_data.get('is_upi_payment_allowed')

        if is_payment_required:
            if not is_online_allowed and not is_offline_allowed and not is_upi_allowed:
                raise forms.ValidationError(
                    "At least one payment method (Online, Offline, or UPI) must be allowed when payment is required."
                )
        else:
            # If payment not required, ensure these are False
            cleaned_data['is_online_payment_allowed'] = False
            cleaned_data['is_offline_payment_allowed'] = False
            cleaned_data['is_upi_payment_allowed'] = False
            cleaned_data['payment_amount'] = 0

        return cleaned_data

    def save(self, commit=True):
        service = super().save(commit=commit)
        if commit:
            # Update organization's UPI details
            org = service.organization
            upi_id = self.cleaned_data.get('upi_id')
            upi_qr_code = self.cleaned_data.get('upi_qr_code')
            
            if upi_id is not None:
                org.upi_id = upi_id
            if upi_qr_code is not None:
                org.upi_qr_code = upi_qr_code
            
            org.save()
        return service

class FormFieldForm(forms.ModelForm):
    class Meta:
        model = FormField
        fields = ['label', 'field_type', 'options', 'is_required', 'order']
        widgets = {
            'label': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Field Label'}),
            'field_type': forms.Select(attrs={'class': 'form-select form-select-sm field-type-input'}),
            'options': forms.TextInput(attrs={'class': 'form-control form-control-sm field-options-input', 'placeholder': 'Option 1, Option 2...'}),
            'is_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
        }

FormFieldFormSet = inlineformset_factory(
    Service, 
    FormField, 
    form=FormFieldForm, 
    extra=1, 
    can_delete=True
)
