"""Input validation for anything that reaches the network or the file system.

Hostnames are passed to `openssl s_client` as arguments, so an unchecked value such as
"-proxy evil:8080" would be read as an OpenSSL option. Every host goes through
`validate_host` first: it accepts DNS names (RFC 1123) and IP literals only.
"""

import ipaddress
import re
from urllib.parse import urlsplit

_LABEL = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$")


class InputError(ValueError):
    """User input that cannot be scanned safely."""


def validate_host(raw: str) -> str:
    """Return a normalised hostname / IP, or raise InputError.

    Accepts "example.com", "https://example.com/path" (scheme and path are dropped) and IP literals.
    """
    if not isinstance(raw, str):
        raise InputError("host must be a string")
    text = raw.strip()
    if not text:
        raise InputError("host is empty")
    if "://" in text:
        parts = urlsplit(text)
        if parts.scheme not in ("http", "https"):
            raise InputError(f"unsupported scheme {parts.scheme!r}")
        text = parts.hostname or ""
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    try:
        return str(ipaddress.ip_address(text))
    except ValueError:
        pass
    host = text.rstrip(".").lower()
    if not host or len(host) > 253:
        raise InputError("host length must be 1-253 characters")
    labels = host.split(".")
    if any(not _LABEL.match(label) for label in labels):
        raise InputError(f"invalid hostname {raw!r}")
    if labels[-1].isdigit():
        raise InputError(f"invalid hostname {raw!r}")
    return host


def validate_port(port) -> int:
    try:
        value = int(port)
    except (TypeError, ValueError):
        raise InputError(f"port must be an integer, got {port!r}") from None
    if not 1 <= value <= 65535:
        raise InputError(f"port out of range: {value}")
    return value


def parse_hosts(text: str):
    """Split user text into valid hosts and error messages (one host per line or comma)."""
    hosts, errors = [], []
    for item in re.split(r"[\s,]+", text or ""):
        if not item:
            continue
        try:
            host = validate_host(item)
            if host not in hosts:
                hosts.append(host)
        except InputError as exc:
            errors.append(f"{item}: {exc}")
    return hosts, errors
