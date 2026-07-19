"""Web Push endpoint SSRF safety.

A push subscription's ``endpoint`` originates from an authenticated but
otherwise untrusted client and is later handed verbatim to pywebpush, which
makes an outbound HTTP request to it. A hostile client could register an
internal URL and make the backend connect to it when a push fires. These
helpers are the single source of truth for "is this endpoint safe to send to",
used both at subscribe time (reject the POST) and at send time (skip/prune a
row that predates the validator or was inserted directly).
"""

import ipaddress
import socket
from urllib.parse import urlparse


def _as_ip_literal(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Return the IP a literal host denotes, or None for a genuine hostname.

    Handles the canonical dotted form plus the numeric aliases the C resolver
    accepts (``127.1``, decimal ``2130706433``, hex ``0x7f000001``). Names with
    letters (``fcm.googleapis.com``) raise in inet_aton and fall through to
    None so they're treated as hostnames.
    """
    try:
        return ipaddress.ip_address(host)  # canonical IPv4/IPv6
    except ValueError:
        pass
    try:
        packed = socket.inet_aton(host)  # 127.1 / 2130706433 / 0x7f000001
    except OSError:
        return None
    return ipaddress.ip_address(packed)


# Non-numeric hostnames that resolve to loopback on a default Linux host
# (/etc/hosts). A literal-IP guard alone misses these because they're names,
# not IPs, so an endpoint like https://ip6-localhost/… would otherwise be
# treated as a public host and handed to pywebpush.
_LOCAL_HOST_ALIASES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "localhost6",
        "localhost6.localdomain6",
        "ip6-localhost",
        "ip6-loopback",
    }
)


def is_safe_push_endpoint(endpoint: str) -> bool:
    """Whether ``endpoint`` is a public https URL safe to send a push to.

    Requires https, rejects known loopback host aliases, and for literal-IP
    hosts requires a globally-routable address — ``is_global`` rejects
    loopback/private/link-local/reserved AND the shared CGNAT range
    100.64.0.0/10 (Tailscale et al.), plus multicast/unspecified. Numeric
    aliases (``127.1``, ``2130706433``, ``0x7f000001``) are normalized first,
    and the standard non-numeric loopback names (``localhost``,
    ``ip6-localhost``/``ip6-loopback`` from the default Linux /etc/hosts) are
    rejected by name. (DNS-rebinding of an arbitrary public hostname is out of
    scope for the homelab threat model; real push services are public https.)
    """
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if host in _LOCAL_HOST_ALIASES:
        return False
    ip = _as_ip_literal(host)
    if ip is not None and not ip.is_global:
        return False
    return True
