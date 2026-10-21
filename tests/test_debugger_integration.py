"""quantum-debugger as an independent second simulator and a step-through view of the attacks."""

import pytest
from qiskit import QuantumCircuit

from qday.quantum import debug
from qday.quantum.grover import grover_key_search_circuit, theoretical_success, toy_encrypt
from qday.quantum.shor import order_finding_circuit

pytest.importorskip("quantum_debugger")


def test_qubit_order_matches_qiskit():
    qc = QuantumCircuit(3)
    qc.x(0)
    qc.h(2)
    result = debug.cross_check(qc)
    assert result["agree"] and result["fidelity"] == pytest.approx(1.0)


@pytest.mark.parametrize("a", [2, 4, 7, 8, 11, 13, 14])
@pytest.mark.parametrize("n_count", [3, 4])
def test_shor_n15_agrees_with_qiskit_for_every_base(a, n_count):
    result = debug.cross_check(order_finding_circuit(a, 15, n_count))
    assert result["agree"], result
    assert result["qubits"] == n_count + 4


@pytest.mark.parametrize("key", range(8))
@pytest.mark.parametrize("iterations", [0, 1, 2, 3])
def test_grover_3bit_agrees_with_qiskit_for_every_key(key, iterations):
    plaintext = 5
    circuit = grover_key_search_circuit(plaintext, toy_encrypt(plaintext, key, 3), iterations, 3)
    assert debug.cross_check(circuit)["agree"]


@pytest.mark.parametrize("key", [0, 6, 11, 15])
def test_grover_4bit_agrees_with_qiskit(key):
    circuit = grover_key_search_circuit(9, toy_encrypt(9, key, 4), 3, 4)
    assert debug.cross_check(circuit)["agree"]


def test_conversion_refuses_to_drop_gates(monkeypatch):
    from quantum_debugger.integrations import QiskitAdapter

    real = QiskitAdapter.from_qiskit

    def lossy(circuit):
        converted = real(circuit)
        converted.gates.pop()
        return converted

    monkeypatch.setattr(QiskitAdapter, "from_qiskit", lossy)
    with pytest.raises(debug.UnsupportedCircuit, match="dropped"):
        debug.to_debugger(order_finding_circuit(7, 15, 3))


@pytest.mark.parametrize("key", range(8))
def test_grover_trace_matches_the_sin_squared_law(key):
    trace = debug.grover_trace(plaintext=5, key=key, iterations=3, n_bits=3)
    assert trace["after_iteration"] == pytest.approx([theoretical_success(i, 3) for i in range(4)], abs=1e-9)
    assert trace["after_iteration"] == pytest.approx(trace["theory"], abs=1e-9)


@pytest.mark.parametrize("key", [3, 12])
def test_grover_trace_4bit_peaks_at_three_iterations(key):
    trace = debug.grover_trace(plaintext=9, key=key, iterations=4, n_bits=4)
    best = max(range(5), key=trace["after_iteration"].__getitem__)
    assert best == 3 and trace["after_iteration"][3] > 0.96


def test_grover_trace_shape():
    trace = debug.grover_trace(plaintext=5, key=6, iterations=2, n_bits=3)
    labels = [m["label"] for m in trace["markers"]]
    assert labels == ["Hadamards", "Oracle 1", "Diffuser 1", "Oracle 2", "Diffuser 2"]
    assert trace["steps"] == list(range(len(trace["p_key"])))
    assert trace["markers"][-1]["step"] == trace["steps"][-1]
    assert all(0.0 <= p <= 1.0 + 1e-12 for p in trace["p_key"])
    assert trace["ciphertext"] == toy_encrypt(5, 6, 3)


def test_grover_trace_with_zero_iterations_is_uniform():
    trace = debug.grover_trace(plaintext=1, key=4, iterations=0, n_bits=3)
    assert trace["after_iteration"] == pytest.approx([1 / 8])


def test_oracle_flips_only_the_key_sign_and_diffuser_reflects_about_the_mean():
    trace = debug.grover_trace(plaintext=5, key=6, iterations=3, n_bits=3)
    stops = trace["markers"]
    for before, oracle_stop, diffuser_stop in zip(stops[0::2], stops[1::2], stops[2::2], strict=False):
        a, o, d = before["amplitudes"], oracle_stop["amplitudes"], diffuser_stop["amplitudes"]
        # oracle: same magnitudes, the key's sign flipped relative to the rest
        assert [abs(x) for x in o] == pytest.approx([abs(x) for x in a], abs=1e-9)
        assert o[6] * o[0] == pytest.approx(-a[6] * a[0], abs=1e-9)
        # diffuser: inversion about the mean, up to the circuit's overall sign
        mean = sum(o) / len(o)
        reflected = [2 * mean - x for x in o]
        assert [abs(x) for x in d] == pytest.approx([abs(x) for x in reflected], abs=1e-9)


def test_amplitudes_have_unit_norm_and_uniform_start():
    trace = debug.grover_trace(plaintext=2, key=3, iterations=2, n_bits=4)
    for stop in trace["markers"]:
        assert sum(x * x for x in stop["amplitudes"]) == pytest.approx(1.0, abs=1e-9)
    assert trace["markers"][0]["amplitudes"] == pytest.approx([0.25] * 16, abs=1e-9)
