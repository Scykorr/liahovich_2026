from django.core.exceptions import ImproperlyConfigured

from config.env import env_bool, env_int, env_list

from .base import *  # noqa: F403

DEBUG = False

if SECRET_KEY in {  # noqa: F405
    None,
    "",
    "change-me-in-production-use-a-long-random-string",
    "insecure-dev-key-change-me",
}:
    raise ImproperlyConfigured("Set a strong DJANGO_SECRET_KEY in production")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", True)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", True)
SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 60)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)

if not CSRF_TRUSTED_ORIGINS:  # noqa: F405
    CSRF_TRUSTED_ORIGINS = env_list(
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        "https://localhost",
    )
