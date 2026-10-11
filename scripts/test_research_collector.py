import datetime as dt
import hashlib
import socket
import unittest

from research_collector import (CaptureDenied, PinnedTLS, acquire, packet_source,
                                public_ip_set, target, main)

OK_HOST = ('docs.example.org',)
NOW = dt.datetime(2026, 10, 11, 6, 14, tzinfo=dt.timezone.utc)


def res(addr='93.184.216.34'):
    family = socket.AF_INET6 if ':' in addr else socket.AF_INET
    address = (addr, 443, 0, 0) if family == socket.AF_INET6 else (addr, 443)
    return [(family, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', address)]


class FakeSock:
    def getpeercert(self, binary_form=False):
        return b'fake-for-test-only' if binary_form else {}


class FakeReply:
    def __init__(self, status=200, body=b'Hello public page', headers=None):
        self.status, self.body = status, body
        self.headers = headers or {'Content-Type': 'text/plain', 'Content-Length': str(len(body))}

    def getheader(self, name):
        return self.headers.get(name)

    def read(self, limit):
        return self.body[:limit]


class FakeConnection:
    response = FakeReply()
    calls = []

    def __init__(self, host, ip, *, timeout):
        self.calls.append(('created', host, ip, timeout))
        self.sock = FakeSock()

    def connect(self):
        self.calls.append(('connect',))

    def request(self, method, path, headers):
        self.calls.append(('request', method, path, headers))

    def getresponse(self):
        return self.response

    def close(self):
        self.calls.append(('closed',))


def capture(**kw):
    FakeConnection.calls.clear()
    FakeConnection.response = kw.pop('response', FakeReply())
    resolver = kw.pop('resolver', lambda *args, **kwargs: res())
    return acquire('https://docs.example.org/page', OK_HOST,
                   resolver=resolver, connection_factory=FakeConnection, clock=lambda: NOW, **kw)


class CollectorTests(unittest.TestCase):
    def test_target(self):
        self.assertEqual(target('https://docs.example.org/path', OK_HOST), ('docs.example.org','/path'))
    def test_root(self):
        self.assertEqual(target('https://docs.example.org', OK_HOST)[1], '/')
    def test_verified_receipt_local_not_publisher(self):
        result = capture()
        self.assertEqual(result['schema'], 'aegis.research.capture.v1')
        self.assertEqual(result['claim_truth'], 'NOT_VERIFIED')
        self.assertEqual(result['publisher_identity'], 'NOT_INDEPENDENTLY_AUTHENTICATED')
        self.assertEqual(result['authority_effect'], 'NONE')
        self.assertEqual(result['captured_at'], '2026-10-11T06:14:00Z')
        self.assertEqual(result['full_body_sha256'], hashlib.sha256(b'Hello public page').hexdigest())
        self.assertIn(('created','docs.example.org','93.184.216.34',8), FakeConnection.calls)
        self.assertEqual(FakeConnection.calls[-1], ('closed',))
    def test_get_only_and_no_credentials(self):
        capture()
        request = next(c for c in FakeConnection.calls if c[0] == 'request')
        self.assertEqual(request[1:3], ('GET','/page'))
        self.assertEqual(request[3]['Accept-Encoding'], 'identity')
        self.assertNotIn('Authorization', request[3])
        self.assertNotIn('Cookie', request[3])
    def test_packet_compatibility(self):
        source = packet_source(capture(), 'release_1')
        self.assertEqual(source['acquisition'], 'connector_capture')
        self.assertEqual(source['sha256'],hashlib.sha256(source['content'].encode()).hexdigest())
    def test_tampered_packet_rejected(self):
        snap = capture(); snap['excerpt'] = 'tampered'
        with self.assertRaisesRegex(CaptureDenied,'CAPTURE_TAMPERED'):
            packet_source(snap,'release_1')
    def test_bad_source_id(self):
        with self.assertRaisesRegex(CaptureDenied,'INVALID_SOURCE_ID'):
            packet_source(capture(),'../../../etc')
    def test_no_real_network_default_cli(self):
        with self.assertRaises(SystemExit) as ctx:
            main(['https://docs.example.org/page','--allow-host','docs.example.org'])
        self.assertEqual(ctx.exception.code, 2)
    def test_https_only(self):
        for u in ['http://docs.example.org/','ftp://docs.example.org/a','file:///etc/passwd','//docs.example.org/a']:
            with self.subTest(u=u),self.assertRaises(CaptureDenied):target(u,OK_HOST)
    def test_host_allowlist_exact(self):
        for u in ['https://docs.example.org.evil.com/','https://foo.docs.example.org/','https://not-allowed.org/']:
            with self.subTest(u=u),self.assertRaisesRegex(CaptureDenied,'HOST_NOT_ALLOWED'):
                target(u, OK_HOST)
    def test_url_userinfo(self):
        with self.assertRaises(CaptureDenied): target('https://a:b@docs.example.org/a',OK_HOST)
    def test_url_query_fragment(self):
        for u in ['https://docs.example.org/a?secret=1','https://docs.example.org/a#secret']:
            with self.subTest(u=u),self.assertRaises(CaptureDenied):target(u,OK_HOST)
    def test_url_port(self):
        with self.assertRaises(CaptureDenied):target('https://docs.example.org:443/a',OK_HOST)
    def test_url_backslash_and_newline(self):
        for u in ['https://docs.example.org\\@127.0.0.1/','https://docs.example.org/\r\nHost: bad']:
            with self.subTest(u=u),self.assertRaises(CaptureDenied):target(u,OK_HOST)
    def test_bad_ipv6_url(self):
        with self.assertRaises(CaptureDenied):target('https://[::1/a',OK_HOST)
    def test_ip_literal_rejected(self):
        with self.assertRaises(CaptureDenied):target('https://93.184.216.34/',('93.184.216.34',))
    def test_public_ipv4(self):
        self.assertEqual(public_ip_set('docs.example.org',lambda *args,**kw:res()),('93.184.216.34',))
    def test_dns_private_ipv4_ipv6(self):
        for addr in ['127.0.0.1','10.0.0.1','192.168.1.1','169.254.169.254','::1','fc00::1','fe80::1']:
            with self.subTest(addr=addr),self.assertRaises(CaptureDenied):
                public_ip_set('docs.example.org',lambda *args, **kw:res(addr))
    def test_dns_ipv4_mapped_ipv6(self):
        with self.assertRaises(CaptureDenied):public_ip_set('docs.example.org',lambda *args,**kw:res('::ffff:127.0.0.1'))
    def test_dns_mixed_public_private(self):
        with self.assertRaisesRegex(CaptureDenied,'DNS_NONPUBLIC_IP'):
            public_ip_set('docs.example.org',lambda *args,**kw:res()+res('10.0.0.1'))
    def test_dns_multiple_public_all_validated_and_one_pinned(self):
        d=capture(resolver=lambda *args,**kw:res()+res('1.1.1.1'))
        self.assertEqual(d['resolved_ip'], '1.1.1.1')
        created=[c for c in FakeConnection.calls if c[0]=='created']
        self.assertEqual(len(created),1)
    def test_dns_empty_and_failure(self):
        with self.assertRaises(CaptureDenied):public_ip_set('docs.example.org',lambda *a,**k:[])
        with self.assertRaises(CaptureDenied):public_ip_set('docs.example.org',lambda *a,**k:(_ for _ in ()).throw(OSError()))
    def test_redirect_denied(self):
        with self.assertRaisesRegex(CaptureDenied,'HTTP_NOT_200'):
            capture(response=FakeReply(302,b'',{'Location':'http://127.0.0.1/admin'}))
    def test_non200_denied(self):
        with self.assertRaises(CaptureDenied):capture(response=FakeReply(403))
    def test_encoding_denied(self):
        with self.assertRaises(CaptureDenied):capture(response=FakeReply(headers={'Content-Encoding':'gzip','Content-Type':'text/html'}))
    def test_content_type_denied(self):
        with self.assertRaises(CaptureDenied):capture(response=FakeReply(headers={'Content-Type':'application/octet-stream'}))
    def test_large_declared_denied(self):
        with self.assertRaises(CaptureDenied):capture(response=FakeReply(headers={'Content-Type':'text/html','Content-Length':'10000000'}))
    def test_large_stream_denied(self):
        with self.assertRaises(CaptureDenied):capture(response=FakeReply(body=b'x'*131073))
    def test_empty_denied(self):
        with self.assertRaises(CaptureDenied):capture(response=FakeReply(body=b''))
    def test_utf8_denied(self):
        with self.assertRaises(CaptureDenied):capture(response=FakeReply(body=b'\xff'))
    def test_excerpt_bounded_and_explicit(self):
        d=capture(response=FakeReply(body=b'a'*16010))
        self.assertTrue(d['truncated']);self.assertEqual(len(d['excerpt']),16000)
        self.assertNotEqual(d['full_body_sha256'],d['excerpt_sha256'])
    def test_naive_clock_denied(self):
        with self.assertRaises(CaptureDenied):
            acquire('https://docs.example.org/page',OK_HOST,resolver=lambda *a,**k:res(),connection_factory=FakeConnection,
                    clock=lambda:dt.datetime(2026,10,11,6,14))
    def test_real_connection_pins_numeric_socket_and_tls_host(self):
        # Structural proof of no hostname re-resolution in transport's connect().
        import inspect
        src=inspect.getsource(PinnedTLS.connect)
        self.assertIn('raw.connect((self.public_ip, 443))',src)
        self.assertIn('server_hostname=self.host',src)
        self.assertNotIn('create_connection',src)

if __name__=='__main__':unittest.main()
