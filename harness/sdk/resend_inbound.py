"""Resend -> existing AEGIS envelopes, observation-only, without network or dispatch.

Contract pinned in docs/resend-inbound-contract-v1.md. The HTTP host, credentials,
route, runtime identity and policy registry are TRUSTED inputs. All email fields
remain UNTRUSTED DATA even after the provider's webhook signature is verified.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import math
import os
import re
import sqlite3
import time
import unicodedata
from contextlib import closing
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence
from uuid import UUID

from harness.sdk.sovereign_execution import (
    ADMITTED, D0, ZERO_HASH, AuthorityEvaluator, AuthorityRequest, EventEnvelope,
    ExecutionIdentityEnvelope, PolicyDecision, SovereignExecutionError,
    canonical_bytes, canonical_hash, sha256_hex,
)

# This names a REQUEST, not a registry entry or a grant. The pinned repo has no
# matching capability. Do not alias it to platform-status or execution-read.
CAPABILITY = 'resend.inbound.observe'
TOOL = 'resend_inbound'
MAX_BODY_BYTES = 65_536
MAX_HEADERS_BYTES = 8_192
MAX_SUBJECT_BYTES = 2_048
MAX_ADDRESSES_PER_FIELD = 10
MAX_ADDRESSES_TOTAL = 20
MAX_ATTACHMENTS = 8
MAX_ATTACHMENT_FILENAME_BYTES = 512
MAX_ATTACHMENT_TYPE_BYTES = 256
MAX_ATTACHMENT_CONTENT_ID_BYTES = 512
TIMESTAMP_TOLERANCE_SECONDS = 300
_SAFE_ID = re.compile(r'[A-Za-z0-9._:/@+#=-]{1,256}')
_LOCAL = re.compile(r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*")
_LABEL = re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?')


class InboundError(ValueError):
    """Stable public code only; never expose a body, credential or exception text."""
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _text(value: object, maximum: int, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value):
        raise InboundError('TEXT_INVALID')
    if len(value.encode('utf-8')) > maximum:
        raise InboundError('FIELD_TOO_LARGE')
    if unicodedata.normalize('NFC', value) != value or any(unicodedata.category(c).startswith('C') for c in value):
        raise InboundError('TEXT_CONTROL_OR_UNICODE_AMBIGUITY')
    return value


def normalize_sender(value: str) -> str:
    """Conservative one-mailbox profile: ASCII dot-atom address, optional display name.

    Preserve local-part case, dots and plus tags. Lowercase the domain only.
    Unicode display names are data; SMTPUTF8, quoted local parts, groups and
    comments are deliberately unsupported. This is NOT sender authentication.
    """
    value = _text(value, 1_024).strip()
    if '<' in value or '>' in value:
        match = re.fullmatch(r'[^<>]*<([^<>]+)>', value)
        if not match:
            raise InboundError('SENDER_INVALID')
        display = value[:value.index('<')].strip()
        if display.startswith('"'):
            if not re.fullmatch(r'"(?:[^"\\]|\\["\\])*"', display):
                raise InboundError('SENDER_INVALID')
        elif any(c in display for c in '@,;:()"\\'):
            raise InboundError('SENDER_INVALID')
        value = match.group(1).strip()
    if not value.isascii() or len(value) > 254 or value.count('@') != 1:
        raise InboundError('SENDER_INVALID')
    local, domain = value.split('@')
    if len(local) > 64 or not _LOCAL.fullmatch(local) or not all(_LABEL.fullmatch(p) for p in domain.split('.')):
        raise InboundError('SENDER_INVALID')
    return local + '@' + domain.lower()


def _headers(pairs: Sequence[tuple[str, str]]) -> dict[str, str]:
    # A mapping has already discarded duplicates; the host must preserve pairs.
    if not isinstance(pairs, (list, tuple)) or len(pairs) > 32:
        raise InboundError('INVALID_HEADERS')
    result: dict[str, str] = {}
    total = 0
    for pair in pairs:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise InboundError('INVALID_HEADERS')
        key, value = pair
        if not isinstance(key, str) or not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9-]+', key):
            raise InboundError('INVALID_HEADERS')
        if not value.isascii() or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise InboundError('INVALID_HEADERS')
        total += len(key) + len(value) + 4
        if total > MAX_HEADERS_BYTES:
            raise InboundError('HEADERS_TOO_LARGE')
        key = key.lower()
        if key in result:
            raise InboundError('DUPLICATE_HEADER')
        result[key] = value
    return result


def verify_signature(raw: bytes, headers: Sequence[tuple[str, str]], secrets: tuple[str, ...], *, now: float) -> str:
    """Svix v1 HMAC over ORIGINAL bytes; returns verified delivery ID, not a principal.

    Implements the official manual contract; no Resend API key substitutes for a
    whsec_ signing secret. At most two trusted keys allow endpoint-key rotation.
    """
    if not isinstance(raw, bytes) or not raw:
        raise InboundError('RAW_BYTES_REQUIRED')
    if len(raw) > MAX_BODY_BYTES:
        raise InboundError('BODY_TOO_LARGE')
    h = _headers(headers)
    required = ('svix-id', 'svix-timestamp', 'svix-signature')
    if any(k not in h for k in required):
        raise InboundError('SIGNATURE_HEADERS_MISSING')
    delivery, timestamp = h['svix-id'], h['svix-timestamp']
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', delivery) or not re.fullmatch(r'[0-9]{1,12}', timestamp):
        raise InboundError('SIGNATURE_HEADERS_INVALID')
    if isinstance(now, bool) or not isinstance(now, (int, float)) or not math.isfinite(now):
        raise InboundError('CLOCK_UNAVAILABLE')
    if abs(now - int(timestamp)) > TIMESTAMP_TOLERANCE_SECONDS:
        raise InboundError('SIGNATURE_TIMESTAMP_OUTSIDE_WINDOW')
    if not isinstance(secrets, tuple) or not 1 <= len(secrets) <= 2:
        raise InboundError('WEBHOOK_SECRET_UNAVAILABLE')
    keys = []
    for secret in secrets:
        try:
            if not isinstance(secret, str) or not secret.startswith('whsec_') or len(secret) > 128:
                raise ValueError()
            key = base64.b64decode(secret[6:], validate=True)
            if not 16 <= len(key) <= 64:
                raise ValueError()
            keys.append(key)
        except (ValueError, binascii.Error):
            raise InboundError('WEBHOOK_SECRET_UNAVAILABLE') from None
    signatures = h['svix-signature'].split(' ')
    if not 1 <= len(signatures) <= 8:
        raise InboundError('SIGNATURE_INVALID')
    signed = (delivery + '.' + timestamp + '.').encode('ascii') + raw
    matched = False
    for part in signatures:
        version, sep, encoded = part.partition(',')
        if version != 'v1' or not sep:
            continue
        try:
            candidate = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            continue
        if len(candidate) != 32:
            continue
        for key in keys:
            matched |= hmac.compare_digest(hmac.new(key, signed, hashlib.sha256).digest(), candidate)
    if not matched:
        raise InboundError('SIGNATURE_INVALID')
    return delivery


def _strict_json(raw: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise InboundError('JSON_DUPLICATE_KEY')
            result[key] = value
        return result

    def constant(_):
        raise InboundError('JSON_NONFINITE')

    def bound(value, depth=0):
        if depth > 16:
            raise InboundError('JSON_TOO_DEEP')
        if isinstance(value, float) and not math.isfinite(value):
            raise InboundError('JSON_NONFINITE')
        if isinstance(value, (dict, list)):
            for item in value.values() if isinstance(value, dict) else value:
                bound(item, depth + 1)

    try:
        obj = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
        bound(obj)
        if not isinstance(obj, dict):
            raise InboundError('SCHEMA_INVALID')
        return obj
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        if isinstance(exc, InboundError):
            raise
        raise InboundError('JSON_INVALID') from None


def _shape(obj: object, required: set[str], optional: set[str] = frozenset()) -> dict:
    if not isinstance(obj, dict) or not required.issubset(obj):
        raise InboundError('SCHEMA_INVALID')
    if set(obj) - required - optional:
        raise InboundError('SCHEMA_DRIFT')
    return obj


def _uuid(value: object) -> str:
    if not isinstance(value, str) or len(value) != 36:
        raise InboundError('PROVIDER_ID_INVALID')
    try:
        if str(UUID(value)) != value or int(UUID(value)) == 0:
            raise ValueError()
    except ValueError:
        raise InboundError('PROVIDER_ID_INVALID') from None
    return value


def _timestamp(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})', value):
        raise InboundError('EVENT_TIMESTAMP_INVALID')
    try:
        datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:
        raise InboundError('EVENT_TIMESTAMP_INVALID') from None
    return value


def _addresses(value: object, *, bare: bool = False) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_ADDRESSES_PER_FIELD:
        raise InboundError('ADDRESSES_INVALID')
    result = []
    for item in value:
        address = normalize_sender(item)
        if bare and (not isinstance(item, str) or any(c in item for c in '<> ') or not item.isascii()):
            raise InboundError('TRANSPORT_ADDRESS_INVALID')
        result.append(address)
    return result


@dataclass(frozen=True)
class Route:
    endpoint_scope: str
    routing_domain: str
    receiving_addresses: tuple[str, ...]

    def validate(self) -> None:
        for value in (self.endpoint_scope, self.routing_domain):
            if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
                raise InboundError('ROUTE_CONFIGURATION_INVALID')
        if not isinstance(self.receiving_addresses, tuple) or not self.receiving_addresses:
            raise InboundError('ROUTE_CONFIGURATION_INVALID')
        if len(self.receiving_addresses) > MAX_ADDRESSES_PER_FIELD:
            raise InboundError('ROUTE_CONFIGURATION_INVALID')
        for address in self.receiving_addresses:
            if normalize_sender(address) != address:
                raise InboundError('ROUTE_CONFIGURATION_INVALID')


def _attachment_metadata(value: object) -> list[dict]:
    if not isinstance(value, list) or len(value) > MAX_ATTACHMENTS:
        raise InboundError('ATTACHMENTS_LIMIT_EXCEEDED')
    result: list[dict] = []
    for item in value:
        item = _shape(item, {'id'}, {'filename', 'content_type', 'content_disposition', 'content_id'})
        attachment_id = _text(item['id'], 256)
        if not _SAFE_ID.fullmatch(attachment_id):
            raise InboundError('ATTACHMENT_ID_INVALID')
        normalized = {'id': attachment_id}
        if 'filename' in item:
            normalized['filename'] = _text(item['filename'], MAX_ATTACHMENT_FILENAME_BYTES, empty=True)
        if 'content_type' in item:
            normalized['content_type'] = _text(item['content_type'], MAX_ATTACHMENT_TYPE_BYTES)
        if 'content_disposition' in item:
            disposition = item['content_disposition']
            if disposition not in ('inline', 'attachment'):
                raise InboundError('ATTACHMENT_DISPOSITION_INVALID')
            normalized['content_disposition'] = disposition
        if 'content_id' in item:
            normalized['content_id'] = _text(item['content_id'], MAX_ATTACHMENT_CONTENT_ID_BYTES, empty=True)
        result.append(normalized)
    return result


def _message(event: dict, route: Route) -> tuple[dict, str]:
    _shape(event, {'type', 'created_at', 'data'})
    typ = event['type']
    if typ != 'email.received':
        raise InboundError('EVENT_TYPE_UNSUPPORTED')
    _timestamp(event['created_at'])

    required = {
        'email_id', 'created_at', 'from', 'to', 'subject', 'message_id',
        'bcc', 'cc', 'attachments',
    }
    data = _shape(event['data'], required, {'received_for'})
    email_id = _uuid(data['email_id'])
    received_at = _timestamp(data['created_at'])
    sender = normalize_sender(data['from'])
    addresses = {key: _addresses(data[key], bare=True) for key in ('to', 'cc', 'bcc')}
    if not addresses['to'] or not set(addresses['to']).issubset(route.receiving_addresses):
        raise InboundError('ROUTE_MISMATCH')
    received_for = _addresses(data.get('received_for', []), bare=True)
    if sum(len(v) for v in addresses.values()) + len(received_for) > MAX_ADDRESSES_TOTAL:
        raise InboundError('TOO_MANY_ADDRESSES')
    attachments = _attachment_metadata(data['attachments'])

    normalized = {
        'provider': 'resend',
        'event_type': typ,
        'email_id': email_id,
        'sender': sender,
        'sender_authentication': 'UNVERIFIED_EMAIL_CLAIM',
        'subject': _text(data['subject'], MAX_SUBJECT_BYTES, empty=True),
        'message_id': _text(data['message_id'], 512),
        'received_at': received_at,
        'received_for': received_for,
        **addresses,
        'attachments': attachments,
        'attachment_count': len(attachments),
        'attachment_content_state': 'NOT_FETCHED',
        'content_state': 'NOT_FETCHED',
        'execution_state': 'NOT_EXECUTED',
        'granted_capabilities': [],
        'trust': 'UNTRUSTED_EMAIL_DATA',
    }
    message_key = canonical_hash('AEGIS_RESEND_MESSAGE_KEY_V1', [typ, email_id])
    return normalized, message_key


@dataclass(frozen=True)
class InboundResult:
    status: str
    codes: tuple[str, ...] = ()
    event: EventEnvelope | None = None
    identity: ExecutionIdentityEnvelope | None = None
    decision: PolicyDecision | None = None


class LocalJournal:
    """Single-host durable evidence journal, NOT an executable agent queue.

    All delivery IDs and observations are committed atomically. No TTL: manual
    replays must not become new work. The operator owns retention/backup and
    supplies a private trusted directory. This is not a distributed exactly-once
    guarantee and does not replace the external action idempotency protocol.
    """
    def __init__(self, path: str | Path, *, max_observations: int = 1_000, max_deliveries: int = 10_000):
        if any(type(v) is not int or v < 1 for v in (max_observations,max_deliveries)):
            raise InboundError('JOURNAL_CAPACITY_INVALID')
        self.max_observations, self.max_deliveries = max_observations, max_deliveries
        if str(path) == ':memory:':
            raise InboundError('DURABLE_JOURNAL_REQUIRED')
        self.path = Path(path)
        if self.path.is_symlink() or not self.path.parent.is_dir():
            raise InboundError('JOURNAL_PATH_INVALID')
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        except FileExistsError:
            if not self.path.is_file():
                raise InboundError('JOURNAL_PATH_INVALID') from None
        with closing(self._connect()) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS observations (scope TEXT NOT NULL, message_key TEXT NOT NULL, semantic_digest TEXT NOT NULL, sequence INTEGER NOT NULL, event_root TEXT NOT NULL, record TEXT NOT NULL, PRIMARY KEY(scope,message_key), UNIQUE(scope,sequence))')
            db.execute('CREATE TABLE IF NOT EXISTS deliveries (scope TEXT NOT NULL, delivery_id TEXT NOT NULL, input_digest TEXT NOT NULL, message_key TEXT NOT NULL, PRIMARY KEY(scope,delivery_id))')

    def _connect(self):
        return sqlite3.connect(self.path, timeout=5.0)

    def count(self) -> int:
        with closing(self._connect()) as db:
            return db.execute('SELECT count(*) FROM observations').fetchone()[0]

    def append(self, *, scope: str, delivery_id: str, input_digest: str, message_key: str,
               semantic_digest: str, build: Callable[[int, str], InboundResult]) -> InboundResult:
        with closing(self._connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                delivery = db.execute('SELECT input_digest,message_key FROM deliveries WHERE scope=? AND delivery_id=?', (scope,delivery_id)).fetchone()
                if delivery:
                    if delivery != (input_digest,message_key):
                        raise InboundError('DELIVERY_ID_CONFLICT')
                    if not db.execute('SELECT 1 FROM observations WHERE scope=? AND message_key=?', (scope,message_key)).fetchone():
                        raise InboundError('JOURNAL_INCONSISTENT')
                    db.commit()
                    return InboundResult('DUPLICATE')
                known = db.execute('SELECT semantic_digest FROM observations WHERE scope=? AND message_key=?', (scope,message_key)).fetchone()
                if known and known[0] != semantic_digest:
                    raise InboundError('MESSAGE_ID_CONFLICT')
                if (not known and db.execute('SELECT count(*) FROM observations').fetchone()[0] >= self.max_observations
                        or db.execute('SELECT count(*) FROM deliveries').fetchone()[0] >= self.max_deliveries):
                    raise InboundError('JOURNAL_CAPACITY')
                if known:
                    result = InboundResult('DUPLICATE')
                else:
                    last = db.execute('SELECT sequence,event_root FROM observations WHERE scope=? ORDER BY sequence DESC LIMIT 1', (scope,)).fetchone()
                    sequence, parent = (last[0]+1,last[1]) if last else (0,ZERO_HASH)
                    result = build(sequence, parent)
                    record = canonical_bytes(asdict(result)).decode('utf-8')
                    db.execute('INSERT INTO observations VALUES (?,?,?,?,?,?)', (scope,message_key,semantic_digest,sequence,result.event.root,record))
                db.execute('INSERT INTO deliveries VALUES (?,?,?,?)', (scope,delivery_id,input_digest,message_key))
                db.commit()
                return result
            except BaseException:
                db.rollback()
                raise


class InboundAdapter:
    """Raw request boundary. No send, fetch, subprocess, agent dispatch or grant.

    Provide registry_root from the same trusted load_capability_registry call as
    evaluator.registry. Never construct any of these bindings from webhook data.
    """
    def __init__(self, *, secrets: tuple[str, ...], route: Route,
                 identity: ExecutionIdentityEnvelope, evaluator: AuthorityEvaluator,
                 registry_root: str, journal: LocalJournal, clock: Callable[[], float] = time.time):
        self.secrets, self.route, self.identity = secrets, route, identity
        self.evaluator, self.registry_root, self.journal, self.clock = evaluator, registry_root, journal, clock

    def _runtime(self) -> None:
        self.route.validate()
        try:
            self.identity.validate()
        except (SovereignExecutionError, TypeError, ValueError):
            raise InboundError('RUNTIME_BINDING_INVALID') from None
        i = self.identity
        if (i.registry_root != self.registry_root or i.policy_root != self.evaluator.policy_root
                or i.observed_authority != 'NONE' or i.approval_reference != 'NONE'
                or i.requested_capability != CAPABILITY or i.tool_identity != TOOL
                or i.actor_class != 'TRANSPORT_ADAPTER' or i.actor_identity != 'resend-inbound'
                or i.authority_domain != self.route.routing_domain or i.model_identity != 'NONE'):
            raise InboundError('RUNTIME_BINDING_INVALID')
        # Fail retryably before retaining a candidate when the service is missing.
        if self.evaluator.policy is None:
            raise InboundError('AUTHORITY_SERVICE_UNAVAILABLE')
        if self.evaluator.registry is None:
            raise InboundError('REGISTRY_UNAVAILABLE')
        if canonical_hash('AEGIS_CONSEQUENCE_POLICY_V1',self.evaluator.policy) != i.policy_root:
            raise InboundError('RUNTIME_BINDING_INVALID')

    def handle(self, raw: bytes, headers: Sequence[tuple[str, str]], *, method: str = 'POST') -> InboundResult:
        try:
            if method != 'POST':
                raise InboundError('METHOD_UNSUPPORTED')
            delivery = verify_signature(raw, headers, self.secrets, now=self.clock())
            h = _headers(headers)
            if h.get('content-encoding','identity').lower() != 'identity':
                raise InboundError('CONTENT_ENCODING_UNSUPPORTED')
            if h.get('content-type','').lower() not in ('application/json','application/json; charset=utf-8'):
                raise InboundError('CONTENT_TYPE_UNSUPPORTED')
            if 'content-length' in h and h['content-length'] != str(len(raw)):
                raise InboundError('CONTENT_LENGTH_MISMATCH')
            self._runtime()
            message, message_key = _message(_strict_json(raw),self.route)
            input_digest = sha256_hex(raw)
            action = {'operation':'observe_inbound_metadata', 'provider':'resend',
                      'message_key':message_key, 'input_digest':input_digest}
            identity = replace(self.identity, input_digest=input_digest,
                action_digest=canonical_hash('AEGIS_REQUESTED_ACTION_V1', action),
                deterministic_nonce=message_key)
            decision = self.evaluator.evaluate(AuthorityRequest(
                action_class=D0, authority_domain=identity.authority_domain,
                requested_capability=CAPABILITY, tool=TOOL, target='evidence:resend:'+message_key,
                identity_root=identity.root, workspace_binding=identity.workspace_binding,
                source_commit=identity.source_commit, registry_root=identity.registry_root,
                policy_root=identity.policy_root, current_generation=0))
            if any(c in decision.denial_codes for c in ('AUTHORITY_SERVICE_UNAVAILABLE','REGISTRY_UNAVAILABLE','POLICY_UNAVAILABLE','POLICY_ROOT_MISMATCH')):
                raise InboundError('AUTHORITY_SERVICE_UNAVAILABLE')
            # A denial is retained as blocked evidence, NOT dropped or promoted.
            status = 'VERIFIED_OBSERVATION_ONLY' if decision.outcome == ADMITTED else 'VERIFIED_NOT_ADMITTED'
            payload = {'content_type':'application/vnd.aegis.resend-inbound-metadata+json', 'data':message}

            def build(sequence: int, parent: str) -> InboundResult:
                event = EventEnvelope(
                    sender_identity_root=identity.root,
                    recipient_or_routing_domain=self.route.routing_domain,
                    source_state=identity.parent_state_root, capability_request=CAPABILITY,
                    payload_schema='resend-inbound-metadata.v1', payload=payload,
                    payload_digest=sha256_hex(canonical_bytes(payload)),
                    provenance='resend-webhook:'+input_digest,
                    policy_decision=decision.decision_root, parent_event=parent,
                    sequence=sequence, receipt_reference=ZERO_HASH)
                event.validate(expected_sequence=sequence, expected_parent=parent)
                return InboundResult(status,tuple(decision.denial_codes),event,identity,decision)

            return self.journal.append(scope=self.route.endpoint_scope, delivery_id=delivery,
                input_digest=input_digest, message_key=message_key,
                semantic_digest=canonical_hash('AEGIS_RESEND_METADATA_V1',message),build=build)
        except InboundError as exc:
            return InboundResult('REJECTED',(exc.code,))
        except (sqlite3.Error, OSError):
            return InboundResult('REJECTED',('JOURNAL_UNAVAILABLE',))
        except SovereignExecutionError:
            return InboundResult('REJECTED',('AEGIS_ENVELOPE_INVALID',))
        except Exception:
            # No fallback verifier, actor, registry, journal, admission or dispatch.
            return InboundResult('REJECTED',('ADAPTER_INTERNAL_ERROR',))
