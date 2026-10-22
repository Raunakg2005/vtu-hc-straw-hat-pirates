"""Credential loading and backend plumbing, with no real keys and no network."""

import json

import pytest

from qday import config
from qday.quantum import runner
from qday.quantum.shor import order_finding_circuit


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    for var in ("IBM_QUANTUM_TOKEN", "IBM_QUANTUM_INSTANCE", "QDAY_ENV_FILE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)  # never read the developer's real .env
    return tmp_path


def write_env(path, text):
    path.write_text(text, encoding="utf8")
    return path


@pytest.mark.parametrize("text,token,instance", [
    ("IBM_QUANTUM_TOKEN=abc\nIBM_QUANTUM_INSTANCE=crn:1\n", "abc", "crn:1"),
    ('IBM_QUANTUM_TOKEN="quoted"\n', "quoted", None),
    ("IBM_QUANTUM_TOKEN='single'\n", "single", None),
    ("# comment\n\nIBM_QUANTUM_TOKEN = spaced \n", "spaced", None),
    ("IBM_QUANTUM_TOKEN=\nIBM_QUANTUM_INSTANCE=\n", None, None),
    ("NOT_A_PAIR\nIBM_QUANTUM_TOKEN=x=y\n", "x=y", None),
])
def test_env_file_parsing(clean_env, monkeypatch, text, token, instance):
    monkeypatch.setenv("QDAY_ENV_FILE", str(write_env(clean_env / "a.env", text)))
    assert config.load_credentials() == {"token": token, "instance": instance}


def test_project_dotenv_is_used_by_default(clean_env):
    write_env(clean_env / ".env", "IBM_QUANTUM_TOKEN=from-project\n")
    assert config.load_credentials()["token"] == "from-project"


def test_environment_variables_win_over_files(clean_env, monkeypatch):
    write_env(clean_env / ".env", "IBM_QUANTUM_TOKEN=from-file\n")
    monkeypatch.setenv("IBM_QUANTUM_TOKEN", "from-env")
    assert config.load_credentials()["token"] == "from-env"


def test_no_credentials_anywhere(clean_env):
    assert config.load_credentials() == {"token": None, "instance": None}


def test_missing_env_file_path_is_ignored(clean_env, monkeypatch):
    monkeypatch.setenv("QDAY_ENV_FILE", str(clean_env / "does-not-exist.env"))
    assert config.load_credentials()["token"] is None


class FakeService:
    calls = []

    def __init__(self, **kwargs):
        FakeService.calls.append(kwargs)


def test_runtime_service_uses_token(clean_env, monkeypatch):
    import qiskit_ibm_runtime
    FakeService.calls.clear()
    monkeypatch.setattr(qiskit_ibm_runtime, "QiskitRuntimeService", FakeService)
    monkeypatch.setenv("IBM_QUANTUM_TOKEN", "t0k3n")
    config.runtime_service()
    assert FakeService.calls[-1] == {"channel": "ibm_quantum_platform", "token": "t0k3n", "instance": None}


def test_runtime_service_falls_back_to_saved_account(clean_env, monkeypatch):
    import qiskit_ibm_runtime
    FakeService.calls.clear()
    monkeypatch.setattr(qiskit_ibm_runtime, "QiskitRuntimeService", FakeService)
    config.runtime_service()
    assert FakeService.calls[-1] == {}


def test_token_never_appears_in_repr_of_credentials(clean_env, monkeypatch):
    """The token is only ever returned to the caller, never printed or logged by config."""
    monkeypatch.setenv("IBM_QUANTUM_TOKEN", "super-secret")
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        config.load_credentials()
    assert "super-secret" not in buf.getvalue()


# ---------------------------------------------------------------- runner
@pytest.mark.parametrize("name", ["aer", "fake_marrakesh", "fake_fez", "fake_torino", "fake_brisbane"])
def test_local_backends_resolve(name):
    backend = runner.get_backend(name)
    assert not runner.is_hardware(backend)


@pytest.mark.parametrize("name", ["", "qasm_simulator", "fake_nowhere", "IBM_KINGSTON"])
def test_unknown_backend_rejected(name):
    with pytest.raises(ValueError):
        runner.get_backend(name)


def test_run_sampler_batches_circuits_in_one_job():
    res = runner.run_sampler([order_finding_circuit(7, 15, 3), order_finding_circuit(2, 15, 3)], "aer", shots=500)
    assert len(res["circuits"]) == 2 and not res["hardware"]
    assert all(sum(c["counts"].values()) == 500 for c in res["circuits"])


def test_run_sampler_can_return_the_job():
    job = runner.run_sampler([order_finding_circuit(7, 15, 3)], "aer", shots=100, wait=False)
    assert job.result()


def test_save_and_load_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "RESULTS_DIR", tmp_path / "results")
    path = runner.save_result({"backend": "x", "circuits": []}, "r.json")
    assert json.loads(open(path, encoding="utf8").read())["backend"] == "x"
    assert runner.load_result("r.json")["backend"] == "x"
    assert runner.load_result("missing.json") is None


def test_circuit_stats_counts_multi_qubit_gates():
    stats = runner.circuit_stats(order_finding_circuit(7, 15, 3))
    assert stats["two_qubit_gates"] > 0 and stats["num_qubits_used"] == 7
