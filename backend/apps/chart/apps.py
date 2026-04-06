from django.apps import AppConfig


class ChartConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.chart"
    label = "chart"
    verbose_name = "Chart (market-structure detection)"
