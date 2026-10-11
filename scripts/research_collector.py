#!/usr/bin/env python3
"""AEGIS UWP-13 opt-in public HTTPS snapshot acquisition, NO admission/learning.

Every connection is made to an explicitly validated public IP while TLS verifies
its original hostname. No environment proxies, redirects, credentials, cookies,
subprocesses or writes beyond an explicitly named local output file.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import http.client
import ipaddress
import json
import re
import socket
import ssl
from urllib.parse import urlsplit

MAX_RESPONSE = 131072
MAX_EXCERPT = 16000
TIMEOUT = 8
AGENT = 'AEGIS-UWP-ResearchSnapshot/1.0'
HOST = re.compile(r'^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$')


class CaptureDenied(ValueError):
    pass


def target(url: str, allow_hosts: tuple[str, ...]) -> tuple[str, str]:
    if not isinstance(url, str) or len(url) > 2048 or not url.isascii() or any(c in url for c in '\\\r\n\t\x00'):
        raise CaptureDenied('INVALID_URL')
    try:
        p = urlsplit(url)
        host = p.hostname or ''
        port = p.port
    except ValueError as e:
        raise CaptureDenied('INVALID_URL') from e
    if (p.scheme != 'https' or not p.netloc or p.username is not None or p.password is not None
            or port is not None or p.query or p.fragment or not HOST.fullmatch(host)
            or '..' in host or '.' not in host):
        raise CaptureDenied('INVALID_URL')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass  # Hostnames are looked up only through the validated resolver.
    else:
        raise CaptureDenied('IP_LITERAL_FORBIDDEN')
    if host not in allow_hosts:
        raise CaptureDenied('HOST_NOT_ALLOWED')
    path = p.path or '/'
    if any(ord(c) < 0x20 for c in path):
        raise CaptureDenied('INVALID_URL')
    return host, path


def public_ip_set(host: str, resolver=socket.getaddrinfo) -> tuple[str, ...]:
    try:
        records = resolver(host, 443, type=socket.SOCK_STREAM)
    except (OSError, ValueError) as e:
        raise CaptureDenied('DNS_UNAVAILABLE') from e
    if not records:
        raise CaptureDenied('DNS_EMPTY')
    addresses: set[str] = set()
    for family, socktype, _proto, _canon, addr in records:
        if family not in (socket.AF_INET, socket.AF_INET6) or socktype != socket.SOCK_STREAM:
            raise CaptureDenied('DNS_UNSUPPORTED')
        try:
            ip = ipaddress.ip_address(addr[0])
        except (IndexError, ValueError, TypeError) as e:
            raise CaptureDenied('DNS_INVALID_IP') from e
        if ip.version == 6 and ip.ipv4_mapped is not None:
            raise CaptureDenied('DNS_MAPPED_IP')
        if not ip.is_global:
            raise CaptureDenied('DNS_NONPUBLIC_IP')
        addresses.add(ip.compressed)
    return tuple(sorted(addresses))


class PinnedTLS(http.client.HTTPSConnection):
    def __init__(self, hostname: str, public_ip: str, *, timeout: int = TIMEOUT):
        super().__init__(hostname, port=443, timeout=timeout, context=ssl.create_default_context())
        self.public_ip = public_ip

    def connect(self):
        address = ipaddress.ip_address(self.public_ip)
        family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
        raw = socket.socket(family, socket.SOCK_STREAM)
        raw.settimeout(self.timeout)
        try:
            # Numeric-IP connect; never re-resolve hostname after validation.
            raw.connect((self.public_ip, 443))
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def acquire(url: str, allow_hosts: tuple[str, ...], *, resolver=socket.getaddrinfo,
            connection_factory=PinnedTLS, clock=None) -> dict:
    host, path = target(url, allow_hosts)
    addresses = public_ip_set(host, resolver)
    # Every DNS answer is checked; a single validated public IP is selected.
    # No automatic failover/re-resolution after that choice.
    ip = addresses[0]
    conn = connection_factory(host, ip, timeout=TIMEOUT)
    try:
        conn.connect()
        if conn.sock is None:
            raise CaptureDenied('TLS_UNAVAILABLE')
        peer = conn.sock.getpeercert(binary_form=True)
        if not peer:
            raise CaptureDenied('TLS_NO_CERT')
        # TLS peer certificate digest is evidence of this connection, not publisher identity.
        cert_digest = hashlib.sha256(peer).hexdigest()
        conn.request('GET', path, headers={
            'Accept': 'text/plain, text/html, application/json',
            'Accept-Encoding': 'identity', 'User-Agent': AGENT,
            'Connection': 'close', 'Host': host,
        })
        response = conn.getresponse()
        if response.status != 200:
            # Includes all redirects. No Location header is ever followed.
            raise CaptureDenied('HTTP_NOT_200')
        content_type = (response.getheader('Content-Type') or '').split(';')[0].strip().lower()
        if content_type not in ('text/plain', 'text/html', 'application/json'):
            raise CaptureDenied('UNSUPPORTED_CONTENT_TYPE')
        if (response.getheader('Content-Encoding') or 'identity').lower() != 'identity':
            raise CaptureDenied('ENCODED_CONTENT_FORBIDDEN')
        length = response.getheader('Content-Length')
        if length is not None and (not length.isdigit() or int(length) > MAX_RESPONSE):
            raise CaptureDenied('RESPONSE_TOO_LARGE')
        body = response.read(MAX_RESPONSE + 1)
        if len(body) > MAX_RESPONSE or not body:
            raise CaptureDenied('RESPONSE_TOO_LARGE_OR_EMPTY')
        try:
            text = body.decode('utf-8', errors='strict')
        except UnicodeError as e:
            raise CaptureDenied('NON_UTF8_BODY') from e
        excerpt_bytes = text.encode('utf-8')[:MAX_EXCERPT]
        excerpt = excerpt_bytes.decode('utf-8', errors='ignore')
        now = clock() if clock else dt.datetime.now(dt.timezone.utc)
        if now.tzinfo is None:
            raise CaptureDenied('NAIVE_CLOCK')
        return {
            'schema': 'aegis.research.capture.v1', 'url': url,
            'hostname': host, 'resolved_ip': ip,
            'captured_at': now.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'http_status': 200, 'content_type': content_type,
            'tls_peer_cert_sha256': cert_digest,
            'full_body_sha256': hashlib.sha256(body).hexdigest(),
            'excerpt_sha256': hashlib.sha256(excerpt.encode('utf-8')).hexdigest(),
            'excerpt': excerpt, 'full_bytes': len(body),
            'truncated': len(excerpt.encode('utf-8')) != len(body),
            'publisher_identity': 'NOT_INDEPENDENTLY_AUTHENTICATED',
            'claim_truth': 'NOT_VERIFIED', 'authority_effect': 'NONE',
        }
    except (OSError, ssl.SSLError, http.client.HTTPException) as e:
        raise CaptureDenied('NETWORK_OR_TLS_FAILED') from e
    finally:
        conn.close()


def packet_source(snapshot: dict, source_id: str) -> dict:
    """Produce data accepted by the existing offline scout; no source authentication claim."""
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,63}', source_id):
        raise CaptureDenied('INVALID_SOURCE_ID')
    if snapshot.get('schema') != 'aegis.research.capture.v1' or snapshot.get('authority_effect') != 'NONE':
        raise CaptureDenied('INVALID_CAPTURE')
    value = snapshot.get('excerpt', '')
    if not isinstance(value, str) or not value or len(value) > 20000:
        raise CaptureDenied('INVALID_EXCERPT')
    if hashlib.sha256(value.encode('utf-8')).hexdigest() != snapshot.get('excerpt_sha256'):
        raise CaptureDenied('CAPTURE_TAMPERED')
    return {'id': source_id, 'url': snapshot['url'],
            'captured_at': snapshot['captured_at'],
            'content': value, 'sha256': snapshot['excerpt_sha256'],
            'acquisition': 'connector_capture'}


def main(argv=None):
    a = argparse.ArgumentParser(description='Opt-in bounded HTTPS-only public research capture')
    a.add_argument('url')
    a.add_argument('--allow-host', action='append', required=True)
    a.add_argument('--allow-network', action='store_true', help='explicit opt-in required')
    a.add_argument('--output', help='explicit local output path (else stdout)')
    args = a.parse_args(argv)
    if not args.allow_network:
        a.error('NETWORK_DISABLED: pass --allow-network for explicitly authorized public capture')
    hosts = tuple(args.allow_host)
    if len(hosts) > 8 or any(not isinstance(h, str) or not HOST.fullmatch(h) for h in hosts):
        a.error('INVALID_HOST_ALLOWLIST')
    try:
        result = acquire(args.url, hosts)
    except CaptureDenied as exc:
        a.exit(2, 'DENIED: ' + str(exc) + '\n')
    encoded = json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        with open(args.output, 'x', encoding='utf-8') as f:
            f.write(encoded)
    else:
        print(encoded, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
