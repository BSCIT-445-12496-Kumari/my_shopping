from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import Product


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'class': 'form-control', 'placeholder': 'Enter your email'
    }))
    first_name = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'First name'
    }))
    last_name = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'Last name'
    }))

    class Meta: #class meta is inner class jo model ko extra configuration/ behavious provide krne ke liye use hota hai 
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Choose a username'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Create password'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirm password'})


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Username'})
        self.fields['password'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Password'})


class ProductForm(forms.ModelForm):
    class Meta:  #class meta is inner class jo model ko extra configuration/ behavious provide krne ke liye use hota hai 
        model = Product
        fields = ['name', 'description', 'price', 'stock', 'category', 'image_url', 'is_available']
        widgets = {
            'name':        forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'price':       forms.NumberInput(attrs={'class': 'form-control'}),
            'stock':       forms.NumberInput(attrs={'class': 'form-control'}),
            'category':    forms.Select(attrs={'class': 'form-select'}),
            'image_url':   forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'is_available':forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }