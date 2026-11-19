"""Only explicitly trusted immediate proxies may supply the client address."""

from ipaddress import ip_address, ip_network

from django.conf import settings


def client_ip(request):
    try:
        peer = ip_address(request.META.get("REMOTE_ADDR", ""))
    except ValueError:
        return None
    if any(peer in ip_network(value) for value in settings.TRUSTED_PROXY_IPS):
        try:
            # Our Nginx overwrites this single-value header; never parse untrusted XFF.
            return str(ip_address(request.META.get("HTTP_X_REAL_IP", "")))
        except ValueError:
            pass
    return str(peer)
