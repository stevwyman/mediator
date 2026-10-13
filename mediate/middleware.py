from django.conf import settings

# Headers a client can spoof unless the connecting peer is the TLS proxy.
_FORWARDED_HEADERS = (
    "HTTP_X_FORWARDED_PROTO",
    "HTTP_X_FORWARDED_HOST",
    "HTTP_X_FORWARDED_PORT",
    "HTTP_X_FORWARDED_FOR",
)


class TrustedProxyMiddleware:
    """Drop forwarded headers when the direct peer is not a configured proxy."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        trusted = set(getattr(settings, "TRUSTED_PROXY_IPS", []))
        if request.META.get("REMOTE_ADDR") not in trusted:
            for header in _FORWARDED_HEADERS:
                request.META.pop(header, None)
        return self.get_response(request)
