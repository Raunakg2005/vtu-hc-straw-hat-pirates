# Q-Day Time Machine — User guide

How to install, run, use, configure and deploy the app. For how it is built, see
[ARCHITECTURE.md](ARCHITECTURE.md); for the hardware numbers, see [RESULTS.md](RESULTS.md).

- [Install](#install)
- [Run](#run)
- [Using the dashboard](#using-the-dashboard)
- [Command line](#command-line)
- [Reading the results](#reading-the-results)
- [Configuration](#configuration)
- [Running on IBM quantum hardware](#running-on-ibm-quantum-hardware)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

---

## Install

Requirements: **Python 3.11 or newer**, and the **OpenSSL 3.x** command-line tool on the `PATH` (the scanner uses
`openssl s_client` to read the negotiated key-exchange group; without it, website scans still work but may not
report the group).

```bash
git clone https://github.com/vtu-qiskit-fall-fest-2026/vtu-hc-straw-hat-pirates.git
cd vtu-hc-straw-hat-pirates
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .                   # installs the `qday` command
```

No IBM Quantum account is needed: the hardware results are saved in `results/`, and live attacks in the app run
on simulators.

## Run

```bash
python serve.py
```

| Address | What it is |
| :--- | :--- |
| http://localhost:8501/ | Landing page: the 3D year tunnel, results and links |
| http://localhost:8501/app/ | The dashboard (the **Launch the app** buttons go here) |

`serve.py` starts the dashboard as a background process on an internal port and serves both on one public port.
Stopping it stops both. Options:

| Option | Default | Meaning |
| :--- | :--- | :--- |
| `--host` | `127.0.0.1` | Interface to listen on. Use `0.0.0.0` on a server. |
| `--port` | `8501` | Public port for the landing page and dashboard |
| `--app-port` | `8502` | Internal port the dashboard listens on (not exposed) |

For development, run the dashboard on its own with `streamlit run app.py` (it then lives at
http://localhost:8501/ without the landing page). After editing `landing/landing.html`, run
`python landing/build.py` to regenerate `landing/index.html`, which is what `serve.py` serves.

---

## Using the dashboard

The dashboard has four steps as tabs, plus a Sources tab and a settings sidebar.

### 1 · Scan

Find the cryptography a system uses.

1. **Websites to scan:** one hostname per line (for example `example.com`). Only scan systems you own or are
   allowed to test. A URL is accepted; only its hostname is used.
2. **Code folder to scan:** a path to a project folder on the machine running the app.
3. Press **Scan now**. Fill in either field or both; nothing is scanned until you press the button.

No project handy? **Scan the built-in vulnerable sample app** scans `samples/legacy_app/`, which deliberately uses
RSA-2048, ECDSA, MD5, SHA-1 and AES-128.

Results:

- A headline: how many uses of cryptography were found, how many need fixing now, and the earliest break year.
- For websites using post-quantum key exchange (`X25519MLKEM768`), a green note that recorded traffic stays
  secret, and a warning if the certificate is still ECDSA or RSA, which a quantum computer could forge.
- Findings in three columns: **Fix now**, **Plan migration** and **Already safe**. Each card shows the algorithm,
  where it is used, when it breaks, why, and the replacement to use.
- **Technical details:** the full table of findings and websites, and **Download CBOM**, a CycloneDX 1.6
  cryptography bill of materials (JSON).

### 2 · Time Machine

Drag the year slider (2026–2050) to see, for that year:

- the best quantum computer on IBM's roadmap (Starling from 2029, Blue Jay from 2033, then the growth scenario);
- how many of your scanned algorithms a quantum attack could break, and how many are "one step away" (enough
  qubits, not yet enough operations);
- a chart of quantum computing power against what each attack needs; where the purple line rises above a pink
  line, that algorithm can be broken;
- **Harvest now, decrypt later:** which data sent today could be read before its shelf life ends;
- **Calibrated by our hardware runs:** the error rate we measured on IBM's machines and what it means for
  RSA-2048 (see [Reading the results](#reading-the-results)).

### 3 · Prove it

- **Hardware results:** Shor's algorithm factoring 15 on `ibm_marrakesh`, the 45-test validation suite on three
  IBM machines, and the strict suite with pre-registered pass rules. Expand the sections for every run.
- **Try it yourself:**
  - **Shor:** pick N (15 or 21) and a base a, choose *Ideal simulator* or *Noisy ibm_marrakesh copy* (a noise model
    of the real machine), and press **Run Shor**. N = 21 runs on the ideal simulator only (it needs ~6,500
    two-qubit gates). **Show the quantum circuit** draws it.
  - **Grover:** pick a 3- or 4-bit key size and a secret key, then **Run Grover**. The chart shows how often each
    key came out; the secret should stand out.
- **Inside the circuit:** step through the Grover attack with quantum-debugger. Choose how many iterations, then
  move **Stop after** through Hadamards → Oracle 1 → Diffuser 1 → … The left chart shows every key's amplitude:
  the oracle flips the secret key's sign, and the diffuser reflects every amplitude around the mean (dashed line).
  The right chart shows the key's probability after each iteration against the sin² law. The caption below confirms
  quantum-debugger and Qiskit agree on these circuits.

### 4 · Migrate

Runs a real hybrid **X25519 + ML-KEM-768** key exchange and compares **ML-DSA-65** signatures with RSA-2048 and
ECDSA P-256: key sizes, signature sizes, signing and verifying times, and whether a tampered message is rejected.
**Run the handshake again** repeats it with fresh keys.

### Sources

Every published estimate and roadmap figure the app uses, with links.

### Settings (sidebar)

Open the sidebar with the **Settings** button at the top left. These change the Time Machine and every risk level:

| Setting | Default | Meaning |
| :--- | :--- | :--- |
| How long must it stay secret? | 10 years | Mosca's *x*: the data's shelf life (payments ~7, medical records 30+) |
| How long would migrating take? | 3 years | Mosca's *y*: time to replace the cryptography everywhere |
| Growth after 2033 | Roadmap, then growth continues | Or *IBM roadmap only*: no extrapolation after Blue Jay |
| RSA-2048 cost estimate | Gidney 2025 | Or Gidney & Ekerå 2019 |

**Reset to defaults** restores all four. **← Home** returns to the landing page.

---

## Command line

The `qday` command does everything the Scan and Time Machine tabs do, plus the attacks, and fits into scripts and
CI.

```text
qday scan     [--host H]... [--path DIR] [--insecure] [--scenario S] [--rsa-source R]
              [--shelf-life YEARS] [--migration YEARS] [--json] [--fail-on LEVEL]
qday cbom     [--host H]... [--path DIR] [--insecure] [-o FILE] [--name NAME]
qday forecast ALGORITHM [--scenario S] [--rsa-source R]
qday shor     [--N 15|21] [--a A] [--counting N] [--backend B] [--shots N]
qday grover   [--bits 3|4] [--secret K] [--backend B] [--shots N]
qday pqc
```

| Option | Values | Default |
| :--- | :--- | :--- |
| `--host` | a hostname; repeat for several | — |
| `--scenario` | `trend`, `roadmap` | `trend` |
| `--rsa-source` | `gidney2025`, `gidney_ekera2019` | `gidney2025` |
| `--fail-on` | `medium`, `high`, `critical` | — |
| `--backend` | `aer` (ideal), `fake_marrakesh` (noise model), or an IBM machine such as `ibm_kingston` | `aer` |

**Exit codes:** `0` success; `1` a finding at or above `--fail-on`; `2` invalid input, or every target failed.

### Examples

Scan code and fail a CI build on critical findings:

```bash
qday scan --path ./src --fail-on critical
```

```text
critical  RSA-2048               payments.py:8                            breaks 2037  fix: ML-KEM-768 (encryption) / ML-DSA-65 (signatures)
critical  MD5                    payments.py:18                           breaks -     fix: SHA-256
high      ECDSA-P-256            payments.py:9                            breaks 2042  fix: ML-DSA-65
medium    AES-128                payments.py:10                           breaks -     fix: AES-256
9 findings
```

Export a CBOM for a website and a code folder:

```bash
qday cbom --host example.com --path ./src -o cbom.json
```

When does an algorithm break?

```bash
qday forecast RSA-2048 --scenario roadmap
```

```json
{
  "algorithm": "RSA-2048",
  "scenario": "roadmap",
  "logical_qubits": 1399,
  "toffoli": 6500000000.0,
  "physical_qubits": 1000000,
  "runtime": "< 1 week",
  "source": "gidney2025",
  "first_break_year": null
}
```

`first_break_year: null` means not breakable on IBM's published roadmap alone; with `--scenario trend` it is 2037.

Run the attacks:

```bash
qday shor --N 15 --a 7          # {"factors": [3, 5], "most_likely_order": 4, "success_probability": 0.74, ...}
qday grover --bits 3 --secret 6 # {"recovered_key": 6, "key_is_correct": true, "success_probability": 0.94, ...}
qday pqc                        # {"keys_match": true, "message_roundtrip": true, "session_key_bits": 256, ...}
```

### Using it in CI

```yaml
- run: pip install "git+https://github.com/vtu-qiskit-fall-fest-2026/vtu-hc-straw-hat-pirates.git"
- run: qday scan --path . --fail-on critical
```

---

## Reading the results

### Risk levels

| Level | When |
| :--- | :--- |
| **critical** | Already broken classically (MD5, SHA-1, …), **or** Shor-breakable and Mosca's inequality fails: for data that must stay secret, shelf life + migration time > years until the break; for signatures, migration time > years until forgery. |
| **high** | Shor-breakable within the scenario, but there is still time to migrate; or Shor-breakable with no published estimate for that key size. |
| **medium** | Grover halves its strength (AES-128 and similar: move to 256-bit), or Shor-breakable but not within the chosen scenario (the date is unknown, not safe). |
| **safe** | No known efficient quantum attack (AES-256, SHA-256, ML-KEM, ML-DSA, …). |
| **unknown** | Not in the catalog: review it by hand. |

### Break years

A break year is the first year IBM's roadmap provides **both** the logical qubits **and** the operations a published
attack needs. Toffoli gates are compared directly with IBM's gate counts, which favours the attacker, so dates
lean early: the cautious direction for a defender. After 2033 the *trend* scenario is an explicit extrapolation.

### The CBOM file

The CBOM is [CycloneDX 1.6](https://cyclonedx.org/docs/1.6/json/) JSON. Each algorithm is one
`cryptographic-asset` component with its NIST quantum security level, every place it was found
(`evidence.occurrences`), and three properties: `qday:quantum-status` (`shor`, `grover`, `classical` or `safe`),
`qday:recommended-replacement` and `qday:purposes`.

### The hardware-calibrated forecast

We measured the effective error per two-qubit gate on IBM's machines from the Grover runs (about 3 × 10⁻³ on the
best qubits; readout included, so an upper bound) and carried it through a surface-code model to the physical
qubits RSA-2048 would need. It is an order-of-magnitude estimate, reported against the published one: see the
README section *Hardware-calibrated Q-Day* and [RESULTS.md](RESULTS.md).

---

## Configuration

| Variable | Used for |
| :--- | :--- |
| `IBM_QUANTUM_TOKEN` | Your IBM Quantum API key (only for submitting hardware jobs) |
| `IBM_QUANTUM_INSTANCE` | Optional instance CRN; leave empty to auto-select |
| `QDAY_ENV_FILE` | Path to a `.env` file holding the two variables above |

Environment variables win over files. Otherwise the app reads `$QDAY_ENV_FILE`, then `.env` in the project folder.
`.env` is git-ignored and excluded from the Docker image, and the key is never printed or logged. Start from the
template:

```bash
cp .env.example .env    # then add your key
```

---

## Running on IBM quantum hardware

Optional: the saved results already cover this. With a key in `.env`:

```bash
# first run: Shor and Grover on one machine
python scripts/run_hardware.py submit --backend ibm_least_busy
python scripts/run_hardware.py fetch

# 17-circuit validation suite, one job per machine
python scripts/hardware_suite.py submit --backend ibm_kingston
python scripts/hardware_suite.py fetch  --backend ibm_kingston
python scripts/hardware_suite.py report

# strict suite with pre-registered rules; try it on the noise model first
python scripts/hardware_strict.py simulate
python scripts/hardware_strict.py submit --backend ibm_kingston --repeat
python scripts/hardware_strict.py fetch  --backend ibm_kingston
python scripts/hardware_strict.py report

# rebuild docs/RESULTS.md and results/noise_calibration.json from all saved runs
python scripts/summarize_results.py
```

Each suite job uses roughly 20–25 seconds of QPU time; all our runs together used 163 seconds.

---

## Deployment

### Docker

```bash
docker build -t qday .
docker run -d --restart unless-stopped -p 8501:8501 qday
```

The image runs `serve.py` as a non-root user with a health check on `/app/_stcore/health`.

### Your own server

```bash
python serve.py --host 0.0.0.0 --port 8501
```

Behind nginx, pass websockets through (the dashboard's live updates use `/app/_stcore/stream`):

```nginx
server {
    server_name qday.example.com;
    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

Add HTTPS with `certbot --nginx`. With Caddy, `reverse_proxy 127.0.0.1:8501` handles websockets by itself.

Serverless hosts such as Vercel can serve the static landing page (`landing/index.html`) but not the dashboard,
which needs a long-running process and websockets. If you host them separately, point the landing page's
**Launch the app** links at the dashboard's full address.

---

## Troubleshooting

| Problem | Fix |
| :--- | :--- |
| "the dashboard did not become healthy in time" | Something else is using port 8502; start with `--app-port 8600`. |
| Port 8501 already in use | `python serve.py --port 8080` |
| A website scan reports no key-exchange group | Install OpenSSL 3.x and make sure `openssl` is on the `PATH`. |
| "Could not scan … folder not found" | The path must exist on the machine running the app, not your browser's machine. |
| Hardware scripts ask for an account | Add `IBM_QUANTUM_TOKEN` to `.env`, or set `QDAY_ENV_FILE`. |
| `docs/RESULTS.md` is out of date (test or CI fails) | Run `python scripts/summarize_results.py` and commit the result. |
| The landing page looks old after an edit | Run `python landing/build.py`, then hard-refresh the browser. |
