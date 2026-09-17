from __future__ import annotations

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from apps.accounts.models import User
from apps.projects.models import ProjectMembership


class LoginForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "Неверное имя пользователя или пароль.",
        "inactive": "Учётная запись отключена.",
    }


class AnalystUserForm(UserCreationForm):
    role = forms.ChoiceField(choices=User.Role.choices, label="Роль")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name", "role")


class MembershipForm(forms.ModelForm):
    class Meta:
        model = ProjectMembership
        fields = ("user", "role")
        labels = {"user": "Пользователь", "role": "Роль в проекте"}
