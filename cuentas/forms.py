from dataclasses import fields
from pyexpat import model
from django import forms
from cuentas.models import Cuentas, UserPerfil
from urllib.parse import urlparse

class registrarseForm(forms.ModelForm):

    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': 'Ingrese password'
    }))

    confirmar_password = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': 'Confirmar password'
    }))
    class Meta:
        model = Cuentas
        fields = ['nombres', 'apellidos', 'numero_telefono', 'email','password']

    def clean(self):
        cleaned_data = super(registrarseForm, self).clean()
        password = cleaned_data.get('password')
        confirmar_password = cleaned_data.get('confirmar_password')

        if password != confirmar_password:
            raise forms.ValidationError(
                "La contraseña no coiciden"
            )
def _validar_red(url, dominios, nombre):
    """Comprueba que el enlace pertenezca realmente a la red indicada."""
    if not url:
        return url

    host = (urlparse(url).hostname or "").lower()

    if not any(host == d or host.endswith("." + d) for d in dominios):
        raise forms.ValidationError(f"Ingresa un enlace válido de {nombre}.")

    return url

        
class UsuarioPerfilForm (forms.ModelForm):
    image_perfil = forms.ImageField(required=False, error_messages= {'invalid': ('solo archivos de imagen')}, widget=forms.FileInput)
    class Meta:
        model = UserPerfil
        fields = ('direccion_linea_1', 'direccion_linea_2', 'ciudad', 'departamento', 'image_perfil', 'descripcion', 'instagram',
            'tiktok',
            'facebook',)

    widgets = {
            "instagram": forms.URLInput(attrs={"placeholder": "https://www.instagram.com/tu_usuario"}),
            "tiktok": forms.URLInput(attrs={"placeholder": "https://www.tiktok.com/@tu_usuario"}),
            "facebook": forms.URLInput(attrs={"placeholder": "https://www.facebook.com/tu_pagina"}),
        }

    def clean_instagram(self):
        return _validar_red(self.cleaned_data.get("instagram", ""), ["instagram.com"], "Instagram")

    def clean_tiktok(self):
        return _validar_red(self.cleaned_data.get("tiktok", ""), ["tiktok.com"], "TikTok")

    def clean_facebook(self):
        return _validar_red(
            self.cleaned_data.get("facebook", ""),
            ["facebook.com", "fb.com", "fb.me"],
            "Facebook",
        )

    def __init__(self, *args, **kwargs):
        super(UsuarioPerfilForm, self).__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'
    


class UserForm (forms.ModelForm):
    class Meta:
        model = Cuentas
        fields = ('nombres', 'apellidos', 'numero_telefono',) 

    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class']= 'form-control'





