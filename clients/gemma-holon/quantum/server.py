"""
AEGIS Gemma Holon — Quantum purity barrier server.
Receives prompts from Cloudflare tunnel, runs PennyLane variational circuit,
enforces Softplus purity safety barrier, returns constitutional metrics.

Requires: pennylane==0.39.0, torch==2.2.0, flask
Run: python server.py  (binds to 127.0.0.1:5000)
Tunnel: cloudflared to expose publicly with CF Zero Trust headers.

Epistemic tier: T2
"""
import os
import torch
import pennylane as qml
from flask import Flask, request, jsonify

NUM_QUBITS = 4
dev = qml.device("default.qubit", wires=NUM_QUBITS)


@qml.qnode(dev, interface="torch", diff_method="parameter-shift")
def evaluate_quantum_objective(theta):
    for i in range(NUM_QUBITS):
        qml.RX(theta[i], wires=i)
    for i in range(NUM_QUBITS):
        qml.CNOT(wires=[i, (i + 1) % NUM_QUBITS])
    for i in range(NUM_QUBITS):
        qml.RY(theta[i + NUM_QUBITS], wires=i)
    return qml.expval(qml.PauliZ(0))


@qml.qnode(dev, interface="torch", diff_method="parameter-shift")
def evaluate_quantum_state(theta):
    for i in range(NUM_QUBITS):
        qml.RX(theta[i], wires=i)
    for i in range(NUM_QUBITS):
        qml.CNOT(wires=[i, (i + 1) % NUM_QUBITS])
    for i in range(NUM_QUBITS):
        qml.RY(theta[i + NUM_QUBITS], wires=i)
    return qml.state()


class RigorousAegisController:
    """Continuous Softplus purity safety barrier — constitutional analog of martingale."""

    def __init__(self, p_min: float = 0.65, mu: float = 0.5, epsilon: float = 0.02):
        self._p_min = p_min
        self._mu = mu
        self._epsilon = epsilon

    def compute_average_subsystem_purity_loss(self, state_vector):
        rho = torch.outer(state_vector, torch.conj(state_vector))
        purities = []
        for i in range(NUM_QUBITS):
            env_wires = [j for j in range(NUM_QUBITS) if j != i]
            rho_i = qml.math.partial_trace(rho, indices=env_wires)
            purity_i = torch.real(torch.trace(torch.matmul(rho_i, rho_i)))
            purities.append(purity_i)
        avg_purity = torch.stack(purities).mean()
        h = avg_purity - self._p_min
        barrier = self._mu * self._epsilon * torch.log(1.0 + torch.exp(-h / self._epsilon))
        return barrier, avg_purity


app = Flask(__name__)
controller = RigorousAegisController()
system_weights = torch.tensor([0.2] * (NUM_QUBITS * 2), dtype=torch.float64, requires_grad=True)
optimizer = torch.optim.Adam([system_weights], lr=0.05)


@app.route("/trigger-quantum", methods=["POST"])
def handle_trigger():
    data = request.json or {}
    prompt = data.get("prompt", "")

    optimizer.zero_grad()
    l_q = evaluate_quantum_objective(system_weights)
    psi = evaluate_quantum_state(system_weights)
    l_a, purity = controller.compute_average_subsystem_purity_loss(psi)
    loss = l_q + l_a
    loss.backward()
    optimizer.step()

    return jsonify({
        "status": "Authorized & Executed",
        "mobile_context_received": str(prompt),
        "quantum_loss": float(l_q.item()),
        "barrier_loss": float(l_a.item()),
        "average_subsystem_purity": float(purity.item()),
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
