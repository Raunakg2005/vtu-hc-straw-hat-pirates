"""Published resource estimates for breaking public-key cryptography with Shor's algorithm.

Every number here comes from a cited paper; nothing is extrapolated silently.

RSA (n = modulus bits):
  * Gidney 2025, arXiv:2505.15917 — RSA-2048 only: 1,399 logical qubits, 6.5e9 Toffoli
    gates, < 1 million noisy qubits, < 1 week. No formula for other sizes.
  * Gidney & Ekera 2019, arXiv:1905.09749 — formulas from the abstract:
    3n + 0.002 n lg n logical qubits, 0.3 n^3 + 0.0005 n^3 lg n Toffoli gates
    (RSA-2048: ~6,190 logical qubits, ~2.6e9 Toffoli; 20 million noisy qubits, 8 hours).
Elliptic curves (n = field bits):
  * Roetteler, Naehrig, Svore & Lauter 2017, arXiv:1706.06752 — upper bounds:
    9n + 2 ceil(lg n) + 10 logical qubits, 448 n^3 lg n + 4090 n^3 Toffoli gates
    (P-256: 2,330 logical qubits, ~1.3e11 Toffoli).
"""

from math import ceil, log2

SOURCES = {
    "gidney2025": {
        "label": "Gidney 2025 — RSA-2048 under 1M noisy qubits",
        "url": "https://arxiv.org/abs/2505.15917",
    },
    "gidney_ekera2019": {
        "label": "Gidney & Ekerå 2019 — RSA in 8 hours with 20M noisy qubits",
        "url": "https://arxiv.org/abs/1905.09749",
    },
    "roetteler2017": {
        "label": "Roetteler et al. 2017 — elliptic-curve discrete logs",
        "url": "https://arxiv.org/abs/1706.06752",
    },
}

RSA_SOURCES = ("gidney2025", "gidney_ekera2019")


def rsa_requirements(bits: int, source: str = "gidney2025"):
    """Logical qubits and Toffoli count to factor an RSA modulus, or None if not covered."""
    if source == "gidney2025":
        if bits != 2048:
            return None  # the paper only treats n = 2048
        return {"logical_qubits": 1399, "toffoli": 6.5e9, "physical_qubits": 1_000_000,
                "runtime": "< 1 week", "source": "gidney2025"}
    if source == "gidney_ekera2019":
        n, lg = bits, log2(bits)
        return {"logical_qubits": round(3 * n + 0.002 * n * lg),
                "toffoli": 0.3 * n**3 + 0.0005 * n**3 * lg,
                "physical_qubits": 20_000_000 if bits == 2048 else None,
                "runtime": "8 hours" if bits == 2048 else None, "source": "gidney_ekera2019"}
    raise ValueError(source)


def ecc_requirements(bits: int):
    """Roetteler et al. 2017 upper bounds for an elliptic curve over an n-bit prime field."""
    n = bits
    return {"logical_qubits": 9 * n + 2 * ceil(log2(n)) + 10,
            "toffoli": 448 * n**3 * log2(n) + 4090 * n**3,
            "physical_qubits": None, "runtime": None, "source": "roetteler2017"}


def requirements_for(algorithm_size, rsa_source: str = "gidney2025"):
    """algorithm_size is catalog.size_parameter(name): ('rsa', bits) or ('ecc', bits)."""
    if not algorithm_size:
        return None
    kind, bits = algorithm_size
    if kind == "rsa":
        req = rsa_requirements(bits, rsa_source)
        if req is None and rsa_source == "gidney2025":
            req = rsa_requirements(bits, "gidney_ekera2019")  # fall back to the formula
        return req
    return ecc_requirements(bits)
