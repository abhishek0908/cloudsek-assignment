from urllib.parse import urlparse, urlunparse


def normalize_url(raw: str) -> str:
    parsed = urlparse(raw)

    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower()

    if hostname.startswith("www."):
        hostname = hostname.removeprefix("www.")

    port = parsed.port
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    if default_port or port is None:
        netloc = hostname
    else:
        netloc = f"{hostname}:{port}"

    path = parsed.path.rstrip("/") or "/"

    normalized = urlunparse((scheme, netloc, path, "", "", ""))

    return normalized
