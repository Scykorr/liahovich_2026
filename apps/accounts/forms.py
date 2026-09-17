from __future__ import annotations

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from apps.accounts.models import User
from apps.common.forms import apply_bootstrap
from apps.projects.models import ProjectMembership


class LoginForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "Неверное имя пользователя или пароль.",
        "inactive": "Учётная запись отключена.",
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Имя пользователя"
        self.fields["password"].label = "Пароль"
        apply_bootstrap(self)
        self.fields["username"].widget.attrs.update(
            {"autocomplete": "username", "placeholder": "логин"}
        )
        self.fields["password"].widget.attrs.update(
            {"autocomplete": "current-password", "placeholder": "пароль"}
        )


class AnalystUserForm(UserCreationForm):
    role = forms.ChoiceField(choices=User.Role.choices, label="Роль")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name", "role")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        apply_bootstrap(self)


class MembershipForm(forms.ModelForm):
    class Meta:
        model = ProjectMembership
        fields = ("user", "role")
        labels = {"user": "Пользователь", "role": "Роль в проекте"}

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        apply_bootstrap(self)
