from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from django.conf import settings


class CookieJWTAuthentication(JWTAuthentication):
    """Read JWT from httpOnly cookie instead of Authorization header."""

    def authenticate(self, request):
        cookie_name = settings.SIMPLE_JWT.get("AUTH_COOKIE", "access_token")
        raw_token = request.COOKIES.get(cookie_name)

        if raw_token is None:
            # Fall back to header-based for API testing convenience
            return super().authenticate(request)

        try:
            validated_token = self.get_validated_token(raw_token)
        except (TokenError, InvalidToken):
            return None

        return self.get_user(validated_token), validated_token
