---
hide:
  - navigation
---

# Q-Day Time Machine

<div class="qday-hero" markdown>

<p class="tagline"><strong>Find the cryptography a quantum computer will break, see <em>when</em> it breaks, prove it on
real IBM quantum hardware, and get the post-quantum fix.</strong></p>

[Try it live](https://qdaytimemachine.vercel.app){ .md-button .md-button--primary }
[Get started](USER_GUIDE.md#install){ .md-button }
[Watch the demo](https://youtu.be/nhXP6QLFjoU){ .md-button }
[View on GitHub](https://github.com/vtu-qiskit-fall-fest-2026/vtu-hc-straw-hat-pirates){ .md-button }

</div>

```bash
pip install qday-time-machine
qday scan --path ./src --fail-on critical
```

<div class="qday-stats" markdown>
<div><b>45 / 45</b><span>validation tests passed on three IBM quantum computers</span></div>
<div><b>~3×10⁻³</b><span>error per two-qubit gate we measured on the best qubits</span></div>
<div><b>~4 M</b><span>physical qubits RSA-2048 would need at that error rate</span></div>
<div><b>1,002</b><span>automated tests, 96% line coverage</span></div>
</div>

## The problem

Shor's algorithm will break the RSA and elliptic-curve cryptography behind today's logins, payments and
signatures. Attackers can record encrypted traffic now and decrypt it later ("harvest now, decrypt later"), and
NIST's draft transition plan retires RSA and elliptic-curve cryptography by 2035. Teams know the threat exists, but
can't say **which systems break first, in what year, or whether the data they send today is already at risk**.

## What it does

| Step | What you get |
| :--- | :--- |
| **1. Scan** | Every use of cryptography in a website's TLS setup or a code base (eight languages), including detection of the hybrid post-quantum group `X25519MLKEM768`. |
| **2. Inventory** | A CycloneDX 1.6 cryptography bill of materials (CBOM). |
| **3. Time Machine** | A break year for each algorithm: published attack costs (logical qubits **and** gates) against IBM's quantum roadmap. |
| **4. Risk** | Mosca's inequality and a harvest-now window: what to fix first, and which recorded data is already exposed. |
| **5. Prove it** | Shor's and Grover's algorithms in Qiskit, run on `ibm_fez`, `ibm_kingston` and `ibm_marrakesh` with pre-registered pass rules, and stepped through gate by gate with quantum-debugger. |
| **6. Migrate** | A working hybrid X25519 + ML-KEM-768 handshake and ML-DSA-65 signatures beside RSA and ECDSA. |

## Screenshots

![The landing page: each ring is one year on IBM's roadmap, green while safe and pink once breakable](screenshots/landing.jpg)

<div class="grid" markdown>

![Scan results grouped into fix now, plan migration and already safe](screenshots/scan.jpg)

![The Time Machine: quantum power against what each attack needs](screenshots/time-machine.jpg)

![Shor's algorithm factoring 15 on ibm_marrakesh](screenshots/hardware-proof.jpg)

![Stepping through Grover's attack with quantum-debugger](screenshots/step-through.jpg)

</div>

## Our finding

We measured the effective error per two-qubit gate on three IBM quantum computers from every Grover run. The best
qubits on all three agree at about **3 × 10⁻³**, three times the error rate the published RSA-2048 estimate assumes.
Carried through a surface-code model, breaking RSA-2048 on today's qubits would take roughly **4 million physical
qubits rather than under 1 million**. On one machine the compiler's default qubits measured 1.6 × 10⁻²: **above the
error-correction threshold**, where no amount of hardware helps. See [Methods](methods.md) and
[Hardware results](RESULTS.md).

## Where to go next

- **[User guide](USER_GUIDE.md):** install, run the dashboard, every CLI option, configuration and deployment.
- **[Methods](methods.md):** how break years, risk levels, the hardware tests and the error-rate measurement work.
- **[Hardware results](RESULTS.md):** every IBM job ID, with 95% intervals and baselines.
- **[Architecture](ARCHITECTURE.md):** how the code is organised and why.
- **[API reference](api.md):** use `qday` from Python.

Built by **Team Straw Hat Pirates** (Raunak Kumar Gupta, Krish Jain) for the VTU-QFF Hackathon, Qiskit Fall Fest 2026.
