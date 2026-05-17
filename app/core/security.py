from urllib.parse import urlparse
import socket
import ipaddress
from app.core.exceptions import SSRFBlockedError

def validate_ssrf(url: str):

    parsed = urlparse(url)

    hostname = parsed.hostname

    ip = socket.gethostbyname(hostname)

    ip_obj = ipaddress.ip_address(ip)

    if (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
    ):
        raise SSRFBlockedError()