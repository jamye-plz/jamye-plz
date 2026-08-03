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


def _normalize_host(host: str) -> str | None:
    """IDNA-normalize a hostname to the ASCII form the resolver will use, or
    None if it can't be normalized.

    ``urlparse`` keeps non-ASCII characters verbatim, but the resolver applies
    IDNA — U+3002 (。), U+FF0E (．) and U+FF61 (｡) all normalize to "." — so
    ``https://127。0。0。1/x`` resolves to loopback while sailing past a literal-IP
    check performed on the raw string. Normalizing first means the guards below
    inspect exactly what Requests will connect to.
    """
    if host.isascii():
        return host
    try:
        return host.encode("idna").decode("ascii")
    except (UnicodeError, ValueError):
        return None


def _is_non_global(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Whether an address must never be connected to.

    ``is_global`` alone is not enough: Python reports is_global == True for
    multicast literals (224.0.0.1, ff02::1) and for reserved IPv6 such as
    fe00::0, so those flags are checked explicitly too.
    """
    return not ip.is_global or ip.is_multicast or ip.is_unspecified or ip.is_reserved


def _resolves_to_global(host: str) -> bool:
    """Whether every A/AAAA record for ``host`` is globally routable.

    A hostname needs no numeric trickery to reach the internal network — an
    attacker can simply publish ``evil.example A 127.0.0.1`` and register it as
    their push endpoint. Resolving here rejects that at subscribe time.
    Unresolvable names are refused too (a real push service always resolves).

    This does NOT close DNS rebinding (a record that flips to a private address
    after this check): defeating that needs the resolved address pinned into
    the socket, which is out of scope for the homelab threat model.
    """
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except OSError:
        return False
    if not infos:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if _is_non_global(ip):
            return False
    return True


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


# Non-numeric hostnames that a default Linux /etc/hosts maps to non-global
# addresses. A literal-IP guard alone misses these because they're names, not
# IPs, so an endpoint like https://ip6-allnodes/… would otherwise be treated as
# a public host and handed to pywebpush.
#   ::1     localhost ip6-localhost ip6-loopback
#   fe00::0 ip6-localnet        (reserved)
#   ff00::0 ip6-mcastprefix     (multicast)
#   ff02::1 ip6-allnodes        (multicast)
#   ff02::2 ip6-allrouters      (multicast)
_NON_GLOBAL_HOST_ALIASES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "localhost6",
        "localhost6.localdomain6",
        "ip6-localhost",
        "ip6-loopback",
        "ip6-localnet",
        "ip6-mcastprefix",
        "ip6-allnodes",
        "ip6-allrouters",
    }
)


def is_safe_push_endpoint(endpoint: str, *, resolve: bool = False) -> bool:
    """Whether ``endpoint`` is a public https URL safe to send a push to.

    Requires https, rejects known loopback host aliases, and for literal-IP
    hosts requires a globally-routable address — ``is_global`` rejects
    loopback/private/link-local/reserved AND the shared CGNAT range
    100.64.0.0/10 (Tailscale et al.), plus multicast/unspecified. Numeric
    aliases (``127.1``, ``2130706433``, ``0x7f000001``) and IDNA forms
    (``127。0。0。1``) are normalized first, and the non-numeric names a default
    Linux /etc/hosts maps to non-global addresses (``localhost``,
    ``ip6-localhost``, ``ip6-allnodes``, …) are rejected by name.

    With ``resolve=True`` a genuine hostname is additionally resolved and
    refused when any A/AAAA record is non-global — this is what stops
    ``evil.example A 127.0.0.1``. It costs a DNS lookup, so callers pass it at
    subscribe time (once per registration) and leave it off on the send path,
    which runs on the event loop for every notification. (DNS rebinding after
    the check remains out of scope for the homelab threat model; blocking it
    requires pinning the resolved address into the socket.)
    """
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    # Normalize to the resolver's view BEFORE any guard, so Unicode dot
    # look-alikes can't smuggle a loopback literal past the checks below.
    normalized = _normalize_host(parsed.hostname)
    if normalized is None:
        return False
    host = normalized.lower()
    if host in _NON_GLOBAL_HOST_ALIASES:
        return False
    ip = _as_ip_literal(host)
    if ip is not None:
        return not _is_non_global(ip)
    # A genuine hostname: optionally verify what it actually resolves to.
    return not resolve or _resolves_to_global(host)
