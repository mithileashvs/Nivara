"""Request-scoped context helpers for centralized audit logging.

Uses ContextVars so services deep inside business workflows automatically capture
validated client IP address, User-Agent, and authenticated actor metadata
(strictly resolved via JWT + active DB user check, never client headers).
"""
from __future__ import annotations

import ipaddress
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Sequence

from starlette.requests import Request

if TYPE_CHECKING:
    from app.core.config import Settings

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network

_request_meta_var: ContextVar[dict[str, Any] | None] = ContextVar("nivara_audit_request_meta", default=None)
_actor_meta_var: ContextVar[dict[str, Any] | None] = ContextVar("nivara_audit_actor_meta", default=None)
_in_audit_var: ContextVar[bool] = ContextVar("nivara_inside_audit_log", default=False)

_MAX_FORWARDED_HOPS = 20


def parse_ip_address(raw: str | None) -> IPAddress | None:
    """Safely parse and normalize an IPv4/IPv6 string (optionally with brackets or :port).

    Returns None for empty, oversized, or malformed inputs without raising.
    """
    if not raw:
        return None
    candidate = str(raw).strip().strip('"').strip("'")
    if not candidate or len(candidate) > 128:
        return None

    # Direct IPv4 or IPv6 (with optional zone id)
    try:
        return ipaddress.ip_address(candidate)
    except ValueError:
        pass

    # Bracketed IPv6 with optional port: [2001:db8::1] or [2001:db8::1]:12345
    if candidate.startswith("["):
        end_bracket = candidate.find("]")
        if end_bracket > 1:
            inner = candidate[1:end_bracket]
            rest = candidate[end_bracket + 1 :]
            if rest and not (rest.startswith(":") and rest[1:].isdigit() and 0 <= int(rest[1:]) <= 65535):
                return None
            try:
                return ipaddress.ip_address(inner)
            except ValueError:
                return None
        return None

    # IPv4 with port: 203.0.113.5:54321
    if candidate.count(":") == 1:
        host, port = candidate.rsplit(":", 1)
        if port.isdigit() and 0 <= int(port) <= 65535:
            try:
                return ipaddress.ip_address(host)
            except ValueError:
                return None

    return None


def compile_trusted_proxy_networks(entries: Sequence[str] | None) -> tuple[IPNetwork, ...]:
    """Compile configured IP/CIDR entries into ip_network objects safely."""
    networks: list[IPNetwork] = []
    for item in entries or ():
        cleaned = str(item).strip()
        if not cleaned or cleaned == "*":
            continue
        try:
            networks.append(ipaddress.ip_network(cleaned, strict=False))
        except ValueError:
            continue
    return tuple(networks)


def is_trusted_proxy(socket_ip: IPAddress | None, settings: Settings | None) -> bool:
    """Return True only when proxy header trust is enabled AND socket_ip belongs to trusted_proxy_ips."""
    if socket_ip is None or settings is None:
        return False
    if not getattr(settings, "trust_proxy_headers", False):
        return False
    networks = compile_trusted_proxy_networks(getattr(settings, "trusted_proxy_ips", None))
    if not networks:
        return False
    return any(socket_ip in net for net in networks)


def _ip_in_networks(ip: IPAddress, networks: tuple[IPNetwork, ...]) -> bool:
    return any(ip in net for net in networks)


def resolve_client_ip(
    direct_host: str | None,
    *,
    x_forwarded_for: str | None = None,
    x_real_ip: str | None = None,
    settings: Settings | None = None,
) -> str | None:
    """Resolve canonical client IP for audit telemetry with trusted-proxy verification.

    - Never trusts X-Forwarded-For or X-Real-IP unless settings.trust_proxy_headers is True
      AND the immediate socket peer (direct_host) matches settings.trusted_proxy_ips.
    - When behind trusted proxies, inspects X-Forwarded-For right-to-left skipping known
      trusted proxy hops so spoofed left-side values injected by clients are ignored.
    - Malformed headers are safely ignored without interrupting request handling.
    - Resolved IP is purely observational telemetry and NEVER grants authentication or identity.
    """
    socket_ip = parse_ip_address(direct_host)
    if not is_trusted_proxy(socket_ip, settings):
        return str(socket_ip) if socket_ip is not None else None

    trusted_nets = compile_trusted_proxy_networks(getattr(settings, "trusted_proxy_ips", None))

    if x_forwarded_for:
        parts = [p.strip() for p in x_forwarded_for.split(",") if p.strip()]
        # Inspect right-to-left (capped at last _MAX_FORWARDED_HOPS entries)
        fallback_trusted: IPAddress | None = None
        for token in reversed(parts[-_MAX_FORWARDED_HOPS:]):
            hop_ip = parse_ip_address(token)
            if hop_ip is None:
                continue
            if not _ip_in_networks(hop_ip, trusted_nets):
                return str(hop_ip)
            fallback_trusted = hop_ip
        if fallback_trusted is not None:
            return str(fallback_trusted)

    if x_real_ip:
        real_ip = parse_ip_address(x_real_ip)
        if real_ip is not None:
            return str(real_ip)

    return str(socket_ip) if socket_ip is not None else None


def extract_client_ip(request: Request, settings: Settings | None = None) -> str | None:
    """Extract client IP from Starlette Request using app settings for trusted proxy checks."""
    resolved_settings = settings
    if resolved_settings is None:
        state = getattr(getattr(request, "app", None), "state", None)
        resolved_settings = getattr(state, "settings", None)
    direct_host = request.client.host if request.client and request.client.host else None
    return resolve_client_ip(
        direct_host,
        x_forwarded_for=request.headers.get("x-forwarded-for"),
        x_real_ip=request.headers.get("x-real-ip"),
        settings=resolved_settings,
    )


def extract_user_agent(request: Request) -> str | None:
    ua = request.headers.get("user-agent")
    if not ua:
        return None
    cleaned = ua.strip()
    return cleaned[:500] if cleaned else None


def set_request_meta(meta: dict[str, Any] | None):
    return _request_meta_var.set(meta)


def reset_request_meta(token: Any) -> None:
    _request_meta_var.reset(token)


def get_request_meta() -> dict[str, Any]:
    return dict(_request_meta_var.get() or {})


def set_audit_actor(user_id: str | None, role: str | None):
    if not user_id:
        return _actor_meta_var.set(None)
    return _actor_meta_var.set({"user_id": str(user_id), "role": str(role or "UNKNOWN")})


def clear_audit_actor() -> None:
    _actor_meta_var.set(None)


def get_audit_actor() -> dict[str, Any] | None:
    val = _actor_meta_var.get()
    return dict(val) if val else None


def is_inside_audit() -> bool:
    return bool(_in_audit_var.get())


@contextmanager
def audit_guard():
    """Prevent recursive audit logging if auditing itself triggers an error."""
    token = _in_audit_var.set(True)
    try:
        yield
    finally:
        _in_audit_var.reset(token)
