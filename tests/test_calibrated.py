"""Hardware-calibrated Q-Day: the noise estimator, the surface-code model and the numbers in the README."""

from math import log
from pathlib import Path

import numpy as np
import pytest

from qday.forecast import calibrated as c

RESULTS = Path(__file__).resolve().parent.parent / "results"
KEYS = [format(i, "03b") for i in range(8)]
IDEAL = {"110": 0.9453125, **{k: (1 - 0.9453125) / 7 for k in KEYS if k != "110"}}


def counts_from(probs, shots):
    return {k: round(probs.get(k, 0) * shots) for k in KEYS}


def mixed(f):
    return {k: f * IDEAL.get(k, 0) + (1 - f) / 8 for k in KEYS}


# ---------------------------------------------------------------- estimator
@pytest.mark.parametrize("f", [1.0, 0.8, 0.5, 0.2, 0.0])
def test_fidelity_recovers_the_mixing_weight(f):
    est, se = c.effective_fidelity(counts_from(mixed(f), 1_000_000), IDEAL, 3)
    assert est == pytest.approx(f, abs=2e-3)
    assert se >= 0


def test_fidelity_is_undefined_when_the_ideal_output_is_uniform():
    assert c.effective_fidelity({k: 10 for k in KEYS}, {k: 1 / 8 for k in KEYS}, 3) is None


def test_standard_error_shrinks_with_shots_and_covers_the_truth():
    rng = np.random.default_rng(7)
    probs = np.array([mixed(0.6)[k] for k in KEYS])
    hits, errors = 0, []
    for shots in (500, 4000, 32000):
        draws = [dict(zip(KEYS, rng.multinomial(shots, probs), strict=True)) for _ in range(200)]
        fits = [c.effective_fidelity(d, IDEAL, 3) for d in draws]
        hits += sum(abs(f - 0.6) <= 1.96 * se for f, se in fits)
        errors.append(np.mean([se for _, se in fits]))
    assert errors[0] > errors[1] > errors[2]
    assert hits / 600 > 0.9  # 95% intervals cover the true value


def test_error_per_gate_inverts_the_decay():
    eps, low, high = c.error_per_gate((1 - 3e-3) ** 143, 0.01, 143)
    assert eps == pytest.approx(3e-3, rel=1e-9)
    assert low <= eps <= high


@pytest.mark.parametrize("fidelity,gates", [(0.0, 143), (-0.1, 143), (0.5, 0)])
def test_error_per_gate_reports_no_signal(fidelity, gates):
    assert c.error_per_gate(fidelity, 0.01, gates) is None


# ---------------------------------------------------------------- surface code and RSA-2048
def test_above_threshold_no_distance_helps():
    assert c.surface_code(1e-2) is None
    assert c.surface_code(2e-2) is None


@pytest.mark.parametrize("eps", [1e-4, 1e-3, 3e-3, 6e-3, 9e-3])
def test_chosen_distance_meets_the_target_and_is_minimal(eps):
    code = c.surface_code(eps)
    target = 1 / (c.RSA_LOGICAL_QUBITS * c.RUNTIME_ROUNDS)

    def p_logical(d):
        return c.SURFACE_A * (eps / c.SURFACE_THRESHOLD) ** ((d + 1) / 2)

    assert p_logical(code["distance"]) <= target < p_logical(code["distance"] - 2)
    assert code["physical_qubits"] == 2 * code["distance"] ** 2 * c.RSA_LOGICAL_QUBITS


def test_worse_qubits_never_need_fewer_physical_qubits():
    sizes = [c.surface_code(e)["physical_qubits"] for e in np.linspace(1e-4, 9.9e-3, 40)]
    assert sizes == sorted(sizes)


def test_published_assumption_maps_to_the_published_estimate():
    f = c.rsa2048_at(c.PUBLISHED_ERROR_RATE)
    assert f["ratio_to_published"] == pytest.approx(1.0)
    assert f["physical_qubits"] == pytest.approx(1_000_000)
    assert f["max_eps_without_qec"] == pytest.approx(log(2) / (6 * 6.5e9))


def test_rsa_above_threshold_has_no_qubit_estimate():
    f = c.rsa2048_at(0.02)
    assert not f["below_threshold"] and "physical_qubits" not in f
    assert c.describe(f).endswith("no code distance helps")


# ---------------------------------------------------------------- golden: the numbers quoted in the README
@pytest.fixture(scope="module")
def calibration():
    return c.calibrate(RESULTS)


def test_every_hardware_machine_has_qubits_near_3e_3(calibration):
    for name in ("ibm_fez", "ibm_kingston", "ibm_marrakesh"):
        m = calibration["machines"][name]
        assert m["hardware"]
        assert 2.5e-3 < m["best"] < 4e-3, name


def test_marrakesh_transpiler_placement_is_above_threshold(calibration):
    m = calibration["machines"]["ibm_marrakesh"]
    assert m["worst_qubits"] == [33, 34, 35]
    assert m["worst"] > c.SURFACE_THRESHOLD
    assert m["above_threshold"] >= 4
    assert m["best_qubits"] == [110, 111, 112]


def test_forecast_headline(calibration):
    best = calibration["forecast"]["best_measured"]
    assert best["eps"] == pytest.approx(3.06e-3, rel=0.02)
    assert best["distance"] == 55
    assert best["physical_qubits"] == pytest.approx(4.1e6, rel=0.03)
    assert 1e8 < best["improvement_needed_without_qec"] < 3e8
    median = calibration["forecast"]["median_measured"]
    assert median["physical_qubits"] == pytest.approx(7.7e6, rel=0.03)


def test_noise_model_is_more_optimistic_than_the_chip_it_models(calibration):
    assert calibration["machines"]["fake_marrakesh"]["median"] < calibration["machines"]["ibm_marrakesh"]["median"]
