from .base import *  # noqa: F403

DEBUG = True

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "liahovich-dev",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
