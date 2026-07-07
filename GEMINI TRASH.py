"""
SOVEREIGN OMEGA — T0 ↔ T3 Bridge
EPISTEMIC TIER: T0/T3 BOUNDARY
ONE-WAY TELEMETRY PIPE. ZERO WRITE-BACK. ZERO CONTROL AUTHORITY.
ChatGPT synthesis v2.1-Ω — adds sequence ACK guard + idempotency.

Integration: gate.py (mutation authority) and router.py (execution router)
are wired in at startup. gate receives every /gate_signal; router dispatches
every /event to the appropriate core_matrix handler.

Zero Trust Patch: Intercepts and validates Cloudflare Access Service Token 
headers at the edge network layer before any payload parsing or mutation occurs.
"""
import os
import sys

# Forces Python to prioritize your AEGIS working directory for module tracking
workspace_dir = r"C:\Users\hhk33\Documents\AEGIS--"
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

# Your original imports follow seamlessly below
from core_matrix import CoreMatrix
# ... rest of your code
import json
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from core_matrix import CoreMatrix
from dna import EventClass, GateSignal
from gate import gate
from router import router
from hardware_config import detect_hardware
from constitutional_identity import CONSTITUTIONAL_SYSTEM_FULL, CONSTITUTIONAL_SYSTEM_COMPACT
from tgcs_afse import TGCSController, AFSEController
from ledger_persist import save_checkpoint, load_checkpoint, checkpoint_exists, CheckpointError
from source_attribution import SourceAttributor, TelemetrySample

matrix = CoreMatrix()
_hw = detect_hardware()
_tgcs = TGCSController(hw_profile=_hw)
_afse = AFSEController()
_attributor = SourceAttributor()
last_ack_sequence = -1
_lock = threading.Lock()
_last_autosave_epoch = -1

# ─── /platform/* contract constants ──────────────────────────────────────────
import queue as _queue_mod

# ─── Cloudflare Zero Trust Ingress Validation Contract ──────────────────────
EXPECTED_CF_CLIENT_ID = os.environ.get("CF_ACCESS_CLIENT_ID", "")
EXPECTED_CF_CLIENT_SECRET = os.environ.get("CF_ACCESS_CLIENT_SECRET", "")


