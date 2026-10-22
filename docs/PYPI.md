# qday-time-machine

[![PyPI](https://img.shields.io/pypi/v/qday-time-machine)](https://pypi.org/project/qday-time-machine/)
[![Python](https://img.shields.io/pypi/pyversions/qday-time-machine)](https://pypi.org/project/qday-time-machine/)
[![License: MIT](https://img.shields.io/pypi/l/qday-time-machine)](https://github.com/vtu-qiskit-fall-fest-2026/vtu-hc-straw-hat-pirates/blob/main/LICENSE)
[![CI](https://github.com/vtu-qiskit-fall-fest-2026/vtu-hc-straw-hat-pirates/actions/workflows/ci.yml/badge.svg)](https://github.com/vtu-qiskit-fall-fest-2026/vtu-hc-straw-hat-pirates/actions/workflows/ci.yml)

**Find the cryptography a quantum computer will break, see *when* it breaks, and get the post-quantum fix.**

A large quantum computer running Shor's algorithm will break the RSA and elliptic-curve cryptography behind today's
logins, payments and signatures, and attackers can record encrypted traffic now to decrypt it later. `qday` tells
you **which of your systems break first, in what year, and whether the data you send today is already at risk**,
then gives you the replacement.

![Q-Day Time Machine: each ring is one year on IBM's quantum roadmap, green while safe and pink once breakable](https://raw.githubusercontent.com/vtu-qiskit-fall-fest-2026/vtu-hc-straw-hat-pirates/main/docs/screenshots/landing.jpg)

**[Documentation](https://qday-time-machine.readthedocs.io/)** ·
**[Demo video, with a technical deep-dive](https://youtu.be/nhXP6QLFjoU)** ·
**[Source, dashboard and hardware results](https://github.com/vtu-qiskit-fall-fest-2026/vtu-hc-straw-hat-pirates)**

## Features

- **Scan** websites (certificate, issuing CA, key-exchange group, cipher) and source code in eight languages
  (Python, JavaScript, TypeScript, Java, Go, Kotlin, Rust and config files) for quantum-vulnerable cryptography.
  Detects the hybrid post-quantum TLS group `X25519MLKEM768`.
- **Inventory** everything as a **CycloneDX 1.6 cryptography bill of materials (CBOM)**.
- **Forecast** a break year for each algorithm by comparing published attack costs (logical qubits **and** gate
  counts) with IBM's fault-tolerant quantum roadmap.
- **Prioritise** with Mosca's inequality: critical, high, medium or safe, with the reason and the replacement.
- **Gate CI:** `--fail-on critical` exits with code 1, so a pull request that adds RSA or ECDSA fails.
- **Prove it:** scaled-down Shor (factors 15 and 21) and Grover attacks in Qiskit, on simulators or real IBM
  quantum computers.
- **Migrate:** a working hybrid X25519 + ML-KEM-768 handshake (NIST FIPS 203) and ML-DSA-65 signatures (FIPS 204).

## Install

```bash
pip install qday-time-machine
```

Python 3.11 or newer. Install the OpenSSL 3.x command-line tool too, so website scans can report the negotiated
key-exchange group.

## Quick start

Scan a code base:

```text
$ qday scan --path ./src
critical  RSA-2048       payments.py:8     breaks 2037  fix: ML-KEM-768 (encryption) / ML-DSA-65 (signatures)
critical  MD5            payments.py:18    breaks -     fix: SHA-256
high      ECDSA-P-256    server.js:3       breaks 2042  fix: ML-DSA-65
medium    AES-128        payments.py:10    breaks -     fix: AES-256
```

Scan a website and a folder together, and export a CBOM:

```bash
qday scan --host example.com --path ./src
qday cbom --host example.com --path ./src -o cbom.json
```

Ask when an algorithm breaks:

```text
$ qday forecast RSA-2048
{ "logical_qubits": 1399, "toffoli": 6500000000.0, "first_break_year": 2037, ... }
```

Run the attacks and the post-quantum handshake:

```bash
qday shor --N 15 --a 7          # factors 15 = 3 x 5 on the Qiskit Aer simulator
qday grover --bits 3 --secret 6 # recovers the secret key
qday pqc                        # hybrid X25519 + ML-KEM-768 key exchange
qday shor --backend ibm_kingston  # on real IBM hardware (needs an IBM Quantum API key)
```

### Commands

| Command | What it does |
| :--- | :--- |
| `qday scan` | Findings with risk level, break year and the fix. Options: `--host` (repeatable), `--path`, `--fail-on {medium,high,critical}`, `--json`, `--scenario {trend,roadmap}`, `--shelf-life`, `--migration` |
| `qday cbom` | CycloneDX 1.6 CBOM: `--host`, `--path`, `-o FILE` |
| `qday forecast ALGORITHM` | What an attack needs and the first break year, e.g. `RSA-2048`, `ECDSA-P-256` |
| `qday shor` | Shor's order finding: `--N {15,21}`, `--a`, `--backend` |
| `qday grover` | Grover key search: `--bits {3,4}`, `--secret`, `--backend` |
| `qday pqc` | Hybrid post-quantum handshake |

Exit codes: `0` ok, `1` a finding at or above `--fail-on`, `2` invalid input or every target failed.

## Use it in CI

```yaml
# .github/workflows/quantum-safe.yml
- run: pip install qday-time-machine
- run: qday scan --path . --fail-on critical
```

## Python API

```python
from qday.scanner.code import scan_code
from qday.forecast.risk import assess_all
from qday.scanner.cbom import build_cbom

assets = scan_code("./src")["assets"]
for finding in assess_all(assets, migration_years=3, shelf_life=10):
    print(finding["risk"], finding["algorithm"], finding["break_year"], finding["replacement"])
cbom = build_cbom(assets, target="my-service")   # a CycloneDX 1.6 dict
```

## How the forecast works

A **break year** is the first year IBM's roadmap provides both the logical qubits and the operations a published
attack needs: Gidney 2025 for RSA-2048 (1,399 logical qubits, 6.5 × 10⁹ Toffoli gates) and Roetteler et al. 2017
for elliptic curves. **Risk** follows Mosca's inequality: if data must stay secret for *x* years and migrating takes
*y*, it is already at risk when *x + y* exceeds the years left before the break. After 2033 the default `trend`
scenario is an explicit extrapolation; `--scenario roadmap` uses IBM's published roadmap only.

## Validated on IBM quantum hardware

The attacks were run on **ibm_fez, ibm_kingston and ibm_marrakesh**: 45 / 45 validation tests passed, and Shor
passed 24 / 24 tests with pass rules fixed in code before the runs. From those runs we measured an error of about
3 × 10⁻³ per two-qubit gate on the best qubits, which means breaking RSA-2048 on today's hardware would take about
4 million physical qubits rather than the published estimate's under 1 million.
[Full results and job IDs](https://github.com/vtu-qiskit-fall-fest-2026/vtu-hc-straw-hat-pirates/blob/main/docs/RESULTS.md).

![Shor's algorithm factoring 15 on ibm_marrakesh](https://raw.githubusercontent.com/vtu-qiskit-fall-fest-2026/vtu-hc-straw-hat-pirates/main/docs/screenshots/hardware-proof.jpg)

## Limitations

The Shor and Grover attacks break toy instances (N = 15 and 21, 3–4-bit keys), not real keys. Break years rest on
published estimates and IBM's stated roadmap. The code scanner is pattern-based: findings are leads to review, not
proof that the code path is reachable. Only scan systems you own or are authorised to test.

## About

Built by **Team Straw Hat Pirates** (Raunak Kumar Gupta, Krish Jain) for the VTU-QFF Hackathon, Qiskit Fall Fest
2026. Uses Qiskit, Qiskit Aer, Qiskit IBM Runtime, [quantum-debugger](https://pypi.org/project/quantum-debugger/),
cryptography, kyber-py and dilithium-py. MIT licensed.
