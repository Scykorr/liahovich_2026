from __future__ import annotations

from django import forms

from apps.common.forms import apply_bootstrap
from apps.projects.models import Project, ProjectMembership


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ("name", "description")
        labels = {"name": "Название", "description": "Описание"}
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        apply_bootstrap(self)


class MembershipForm(forms.ModelForm):
    class Meta:
        model = ProjectMembership
        fields = ("user", "role")
        labels = {"user": "Пользователь", "role": "Роль"}

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        apply_bootstrap(self)
