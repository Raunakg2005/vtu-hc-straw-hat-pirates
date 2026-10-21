"""Live checks against the team's own public sites. Opt-in: `pytest -m network`."""

import pytest

from qday.scanner.tls import scan_tls

pytestmark = pytest.mark.network

SITES = ["quantyxio.cloud"]


@pytest.mark.parametrize("host", SITES)
def test_live_site_uses_hybrid_post_quantum_key_exchange(host):
    assert scan_tls(host)["key_exchange_group"] == "X25519MLKEM768"


@pytest.mark.parametrize("host", SITES)
def test_live_site_certificate_is_still_quantum_vulnerable(host):
    profile = scan_tls(host)
    assert profile["certificate_key"].startswith("ECDSA")
    assert profile["tls_version"] == "TLSv1.3"
