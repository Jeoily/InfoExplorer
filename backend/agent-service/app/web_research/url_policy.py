"""Pure candidate validation, NOT an SSRF-safe HTTP client.

DNS validation here is useful only when the future downloader pins its actual
connection to a validated IP, keeps TLS hostname verification, and repeats the
policy for every redirect. This module never resolves or downloads a URL.
"""
from dataclasses import dataclass
import ipaddress
import re
from urllib.parse import unquote, urlsplit, urlunsplit

_TRACKING_KEYS = frozenset({"utm_source", "utm_medium", "utm_campaign", "utm_term",
                            "utm_content", "utm_id", "gclid", "fbclid"})
_LOCAL_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home", ".test",
                   ".invalid", ".example", ".onion")
_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")


class UrlRejected(Exception):
    def __init__(self, code: str = "SOURCE_URL_REJECTED"):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class CandidateUrl:
    requested_url: str
    canonical_url: str
    host: str
    port: int


def public_ip(value: str) -> bool:
    """Conservatively reject mapped/tunnel/local/special addresses."""
    try:
        if not isinstance(value, str) or "%" in value:
            return False
        address = ipaddress.ip_address(value)
        if (not address.is_global or address.is_multicast or address.is_reserved
                or address.is_loopback or address.is_link_local or address.is_unspecified):
            return False
        if isinstance(address, ipaddress.IPv6Address):
            if address.ipv4_mapped or address.sixtofour or address.teredo or address.is_site_local:
                return False
            if address in ipaddress.ip_network("64:ff9b::/96"):
                return False
        return True
    except ValueError:
        return False


def validate_resolved_ips(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Reject the whole resolution if ANY answer is unsafe; no socket is opened."""
    if not values or len(values) > 32 or not all(public_ip(value) for value in values):
        raise UrlRejected("SOURCE_ADDRESS_REJECTED")
    return tuple(dict.fromkeys(str(ipaddress.ip_address(value)) for value in values))


def validate_candidate_url(value: str) -> CandidateUrl:
    if (not isinstance(value, str) or not value or len(value) > 2048
            or any(ch.isspace() or ord(ch) < 32 or 127 <= ord(ch) <= 159
                   or 0xD800 <= ord(ch) <= 0xDFFF for ch in value)
            or "\\" in value or re.search(r"%(?![0-9a-fA-F]{2})", value)):
        raise UrlRejected()
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in {"http", "https"} or not parsed.netloc
                or parsed.username is not None or parsed.password is not None
                or not parsed.hostname or "%" in parsed.hostname):
            raise UrlRejected()
        port = 443 if parsed.scheme == "https" else 80
        if parsed.port is not None and parsed.port != port:
            raise UrlRejected()
        if parsed.hostname.endswith(".."):
            raise UrlRejected()
        host = parsed.hostname.removesuffix(".").encode("idna").decode("ascii").lower()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if (len(host) > 253 or "." not in host or host.endswith(_LOCAL_SUFFIXES)
                    or not all(_LABEL.fullmatch(label) for label in host.split("."))
                    or re.fullmatch(r"(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+))*", host)):
                raise UrlRejected()
            canonical_host = host
        else:
            if not public_ip(host):
                raise UrlRejected()
            host = str(address)
            canonical_host = f"[{host}]" if address.version == 6 else host
        # Keep remaining query bytes/order intact: decoding/re-encoding can change
        # signed URLs or application-specific parameter semantics.
        query = "&".join(part for part in parsed.query.split("&")
                         if unquote(part.split("=", 1)[0]).lower() not in _TRACKING_KEYS)
        path = parsed.path or "/"
        requested = urlunsplit((parsed.scheme, canonical_host, path, parsed.query, ""))
        canonical = urlunsplit((parsed.scheme, canonical_host, path, query, ""))
        return CandidateUrl(requested, canonical, host, port)
    except (ValueError, UnicodeError):
        raise UrlRejected() from None