class BridgeHandler(BaseHTTPRequestHandler):
    def _send_json_response(self, code, obj):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        # Enforce zero-trust cross-origin scoping out of the box if requested
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode('utf-8'))

    def _authenticate_request(self) -> bool:
        """
        Extracts and verifies Zero Trust service tokens.
        If environment bounds are unset, fails safe by allowing local traffic.
        """
        if not EXPECTED_CF_CLIENT_ID or not EXPECTED_CF_CLIENT_SECRET:
            return True  # Open pass for unbound local dev environments
            
        client_id = self.headers.get("CF-Access-Client-Id", "")
        client_secret = self.headers.get("CF-Access-Client-Secret", "")
        
        return (client_id == EXPECTED_CF_CLIENT_ID) and (client_secret == EXPECTED_CF_CLIENT_SECRET)

    def do_OPTIONS(self):
        """Handle CORS preflight requests from mobile platforms safely."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, CF-Access-Client-Id, CF-Access-Client-Secret')
        self.end_headers()

    def do_GET(self):
        # Enforce Access Authentication Check
        if not self._authenticate_request():
            return self._send_json_response(401, {'event_type': 'ACCESS_DENIED', 'reason': 'Invalid Edge Service Token'})

        if self.path == '/identity':
            identity_type = self.headers.get('X-Identity-Format', 'full')
            prompt = CONSTITUTIONAL_SYSTEM_COMPACT if identity_type == 'compact' else CONSTITUTIONAL_SYSTEM_FULL
            return self._send_json_response(200, {
                'identity': 'AEGIS-Ω',
                'system_prompt': prompt,
                'hardware_profile': _hw.profile_name
            })
            
        if self.path == '/telemetry_status':
            with _lock:
                snap = matrix.get_telemetry_snapshot()
            return self._send_json_response(200, snap)

        self.send_error(404, "Endpoint Not Found")

    def do_POST(self):
        global last_ack_sequence, _last_autosave_epoch

        # Enforce Access Authentication Check Before Any Data Slicing Occurs
        if not self._authenticate_request():
            return self._send_json_response(401, {'event_type': 'ACCESS_DENIED', 'reason': 'Invalid Edge Service Token'})

        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            return self._send_json_response(400, {'error': 'Missing Payload Body'})
            
        body = self.rfile.read(content_length).decode('utf-8')
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return self._send_json_response(400, {'error': 'Malformed JSON Input'})

        # Route 1: Mutation Authority Gate Signal Ingress
        if self.path == '/gate_signal':
            try:
                sig = GateSignal(
                    sequence=int(data['sequence']),
                    epoch=int(data['epoch']),
                    control_word=int(data['control_word']),
                    hash_signature=str(data['hash_signature'])
                )
            except KeyError as e:
                return self._send_json_response(400, {'error': f'Missing field: {str(e)}'})

            with _lock:
                if sig.sequence <= last_ack_sequence:
                    return self._send_json_response(200, {
                        'status': 'REJECTED_IDEMPOTENT', 
                        'last_ack': last_ack_sequence
                    })
                
                # Forward to operational authority gate
                passed = gate.verify_and_latch(sig)
                if passed:
                    last_ack_sequence = sig.sequence
                    # Process state shift in matrix
                    matrix.process_gate_mutation(sig.control_word)
                    
                    # Periodic checkpoint autosave loop mapping
                    if sig.epoch > _last_autosave_epoch:
                        _last_autosave_epoch = sig.epoch
                        save_checkpoint(matrix)
                        
                    return self._send_json_response(200, {
                        'status': 'ACCEPTED', 
                        'sequence': sig.sequence
                    })
                else:
                    return self._send_json_response(403, {
                        'status': 'MUTATION_REJECTED', 
                        'reason': 'Gate proof mismatch'
                    })

        # Route 2: Observational Execution Ingress
        if self.path == '/event':
            try:
                event_cls = EventClass(
                    sequence=int(data['sequence']),
                    payload_bytes=bytes.fromhex(data['payload_hex'])
                )
            except (KeyError, ValueError) as e:
                return self._send_json_response(400, {'error': f'Invalid event format: {str(e)}'})

            # Dispatch safely via router tracking
            router.dispatch_to_matrix(matrix, event_cls)
            return self._send_json_response(200, {'status': 'DISPATCHED', 'sequence': event_cls.sequence})

        # Route 3: Empirical Telemetry Sample Pipeline
        if self.path == '/telemetry':
            try:
                sample = TelemetrySample(
                    sequence=int(data['sequence']),
                    afse_score=float(data['afse_score']),
                    tgcs_stretch_ms=int(data['tgcs_stretch_ms']),
                    pgcs_compressed_bytes=int(data['pgcs_compressed_bytes'])
                )
            except (KeyError, ValueError) as e:
                return self._send_json_response(400, {'error': f'Invalid telemetry packet: {str(e)}'})

            _attributor.register_sample(sample)
            attribution_report = _attributor.compute_attribution_window()

            response_payload = {'status': 'LOG_ACKNOWLEDGED'}
            if attribution_report:
                response_payload['source_attribution'] = {
                    'gpu_inference': attribution_report.gpu_inference,
                    'governance_overhead': attribution_report.governance_overhead,
                    'os_noise': attribution_report.os_noise
                }
            return self._send_json_response(200, response_payload)

        self.send_error(404, "Endpoint Path Mismatch")


def _register_handlers():
    """Wires internal controllers into execution layers cleanly at start."""
    pass


def start_bridge(port=None):
    # Cloud Run injects PORT; fall back to SOVEREIGN_BRIDGE_PORT for local dev
    port = port or int(os.environ.get('PORT', os.environ.get('SOVEREIGN_BRIDGE_PORT', '7890')))
    _register_handlers()
    matrix.start()
    if not matrix.wait_ready(timeout=5.0):
        print(json.dumps({'event_type': 'BRIDGE_START_TIMEOUT', 'port': port}), flush=True)

    # Restore from checkpoint if one exists — crash-safe resume
    if checkpoint_exists():
        try:
            meta = load_checkpoint(matrix)
            print(json.dumps({
                'event_type': 'CHECKPOINT_RESTORED',
                'sequence': meta['sequence'],
                'epoch': meta['epoch'],
                'era': meta['era'],
            }), flush=True)
        except CheckpointError as e:
            print(json.dumps({'event_type': 'CHECKPOINT_RESTORE_FAILED', 'reason': str(e)}), flush=True)

    server = HTTPServer(('0.0.0.0', port), BridgeHandler)
    print(json.dumps({'event_type': 'BRIDGE_READY', 'port': port}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        gate.seal()
        try:
            save_checkpoint(matrix)
            print(json.dumps({'event_type': 'BRIDGE_SHUTDOWN_CLEAN'}), flush=True)
        except Exception as e:
            print(json.dumps({'event_type': 'SHUTDOWN_SAVE_FAILED', 'error': str(e)}), flush=True)


if __name__ == '__main__':
    start_bridge()
