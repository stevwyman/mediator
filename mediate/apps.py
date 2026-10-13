from django.apps import AppConfig


class MediateConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mediate"

    def ready(self):
        from django.db.backends.signals import connection_created

        connection_created.connect(_sqlite_pragmas)


def _sqlite_pragmas(sender, connection, **kwargs):
    if connection.vendor != "sqlite":
        return
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=5000;")
