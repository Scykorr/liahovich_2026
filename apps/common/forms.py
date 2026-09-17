from __future__ import annotations

from django import forms


def apply_bootstrap(form: forms.BaseForm) -> None:
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} form-check-input".strip()
            continue
        if isinstance(widget, (forms.Select, forms.SelectMultiple, forms.RadioSelect)):
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} form-select".strip()
            continue
        widget.attrs["class"] = f"{widget.attrs.get('class', '')} form-control".strip()
