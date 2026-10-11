"""Real TLS-handshake tests using a loopback server and disposable test CA.

Do not confuse local TLS tests with external HTTPS collection or publisher
attestation. No non-stdlib imports. OpenSSL CLI is used only to create ephemeral
certificate material inside TemporaryDirectory.
"""
import datetime as dt
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import research_collector as module


class RealLocalTLS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('openssl'):
            raise unittest.SkipTest('OpenSSL CLI missing; TLS integration NOT_RUN')
        cls.temp = tempfile.TemporaryDirectory()
        cls.cert = Path(cls.temp.name) / 'cert.pem'
        cls.key = Path(cls.temp.name) / 'key.pem'
        cmd = ['openssl', 'req', '-x509', '-nodes', '-newkey', 'rsa:2048', '-days', '1',
               '-subj', '/CN=docs.example.org', '-addext', 'subjectAltName=DNS:docs.example.org',
               '-keyout', str(cls.key), '-out', str(cls.cert)]
        subprocess.run(cmd, capture_output=True, check=True, timeout=8)
        cls.server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        cls.server_context.load_cert_chain(str(cls.cert), str(cls.key))
        cls.client_context = ssl.create_default_context(cafile=str(cls.cert))

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'temp'):
            cls.temp.cleanup()

    def exchange(self, hostname, *, server_payload=None):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        listener.settimeout(4)
        port = listener.getsockname()[1]
        evidence = {'requests': [], 'sni': [], 'connect_to': [], 'server_errors': []}
        ctx = self.server_context
        ctx.set_servername_callback(lambda _sock, name, _ctx: evidence['sni'].append(name))

        def serve():
            try:
                client, _ = listener.accept()
                with client:
                    with ctx.wrap_socket(client, server_side=True) as tls:
                        tls.settimeout(3)
                        evidence['requests'].append(tls.recv(4096).decode('ascii'))
                        tls.sendall(server_payload if server_payload is not None else
                                    b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n'
                                    b'Content-Length: 7\r\nConnection: close\r\n\r\nTLS_OK!')
            except (ssl.SSLError, OSError) as error:
                evidence['server_errors'].append(type(error).__name__)
            finally:
                listener.close()

        t = threading.Thread(target=serve, daemon=True)
        t.start()
        real_socket = socket.socket

        class RedirectSocket(real_socket):
            def connect(self, address):
                evidence['connect_to'].append(address)
                return super().connect(('127.0.0.1', port))

        def resolver(_hostname, _port, *, type):
            self.assertEqual(type, socket.SOCK_STREAM)
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP,
                     '', ('93.184.216.34', 443))]

        # This patch only diverts the *numeric-IP* socket connection for the test.
        # TLS still executes with certificate verification and hostname checking.
        with patch.object(module.socket, 'socket', RedirectSocket), \
             patch.object(module.ssl, 'create_default_context', return_value=self.client_context):
            try:
                capture = module.acquire(
                    f'https://{hostname}/release', (hostname,), resolver=resolver,
                    clock=lambda: dt.datetime(2026, 10, 11, tzinfo=dt.timezone.utc))
                return capture, evidence
            finally:
                t.join(timeout=5)
                self.assertFalse(t.is_alive(), 'TLS server thread hung')

    def test_valid_hostname_verified_by_real_tls(self):
        result, evidence = self.exchange('docs.example.org')
        self.assertEqual(result['excerpt'], 'TLS_OK!')
        self.assertEqual(result['resolved_ip'], '93.184.216.34')
        self.assertEqual(evidence['sni'], ['docs.example.org'])
        self.assertEqual(evidence['connect_to'], [('93.184.216.34', 443)])
        self.assertIn('GET /release HTTP/1.1', evidence['requests'][0])
        self.assertIn('Host: docs.example.org', evidence['requests'][0])
        self.assertEqual(result['claim_truth'], 'NOT_VERIFIED')

    def test_truncated_content_length_denied_real_tls(self):
        # Real HTTPResponse must not turn a short TLS body into a signed
        # complete-source capture when server closes before Content-Length.
        data=(b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n'
              b'Content-Length: 99\r\nConnection: close\r\n\r\nshort')
        with self.assertRaisesRegex(module.CaptureDenied,'INCOMPLETE_RESPONSE_BODY'):
            self.exchange('docs.example.org', server_payload=data)

    def test_valid_chunked_response_real_tls(self):
        data=(b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n'
              b'Transfer-Encoding: chunked\r\nConnection: close\r\n\r\n'
              b'5\r\nHello\r\n0\r\n\r\n')
        receipt, _ = self.exchange('docs.example.org', server_payload=data)
        self.assertEqual(receipt['excerpt'],'Hello')
        self.assertEqual(receipt['full_bytes'],5)

    def test_unframed_close_cannot_prove_body_completion_real_tls(self):
        # Legitimate TLS hostname/certificate but no HTTP length or terminal
        # chunk: RFC 9112 6.3 cannot distinguish success from truncation.
        data=(b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n'
              b'Connection: close\r\n\r\npartial')
        with self.assertRaisesRegex(module.CaptureDenied,
                                    'UNVERIFIABLE_BODY_COMPLETION'):
            self.exchange('docs.example.org', server_payload=data)

    def test_wrong_hostname_certificate_rejected(self):
        with self.assertRaisesRegex(module.CaptureDenied, 'NETWORK_OR_TLS_FAILED'):
            self.exchange('wrong.example.org')


if __name__ == '__main__':
    unittest.main()
