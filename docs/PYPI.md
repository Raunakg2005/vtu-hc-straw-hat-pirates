# qday-time-machine

**Find the cryptography a quantum computer will break, see *when* it breaks, and get the fix.**

`qday` scans websites and source code for quantum-vulnerable cryptography, gives every finding a break year from
published attack costs against IBM's quantum roadmap, exports a CycloneDX 1.6 cryptography bill of materials, and
can fail a CI build on critical findings. It also runs scaled-down Shor and Grover attacks in Qiskit and a hybrid
post-quantum (ML-KEM + ML-DSA) handshake.

Built by Team Straw Hat Pirates for the VTU-QFF Hackathon, Qiskit Fall Fest 2026. The attacks were validated on
three IBM quantum computers (ibm_fez, ibm_kingston, ibm_marrakesh).

- **Demo (2 min):** https://youtu.be/8AHgcPisYlE
- **Source, dashboard and hardware results:** https://github.com/vtu-qiskit-fall-fest-2026/vtu-hc-straw-hat-pirates

## Install

```bash
pip install qday-time-machine
```

Requires Python 3.11+. Install the OpenSSL 3.x command-line tool too, so website scans can report the negotiated
key-exchange group.

## Use

```bash
qday scan --host example.com --path ./src     # findings, risk level, break year and the fix
qday scan --path ./src --fail-on critical     # exit code 1 on critical findings: a CI gate
qday cbom --path ./src -o cbom.json           # CycloneDX 1.6 cryptography bill of materials
qday forecast RSA-2048 --scenario roadmap     # what an attack needs, and the first break year
qday shor --N 15 --a 7                        # Shor's order finding (Qiskit Aer by default)
qday grover --bits 3 --secret 6               # Grover key search on a toy cipher
qday pqc                                      # hybrid X25519 + ML-KEM-768 handshake
```

Example:

```text
$ qday scan --path ./src
critical  RSA-2048               payments.py:8      breaks 2037  fix: ML-KEM-768 (encryption) / ML-DSA-65 (signatures)
critical  MD5                    payments.py:18     breaks -     fix: SHA-256
high      ECDSA-P-256            server.js:3        breaks 2042  fix: ML-DSA-65
medium    AES-128                payments.py:10     breaks -     fix: AES-256
```

Exit codes: `0` ok, `1` a finding at or above `--fail-on`, `2` invalid input or every target failed.

### In CI (GitHub Actions)

```yaml
- run: pip install qday-time-machine
- run: qday scan --path . --fail-on critical
```

## How the forecast works

A break year is the first year IBM's roadmap provides both the logical qubits and the operations a published
attack needs (Gidney 2025 for RSA-2048: 1,399 logical qubits and 6.5 × 10⁹ Toffoli gates; Roetteler et al. 2017
for elliptic curves). Risk levels follow Mosca's inequality: data that must stay secret longer than the time left
before the break, plus the time to migrate, is already at risk. After 2033 the default `trend` scenario is an
explicit extrapolation; `--scenario roadmap` uses IBM's published roadmap only.

## Python API

```python
from qday.scanner.code import scan_code
from qday.forecast.risk import assess_all
from qday.scanner.cbom import build_cbom

assets = scan_code("./src")["assets"]
for finding in assess_all(assets, migration_years=3, shelf_life=10):
    print(finding["risk"], finding["algorithm"], finding["break_year"], finding["replacement"])
cbom = build_cbom(assets, target="my-service")
```

## Limits

The Shor and Grover attacks break toy instances (N = 15 and 21, 3–4-bit keys), not real keys. The code scanner is
pattern-based: findings are leads to review. Only scan systems you own or are authorised to test.

## License

MIT
