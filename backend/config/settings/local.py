from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ["*"]

SIMPLE_JWT["AUTH_COOKIE_SECURE"] = False
SIMPLE_JWT["AUTH_COOKIE_SAMESITE"] = "Lax"
