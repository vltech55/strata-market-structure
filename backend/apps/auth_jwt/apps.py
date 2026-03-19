from django.apps import AppConfig


class AuthJwtConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.auth_jwt"
    label = "auth_jwt"
    verbose_name = "Auth (JWT RS256)"
