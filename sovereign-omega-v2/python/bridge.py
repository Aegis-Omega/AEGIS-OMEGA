"""
SOVEREIGN OMEGA — T0 ↔ T3 Bridge
EPISTEMIC TIER: T0/T3 BOUNDARY
ONE-WAY TELEMETRY PIPE. ZERO WRITE-BACK. ZERO CONTROL AUTHORITY.
ChatGPT synthesis v2.1-Ω — adds sequence ACK guard + idempotency.

Integration: gate.py (mutation authority) and router.py (execution router)
are wired in at startup. gate receives every /gate_signal; router dispatches
every /event to the appropriate core_matrix handler.
"""
import json
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from core_matrix import CoreMatrix
from dna import EventClass, GateSignal
from gate import gate
from router import router
from hardware_config import detect_hardware
from tgcs_afse import TGCSController, AFSEController

matrix = CoreMatrix()
_hw = detect_hardware()
_tgcs = TGCSController(hw_profile=_hw)
_afse = AFSEController()
last_ack_sequence = -1
_lock = threading.Lock()


def _register_handlers() -> None:
    """Register core_matrix handlers in the execution router, then seal."""
    router.register(EventClass.GOVERNANCE,  lambda p, v, c, seq: matrix.process_event(p, v, c))
    router.register(EventClass.CALIBRATION, lambda p, v, c, seq: matrix.process_event(p, v, c))
    router.register(EventClass.TELEMETRY,   lambda p, v, c, seq: matrix.emit_vcg_telemetry())
    router.register(EventClass.EPOCH,       lambda p, v, c, seq: matrix.process_event(p, v, c))
    router.seal()


class BridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass  # suppress access log

    def do_POST(self):
        global last_ack_sequence
        length = int(self.headers.get('Content-Length', 0))
        data = json.loads(self.rfile.read(length)) if length else {}

        if self.path == '/gate_signal':
            seq = data.get('sequence', -1)
            accepted = data.get('accepted', False)
            proposal_id = data.get('proposal_id', '')
            lcb = float(data.get('lcb', 0.0))

            with _lock:
                if seq <= last_ack_sequence:
                    self._respond(400, {'status': 'REJECTED', 'reason': 'SEQUENCE_DESYNC'})
                    return
                last_ack_sequence = seq

            # Record signal in both gate (mutation authority) and matrix
            gate.record_signal(GateSignal(
                proposal_id=proposal_id,
                sequence=seq,
                accepted=accepted,
                lcb=lcb,
            ))
            matrix.receive_gate_signal(proposal_id, accepted, seq)
            self._respond(200, {'status': 'ACK', 'sequence': seq})

        elif self.path == '/event':
            payload  = bytes.fromhex(data.get('payload_hex', ''))
            verifier = bytes.fromhex(data.get('verifier_hex', '01'))
            context  = bytes.fromhex(data.get('context_hex', ''))
            result = router.route(payload, verifier, context)
            self._respond(200, result)

        elif self.path == '/inference':
            import subprocess, os
            binary = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'aegis-cl-psi', 'target', 'release', 'aegis_cl_psi'
            )
            if not os.path.exists(binary):
                self._respond(200, {'status': 'unavailable', 'reason': 'aegis-cl-psi binary not compiled'})
                return
            payload_bytes = json.dumps(data).encode()
            result = subprocess.run(
                [binary, '--json'],
                input=payload_bytes,
                capture_output=True,
                timeout=30,
            )
            try:
                out = json.loads(result.stdout)
            except Exception:
                out = {'status': 'error', 'stderr': result.stderr.decode()[:200]}
            self._respond(200, out)

        else:
            self._respond(404, {'error': 'NOT_FOUND'})

    def do_GET(self):
        if self.path == '/telemetry':
            telemetry = matrix.emit_vcg_telemetry()
            telemetry.update(gate.telemetry())
            telemetry.update(router.telemetry())
            # Layer B extended metrics — TGCS/AFSE wired here
            seq = int(telemetry['sequence'])
            tgcs_snap = _tgcs.regulate_cycle(seq)
            telemetry['tgcs_variance'] = tgcs_snap.run_variance
            telemetry['afse_r2'] = _afse.get_r2()
            telemetry['holonic_scaling_score'] = _afse.holonic_scaling_score()
            self._respond(200, telemetry)

        elif self.path == '/health':
            self._respond(200, {
                'status': 'OK',
                'last_ack_sequence': last_ack_sequence,
                'gate_sealed': gate.is_sealed,
                'router_sealed': router.is_sealed,
            })

        elif self.path == '/metrics':
            snap = matrix.emit_vcg_telemetry()
            pgcs_snap = matrix._pgcs.snapshot(snap['sequence'])
            gate_t = gate.telemetry()
            router_t = router.telemetry()

            lines = [
                '# HELP aegis_sequence Current event sequence number',
                '# TYPE aegis_sequence counter',
                f'aegis_sequence {snap["sequence"]}',
                '# HELP aegis_epoch Current epoch number',
                '# TYPE aegis_epoch counter',
                f'aegis_epoch {snap["epoch"]}',
                '# HELP aegis_vcg_error_avg Average VCG error (Q16.16 normalized)',
                '# TYPE aegis_vcg_error_avg gauge',
                f'aegis_vcg_error_avg {snap["avg_vcg_error"]:.6f}',
                '# HELP aegis_drift_index Gradient anchor drift index D',
                '# TYPE aegis_drift_index gauge',
                f'aegis_drift_index {snap["drift_index"]:.6f}',
                '# HELP aegis_pgcs_disk_swap_bytes_in PGCS disk swap bytes in',
                '# TYPE aegis_pgcs_disk_swap_bytes_in counter',
                f'aegis_pgcs_disk_swap_bytes_in {pgcs_snap.disk_swap_bytes_in}',
                '# HELP aegis_pgcs_disk_swap_bytes_out PGCS disk swap bytes out',
                '# TYPE aegis_pgcs_disk_swap_bytes_out counter',
                f'aegis_pgcs_disk_swap_bytes_out {pgcs_snap.disk_swap_bytes_out}',
                '# HELP aegis_gate_acceptance_rate Gate signal acceptance rate',
                '# TYPE aegis_gate_acceptance_rate gauge',
                f'aegis_gate_acceptance_rate {gate_t["gate_acceptance_rate"]:.6f}',
                '# HELP aegis_gate_total_signals Total gate signals received',
                '# TYPE aegis_gate_total_signals counter',
                f'aegis_gate_total_signals {gate_t["gate_total_signals"]}',
                '# HELP aegis_router_total_events Total events routed',
                '# TYPE aegis_router_total_events counter',
                f'aegis_router_total_events {router_t["router_total_events"]}',
                '# HELP aegis_router_rejected Total events rejected',
                '# TYPE aegis_router_rejected counter',
                f'aegis_router_rejected {router_t["router_rejected"]}',
                '# HELP aegis_failsafe_corruption_count Epoch corruption count',
                '# TYPE aegis_failsafe_corruption_count counter',
                f'aegis_failsafe_corruption_count {snap["corruption_count"]}',
            ]
            body = ('\n'.join(lines) + '\n').encode()
            self.send_response(200)
            self._cors_headers()
            self.send_header('Content-Type', 'text/plain; version=0.0.4')
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)
            return

        elif self.path == '/telemetry/stream':
            # Cycles 31–35: Server-Sent Events stream for cockpit real-time dashboard.
            # Emits a telemetry snapshot every 5 seconds. Compatible with EventSource API.
            snap = matrix.emit_vcg_telemetry()
            data = json.dumps(snap)
            self.send_response(200)
            self._cors_headers()
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('X-Accel-Buffering', 'no')
            self.end_headers()
            try:
                import time as _time
                while True:
                    snap = matrix.emit_vcg_telemetry()
                    gate_t = gate.telemetry()
                    payload = {**snap, 'gate': gate_t}
                    line = f'data: {json.dumps(payload)}\n\n'.encode()
                    self.wfile.write(line)
                    self.wfile.flush()
                    _time.sleep(5)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        elif self.path == '/snapshot':
            # Cycles 36–40: Epoch state snapshot — returns current M1 representative sample.
            snap_bytes = matrix.get_epoch_snapshot()
            if snap_bytes is None:
                self._respond(503, {'error': 'SNAPSHOT_UNAVAILABLE'})
                return
            vcg = matrix.emit_vcg_telemetry()
            self._respond(200, {
                'snapshot_hex': snap_bytes.hex(),
                'snapshot_len': len(snap_bytes),
                'sequence': vcg['sequence'],
                'epoch': vcg['epoch'],
                'failsafe_state': vcg['failsafe_state'],
            })

        else:
            self._respond(404, {'error': 'NOT_FOUND'})

    def _cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def _respond(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self._cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)


def run_bridge(port=None):
    port = port or int(os.environ.get('SOVEREIGN_BRIDGE_PORT', '7890'))
    _register_handlers()
    matrix.start()
    if not matrix.wait_ready(timeout=5.0):
        print(json.dumps({'event_type': 'BRIDGE_START_TIMEOUT', 'port': port}), flush=True)
    server = HTTPServer(('127.0.0.1', port), BridgeHandler)
    print(json.dumps({'event_type': 'BRIDGE_READY', 'port': port}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        gate.seal()
        matrix.stop()


if __name__ == '__main__':
    run_bridge()
