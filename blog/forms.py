from __future__ import annotations

import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm


class AuthorSignupForm(UserCreationForm):
    username = forms.CharField(label="Usuário", max_length=150)
    first_name = forms.CharField(label="Nome", max_length=150)
    last_name = forms.CharField(label="Sobrenome", max_length=150, required=False)
    email = forms.EmailField(label="E-mail")

    cpf = forms.CharField(label="CPF", max_length=14)
    phone = forms.CharField(label="Telefone", max_length=20, required=False)
    instagram = forms.URLField(label="Instagram (link)", required=False)

    avatar = forms.ImageField(label="Foto de perfil", required=False)
    bio = forms.CharField(label="Biografia", required=False, widget=forms.Textarea(attrs={"rows": 5}))

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
            "cpf",
            "phone",
            "instagram",
            "avatar",
            "bio",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        base = {
            "class": "w-full border border-gray-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-4 focus:ring-red-100 focus:border-red-600",
            "autocomplete": "off",
        }

        for name, field in self.fields.items():
            attrs = dict(base)
            if name in {"password1", "password2"}:
                attrs["autocomplete"] = "new-password"
            if name in {"username"}:
                attrs["autocomplete"] = "username"
            if isinstance(field.widget, forms.Textarea):
                attrs["class"] = base["class"] + " resize-none"
            if isinstance(field.widget, forms.ClearableFileInput):
                attrs["class"] = "w-full"

            field.widget.attrs.update(attrs)

        # Labels do UserCreationForm
        self.fields["password1"].label = "Senha"
        self.fields["password2"].label = "Confirmar senha"

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        User = get_user_model()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Já existe uma conta com este e-mail.")
        return email

    def clean_cpf(self):
        cpf = (self.cleaned_data.get("cpf") or "").strip()
        digits = re.sub(r"\D+", "", cpf)
        if len(digits) != 11:
            raise forms.ValidationError("CPF inválido. Informe 11 dígitos.")
        return cpf
