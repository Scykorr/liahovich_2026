from __future__ import annotations

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.forms import AnalystUserForm, LoginForm
from apps.accounts.models import User
from apps.audit.services import log_event


@require_http_methods(["GET", "POST"])
def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("projects:dashboard")
    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        log_event(request.user, "login", request=request)
        return redirect("projects:dashboard")
    return render(request, "accounts/login.html", {"form": form})


@login_required
@require_http_methods(["POST"])
def logout_view(request: HttpRequest) -> HttpResponse:
    log_event(request.user, "logout", request=request)
    logout(request)
    return redirect("accounts:login")


@login_required
@require_http_methods(["GET", "POST"])
def user_list(request: HttpRequest) -> HttpResponse:
    if not request.user.is_system_admin:
        return render(request, "errors/403.html", status=403)
    form = AnalystUserForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user: User = form.save()
        log_event(request.user, "user_create", object_uuid=str(user.pk), request=request, extra={"role": user.role})
        return redirect("accounts:users")
    users = User.objects.order_by("username")
    return render(request, "accounts/users.html", {"form": form, "users": users})


def handler400(request, exception=None):
    return render(request, "errors/400.html", status=400)


def handler403(request, exception=None):
    return render(request, "errors/403.html", status=403)


def handler404(request, exception=None):
    return render(request, "errors/404.html", status=404)


def handler500(request):
    return render(request, "errors/500.html", status=500)
