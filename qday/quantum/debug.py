"""Look inside the attack circuits with quantum-debugger (https://pypi.org/project/quantum-debugger/).

Two uses:

1. Independent cross-check. Every Shor and Grover circuit is re-simulated, gate by gate, by
   quantum-debugger's own state-vector engine and compared with Qiskit's. Agreement means the ideal
   distributions that the hardware tests are scored against do not rest on a single simulator.
2. Step-through. ``grover_trace`` replays the Grover attack one gate at a time with
   ``QuantumDebugger`` and records the probability of the secret key after every gate, so amplitude
   amplification can be watched as it happens, block by block (oracle, diffuser).
"""

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Statevector

from qday.quantum.grover import diffuser, oracle, theoretical_success, toy_encrypt

# Gates quantum-debugger's Qiskit adapter converts; anything else would be skipped, so it is rejected
SUPPORTED = ("h", "x", "y", "z", "s", "t", "cx", "cz", "cp", "swap", "ccx", "rx", "ry", "rz", "p")
AGREE_TOL = 1e-9


class UnsupportedCircuit(ValueError):
    """The circuit cannot be converted exactly."""


def to_debugger(circuit: QuantumCircuit):
    """Convert a Qiskit circuit to a quantum-debugger circuit, exactly or not at all."""
    from quantum_debugger.integrations import QiskitAdapter

    bare = circuit.remove_final_measurements(inplace=False)
    basic = transpile(bare, basis_gates=list(SUPPORTED), optimization_level=0)
    names = {inst.operation.name for inst in basic.data} - {"barrier"}
    if names - set(SUPPORTED):
        raise UnsupportedCircuit(f"gates quantum-debugger cannot run: {sorted(names - set(SUPPORTED))}")
    if any(inst.operation.name == "barrier" for inst in basic.data):
        basic.data = [inst for inst in basic.data if inst.operation.name != "barrier"]
    converted = QiskitAdapter.from_qiskit(basic)
    if len(converted.gates) != len(basic.data):  # the adapter skips what it does not know
        raise UnsupportedCircuit("conversion dropped gates")
    return converted, basic


def _start_state(num_qubits: int):
    """|0...0> on quantum-debugger's NumPy backend.

    The default backend ("auto") picks Numba or the GPU, which compiles kernels on first use (~8 s in a fresh
    server process) for no gain on circuits of a few qubits.
    """
    from quantum_debugger import QuantumState

    return QuantumState(num_qubits, backend="numpy")


def _final_state(qd_circuit, initial=None):
    from quantum_debugger import QuantumDebugger

    dbg = QuantumDebugger(qd_circuit, initial or _start_state(qd_circuit.num_qubits))
    dbg.run_to_end()
    return dbg.get_state()


def cross_check(circuit: QuantumCircuit) -> dict:
    """Simulate with quantum-debugger and Qiskit; report how far the output distributions differ."""
    qd_circuit, basic = to_debugger(circuit)
    p_qd = np.asarray(_final_state(qd_circuit).get_probabilities(), dtype=float)
    p_qk = Statevector(basic).probabilities()
    diff = float(np.max(np.abs(p_qd - p_qk)))
    fidelity = float(np.sum(np.sqrt(np.clip(p_qd, 0, None) * np.clip(p_qk, 0, None))) ** 2)
    return {"circuit": circuit.name, "qubits": basic.num_qubits, "gates": len(basic.data),
            "max_abs_diff": diff, "fidelity": fidelity, "agree": diff < AGREE_TOL}


def real_amplitudes(state, key: int, previous: list = None) -> list:
    """Amplitudes with the global phase removed, so Grover's sign flips show as negative bars.

    Each block carries an arbitrary global phase (the S-box synthesis adds one), so a convention is needed:
    after the Hadamards and every diffuser the secret key is drawn positive; after an oracle the other keys
    keep the signs they had at the previous stop (``previous``), so the oracle shows as a flip of the key alone.
    """
    vec = state.state_vector
    vec = np.asarray(vec.get() if hasattr(vec, "get") else vec, dtype=complex)  # CuPy arrays live on the GPU
    if previous is not None:
        others = np.arange(len(vec)) != key
        ref = np.sum(np.asarray(previous)[others] * vec[others])
    else:
        ref = vec[key] if abs(vec[key]) > 1e-9 else vec.sum()
    return (vec * np.exp(-1j * np.angle(ref))).real.tolist()


def grover_trace(plaintext: int, key: int, iterations: int, n_bits: int = 3) -> dict:
    """Step through a Grover key search with QuantumDebugger, recording P(secret key) after every gate.

    The circuit is replayed block by block (Hadamards, then oracle and diffuser per iteration), each block
    starting from the previous block's state, so the block boundaries in the trace are exact.
    """
    from quantum_debugger import QuantumDebugger

    ciphertext = toy_encrypt(plaintext, key, n_bits)
    hadamards = QuantumCircuit(n_bits, name="hadamards")
    hadamards.h(range(n_bits))
    blocks = [("Hadamards", hadamards)]
    for i in range(1, iterations + 1):
        blocks += [(f"Oracle {i}", oracle(plaintext, ciphertext, n_bits)), (f"Diffuser {i}", diffuser(n_bits))]

    steps, p_key, markers = [0], [1.0 if key == 0 else 0.0], []
    state = _start_state(n_bits)
    for label, block in blocks:
        qd_circuit, _ = to_debugger(block)
        dbg = QuantumDebugger(qd_circuit, state)
        while dbg.step():
            steps.append(steps[-1] + 1)
            p_key.append(float(dbg.current_state.get_probabilities()[key]))
        state = dbg.get_state()
        previous = markers[-1]["amplitudes"] if label.startswith("Oracle") else None
        markers.append({"label": label, "step": steps[-1], "p_key": p_key[-1],
                        "amplitudes": real_amplitudes(state, key, previous)})

    # iteration 0 is the state after the Hadamards; iteration i ends with diffuser i
    after_iteration = [markers[0]["p_key"]] + [m["p_key"] for m in markers if m["label"].startswith("Diffuser")]
    return {
        "n_bits": n_bits, "plaintext": plaintext, "key": key, "ciphertext": ciphertext, "iterations": iterations,
        "steps": steps, "p_key": p_key, "markers": markers,
        "after_iteration": after_iteration,
        "theory": [theoretical_success(i, n_bits) for i in range(iterations + 1)],
    }
