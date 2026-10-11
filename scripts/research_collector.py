#!/usr/bin/env python3
"""AEGIS UWP-13 opt-in public HTTPS snapshot acquisition, NO admission/learning.

Every connection is made to an explicitly validated public IP while TLS verifies
its original hostname. No inherited proxies, redirects, cookies or implicit
authentication. The opt-in CLI uses a supervised subprocess; direct acquire()
has no end-to-end deadline. The publishing parent re-verifies any capture MAC.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import socket
import ssl
from urllib.parse import urlsplit

from research_attestation import sign_capture, verify_capture, read_protected_key, AttestationError, _validate_key, _binding

MAX_RESPONSE = 131072
MAX_EXCERPT = 16000
TIMEOUT = 8
DEFAULT_TOTAL_DEADLINE_SECONDS = 20
MAX_TOTAL_DEADLINE_SECONDS = 120
MAX_WORKER_STDOUT = 100000
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
            connection_factory=PinnedTLS, clock=None,
            signing_key: bytes | None = None, signing_key_id: str | None = None,
            capture_binding: dict | None = None) -> dict:
    # Admission fails before DNS or network I/O for a malformed signing context.
    if signing_key is not None:
        _validate_key(signing_key, signing_key_id)
        _binding(capture_binding)
    elif signing_key_id is not None or capture_binding is not None:
        raise CaptureDenied('SIGNING_KEY_REQUIRED')
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
        # HTTP/1.1 has different framing for declared-length, chunked and
        # connection-close bodies. Never sign bytes from an incomplete or
        # ambiguous framing as if they were the full server response.
        length = response.getheader('Content-Length')
        transfer = (response.getheader('Transfer-Encoding') or '').strip().lower()
        if length is not None and transfer:
            raise CaptureDenied('AMBIGUOUS_TRANSFER_FRAMING')
        if transfer and transfer != 'chunked':
            raise CaptureDenied('UNSUPPORTED_TRANSFER_ENCODING')
        # http.client parses/dechunks framing; don't accept a claimed chunked
        # body through a transport that has not actually enabled decoding.
        if bool(getattr(response, 'chunked', False)) != (transfer == 'chunked'):
            raise CaptureDenied('TRANSFER_FRAMING_MISMATCH')
        if length is not None and (not length.isdigit() or int(length) > MAX_RESPONSE):
            raise CaptureDenied('RESPONSE_TOO_LARGE')
        body = response.read(MAX_RESPONSE + 1)
        if len(body) > MAX_RESPONSE or not body:
            raise CaptureDenied('RESPONSE_TOO_LARGE_OR_EMPTY')
        if length is not None and len(body) != int(length):
            if len(body) < int(length):
                raise CaptureDenied('INCOMPLETE_RESPONSE_BODY')
            raise CaptureDenied('CONTENT_LENGTH_MISMATCH')
        try:
            text = body.decode('utf-8', errors='strict')
        except UnicodeError as e:
            raise CaptureDenied('NON_UTF8_BODY') from e
        excerpt_bytes = text.encode('utf-8')[:MAX_EXCERPT]
        excerpt = excerpt_bytes.decode('utf-8', errors='ignore')
        now = clock() if clock else dt.datetime.now(dt.timezone.utc)
        if now.tzinfo is None:
            raise CaptureDenied('NAIVE_CLOCK')
        snapshot = {
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
        if signing_key is not None:
            return sign_capture(snapshot, signing_key, signing_key_id,
                                binding=capture_binding)
        if signing_key_id is not None or capture_binding is not None:
            raise CaptureDenied('SIGNING_KEY_REQUIRED')
        return snapshot
    except (OSError, ssl.SSLError, http.client.HTTPException) as e:
        raise CaptureDenied('NETWORK_OR_TLS_FAILED') from e
    finally:
        conn.close()


def packet_source(snapshot: dict, source_id: str) -> dict:
    """Convert coherent capture metadata to offline-scout input.

    Local coherence does NOT prove publisher authenticity. A malicious caller can
    fabricate a complete, self-consistent capture; signed collector attestations
    and independent publisher verification remain separate admission gates.
    """
    if not isinstance(source_id, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,63}', source_id):
        raise CaptureDenied('INVALID_SOURCE_ID')
    if type(snapshot) is not dict or snapshot.get('schema') != 'aegis.research.capture.v1' or snapshot.get('authority_effect') != 'NONE':
        raise CaptureDenied('INVALID_CAPTURE')

    # The URL is the identity used for research-source grouping. It must not
    # be silently rebound to another publisher after the HTTPS observation.
    hostname = snapshot.get('hostname')
    if not isinstance(hostname, str):
        raise CaptureDenied('CAPTURE_ORIGIN_MISMATCH')
    try:
        observed_host, _path = target(snapshot.get('url'), (hostname,))
    except CaptureDenied as exc:
        raise CaptureDenied('CAPTURE_ORIGIN_MISMATCH') from exc
    if observed_host != hostname:
        raise CaptureDenied('CAPTURE_ORIGIN_MISMATCH')

    try:
        ip = ipaddress.ip_address(snapshot.get('resolved_ip'))
    except (ValueError, TypeError) as exc:
        raise CaptureDenied('CAPTURE_EVIDENCE_INVALID') from exc
    if not ip.is_global or (ip.version == 6 and ip.ipv4_mapped is not None):
        raise CaptureDenied('CAPTURE_EVIDENCE_INVALID')
    if (snapshot.get('http_status') != 200 or
            any(type(snapshot.get(field)) is not str or
                re.fullmatch(r'[a-f0-9]{64}', snapshot[field]) is None
                for field in ('tls_peer_cert_sha256', 'full_body_sha256', 'excerpt_sha256'))):
        raise CaptureDenied('CAPTURE_EVIDENCE_INVALID')

    value = snapshot.get('excerpt', '')
    if not isinstance(value, str) or not value or len(value) > 20000:
        raise CaptureDenied('INVALID_EXCERPT')
    if hashlib.sha256(value.encode('utf-8')).hexdigest() != snapshot['excerpt_sha256']:
        raise CaptureDenied('CAPTURE_TAMPERED')
    body_size = snapshot.get('full_bytes')
    excerpt_size = len(value.encode('utf-8'))
    if (type(body_size) is not int or body_size < 1 or body_size > MAX_RESPONSE or
            excerpt_size > min(MAX_EXCERPT, body_size) or
            type(snapshot.get('truncated')) is not bool or
            snapshot['truncated'] != (excerpt_size != body_size)):
        raise CaptureDenied('CAPTURE_EVIDENCE_INVALID')
    if 'attestation' in snapshot:
        try:
            from research_attestation import _binding
            signed_context = _binding(snapshot['attestation']['binding'])
            if signed_context['source_id'] != source_id:
                raise CaptureDenied('SOURCE_ID_BINDING_MISMATCH')
        except (TypeError, KeyError, AttestationError) as exc:
            raise CaptureDenied('INVALID_CAPTURE_BINDING') from exc
    return {'id': source_id, 'url': snapshot['url'],
            'captured_at': snapshot['captured_at'],
            'content': value, 'sha256': snapshot['excerpt_sha256'],
            'acquisition': 'connector_capture',
            **({'capture_receipt': snapshot} if 'attestation' in snapshot else {})}



# The worker is a child Python process, not a thread. The supervisor can kill
# DNS, TLS and slow-body stalls; socket timeout alone is only per-operation.
# -I ignores PYTHONPATH and other Python-specific environment injection. The
# module directory is inserted explicitly so sibling imports work.
_WORKER_BOOTSTRAP = (
    'import sys, os, json; '
    'source = sys.argv[1]; sys.path.insert(0, os.path.dirname(source)); '
    'from research_collector import _capture_child_request; '
    'record = _capture_child_request(json.loads(sys.argv[2])); '
    'sys.stdout.write(json.dumps(record, sort_keys=True, ensure_ascii=False))'
)


def _capture_child_request(request: dict) -> dict:
    """No public CLI bypass: child is reached only by a supervisor-launched code path.

    This is not a sandbox for someone already able to execute arbitrary Python
    or import acquire(). Workload authorization must live outside this process.
    """
    allowed = {'url', 'hosts', 'key_file', 'key_id', 'binding'}
    if type(request) is not dict or set(request) != allowed:
        raise CaptureDenied('INVALID_WORKER_REQUEST')
    url, hosts = request['url'], request['hosts']
    if type(hosts) is not list or not 1 <= len(hosts) <= 8 or any(
            type(h) is not str or not HOST.fullmatch(h) for h in hosts):
        raise CaptureDenied('INVALID_HOST_ALLOWLIST')
    target(url, tuple(hosts))
    key_file, key_id, binding = request['key_file'], request['key_id'], request['binding']
    if key_file is not None:
        if type(key_file) is not str or not key_file or not isinstance(key_id,str):
            raise CaptureDenied('INVALID_WORKER_SIGNER')
        _binding(binding)
        key = read_protected_key(key_file)
    else:
        if key_id is not None or binding is not None:
            raise CaptureDenied('INVALID_WORKER_SIGNER')
        key = None
    return acquire(url, tuple(hosts), signing_key=key,
                   signing_key_id=key_id, capture_binding=binding)


def _deadline_value(value: int) -> int:
    if type(value) is not int or not (1 <= value <= MAX_TOTAL_DEADLINE_SECONDS):
        raise CaptureDenied('INVALID_TOTAL_DEADLINE')
    return value


def _run_bounded_worker(command: list[str], *, deadline_seconds: int) -> dict:
    """Run one fixed worker under a finite subprocess deadline.

    No shell. No caller-supplied command in production: main() constructs a
    constant Python bootstrap and fixed absolute source path. All output is
    buffered until the child has exited successfully; stdout is not a receipt
    until it has been parsed and validated by the parent.
    """
    deadline_seconds = _deadline_value(deadline_seconds)
    # In particular strip PYTHONPATH, SSL_CERT_FILE and proxy credentials.
    environment = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR')
                   if key in os.environ}
    try:
        child = subprocess.run(command, check=False, capture_output=True,
                               text=True, timeout=deadline_seconds, env=environment)
    except subprocess.TimeoutExpired as exc:
        # subprocess.run kills and waits for its child on timeout.
        raise CaptureDenied('TOTAL_DEADLINE_EXCEEDED') from exc
    except (OSError, UnicodeError) as exc:
        raise CaptureDenied('WORKER_UNAVAILABLE') from exc
    if child.returncode != 0:
        # The worker may expose no signing material, even in its error message.
        raise CaptureDenied('WORKER_DENIED')
    if len(child.stdout.encode('utf-8')) > MAX_WORKER_STDOUT:
        raise CaptureDenied('WORKER_OUTPUT_TOO_LARGE')
    try:
        result = json.loads(child.stdout)
    except (ValueError, TypeError) as exc:
        raise CaptureDenied('WORKER_RESULT_INVALID') from exc
    if type(result) is not dict:
        raise CaptureDenied('WORKER_RESULT_INVALID')
    return result


def _capture_bounded(args, hosts: tuple[str, ...]) -> dict:
    """Validate locally, then acquire and optionally sign *inside* a child."""
    _deadline_value(args.deadline_seconds)
    # Fail closed before process creation; both worker and parent check URL.
    target(args.url, hosts)
    if bool(args.signing_key_file) != bool(args.signing_key_id):
        raise CaptureDenied('KEY_AND_ID_REQUIRED')
    if args.signing_key_file and not all((args.task_id, args.repo_head, args.source_id)):
        raise CaptureDenied('BINDING_ARGUMENTS_REQUIRED')
    if not args.signing_key_file and any((args.task_id, args.repo_head, args.source_id)):
        raise CaptureDenied('UNSIGNED_BINDING_FORBIDDEN')
    if args.signing_key_file:
        _binding({'task_id': args.task_id, 'repo_head': args.repo_head,
                  'source_id': args.source_id})
    worker_input = {
        'url': args.url, 'hosts': list(hosts),
        'key_file': args.signing_key_file, 'key_id': args.signing_key_id,
        'binding': {'task_id': args.task_id, 'repo_head': args.repo_head,
                    'source_id': args.source_id} if args.signing_key_file else None,
    }
    # No --output is sent to the child: only the supervisor can publish
    # completed and independently coherence-checked source evidence.
    script = str(Path(__file__).resolve())
    command = [sys.executable, '-I', '-c', _WORKER_BOOTSTRAP, script,
               json.dumps(worker_input, sort_keys=True)]
    result = _run_bounded_worker(command, deadline_seconds=args.deadline_seconds)
    # Local coherence validation independently of the worker process.
    packet_source(result, args.source_id or 'bounded_capture')
    if result['url'] != args.url or result['hostname'] != target(args.url, hosts)[0]:
        raise CaptureDenied('WORKER_ORIGIN_MISMATCH')
    if args.signing_key_file:
        if 'attestation' not in result:
            raise CaptureDenied('WORKER_UNSIGNED_RESULT')
        # The child reports a signature; it does not get to certify its own
        # signature as valid. Re-verify the complete record in the parent before
        # publishing any supposedly signed evidence. Fail if the shared key
        # rotated or changed between worker acquisition and verification.
        expected_binding = {'task_id': args.task_id, 'repo_head': args.repo_head,
                            'source_id': args.source_id}
        verification_key = read_protected_key(args.signing_key_file)
        if not verify_capture(result, {args.signing_key_id: verification_key},
                              expected_binding=expected_binding):
            raise CaptureDenied('WORKER_CAPTURE_ATTESTATION_INVALID')
    elif 'attestation' in result:
        raise CaptureDenied('WORKER_UNEXPECTED_ATTESTATION')
    return result



def _publish_complete_result(destination: str, encoded: str) -> None:
    """Exclusive atomic publication: no visible partial capture JSON.

    Stage in the same directory, flush/fsync, then hard-link to a NEW final
    filename (never overwrite an existing evidence record). Fail closed if
    filesystem hard links are unsupported; do not silently fall back to copy.
    """
    final = Path(destination)
    parent = final.parent
    # The final path must be a name, not a directory alias or a parent walk.
    if final.name in ('', '.', '..'):
        raise CaptureDenied('INVALID_OUTPUT_PATH')
    fd, staging = tempfile.mkstemp(prefix='.aegis-capture-', suffix='.partial',
                                   dir=str(parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        # POSIX hard-link creation is atomic and fails if the destination exists,
        # including when it is a symlink. Both names share the same filesystem.
        os.link(staging, final)
        # Best-effort sync of the directory entry on POSIX. Some filesystems
        # may not support this; don't claim power-loss durability on all media.
        if os.name == 'posix':
            directory_fd = os.open(str(parent), os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        # Never leave a leaked staging name on any ordinary exception path.
        try:
            os.unlink(staging)
        except FileNotFoundError:
            pass


def main(argv=None):
    a = argparse.ArgumentParser(description='Opt-in bounded HTTPS-only public research capture')
    a.add_argument('url')
    a.add_argument('--allow-host', action='append', required=True)
    a.add_argument('--allow-network', action='store_true', help='explicit opt-in required')
    a.add_argument('--output', help='explicit local output path (else stdout)')
    a.add_argument('--deadline-seconds', type=int, default=DEFAULT_TOTAL_DEADLINE_SECONDS,
                   help='total worker wall-clock limit, 1-120 s (default 20)')
    a.add_argument('--signing-key-file', help='32 raw secret bytes in owner-only file; trusted runner ONLY')
    a.add_argument('--signing-key-id', help='externally configured trusted runner key ID')
    a.add_argument('--task-id', help='trusted runner task identity (required to sign)')
    a.add_argument('--repo-head', help='trusted runner exact source Git OID (required to sign)')
    a.add_argument('--source-id', help='trusted runner stable source ID (required to sign)')
    args = a.parse_args(argv)
    if not args.allow_network:
        a.error('NETWORK_DISABLED: pass --allow-network for explicitly authorized public capture')
    hosts = tuple(args.allow_host)
    if len(hosts) > 8 or any(not isinstance(h, str) or not HOST.fullmatch(h) for h in hosts):
        a.error('INVALID_HOST_ALLOWLIST')
    try:
        if bool(args.signing_key_file) != bool(args.signing_key_id):
            raise CaptureDenied('KEY_AND_ID_REQUIRED')
        if args.signing_key_file and not all((args.task_id, args.repo_head, args.source_id)):
            raise CaptureDenied('BINDING_ARGUMENTS_REQUIRED')
        if not args.signing_key_file and any((args.task_id, args.repo_head, args.source_id)):
            raise CaptureDenied('UNSIGNED_BINDING_FORBIDDEN')
        _deadline_value(args.deadline_seconds)
        result = _capture_bounded(args, hosts)
    except (CaptureDenied, AttestationError, OSError) as exc:
        a.exit(2, 'DENIED: ' + str(exc) + '\n')
    encoded = json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        try:
            _publish_complete_result(args.output, encoded)
        except (OSError, CaptureDenied):
            a.exit(2, 'DENIED: OUTPUT_PUBLICATION_FAILED\n')
    else:
        print(encoded, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
