from django.apps import AppConfig


class StockConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.stock"
    label = "stock"
    verbose_name = "Stock (symbols & OHLCV)"
