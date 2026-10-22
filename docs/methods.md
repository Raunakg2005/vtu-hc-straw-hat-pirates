# Methods

How the app turns a list of algorithms into break years, risk levels and evidence. Every number comes from
a cited source or from our own saved hardware runs.

## Break years

### What an attack needs

| Target | Logical qubits | Toffoli gates | Source |
| :--- | ---: | ---: | :--- |
| RSA-2048 | 1,399 | 6.5 × 10⁹ | Gidney 2025, [arXiv:2505.15917](https://arxiv.org/abs/2505.15917) (under 1 million noisy qubits, under a week) |
| RSA-*n* | 3n + 0.002 n lg n | 0.3 n³ + 0.0005 n³ lg n | Gidney & Ekerå 2019, [arXiv:1905.09749](https://arxiv.org/abs/1905.09749) |
| Elliptic curve over an *n*-bit field | 9n + 2⌈lg n⌉ + 10 | 448 n³ lg n + 4090 n³ | Roetteler et al. 2017, [arXiv:1706.06752](https://arxiv.org/abs/1706.06752) (upper bound; P-256: 2,330 qubits, ~1.3 × 10¹¹ gates) |

### What a machine can do, year by year

IBM's public fault-tolerant roadmap ([ibm.com/roadmaps/quantum](https://www.ibm.com/roadmaps/quantum/)):

| Machine | Year | Logical qubits | Operations |
| :--- | :--- | ---: | ---: |
| Starling | 2029 | 200 | 10⁸ |
| Blue Jay | 2033+ | 2,000 | 10⁹ |

Nothing is published after 2033, so there are two scenarios:

- **`roadmap`:** the machine stays at Blue Jay.
- **`trend`** (default): Starling → Blue Jay growth (×10 in 4 years, about ×1.78 a year) continues. This is a
  hypothetical extrapolation and is labelled as one everywhere.

### The rule

An algorithm's **break year** is the first year whose machine has **both** enough logical qubits **and** enough
operations. A year with enough qubits but too few operations is reported as *qubits ready*: one step away.
Checking only qubits would put RSA-2048 at 2033; checking both moves it to 2037 under `trend`, and to "not on the
published roadmap" under `roadmap`.

!!! note "Why the dates lean early"
    A Toffoli gate is compared one-to-one with IBM's "operations", although a Toffoli costs several logical
    operations. That favours the attacker, so the dates are cautious: the safe direction for a defender.

## Risk levels

Risk follows **Mosca's inequality**. With *x* the years data must stay secret (shelf life), *y* the years
migration takes, and *z* the years until the algorithm breaks:

- For **confidentiality** (key exchange, public-key encryption): if *x + y > z*, data protected today will be
  readable before it stops being sensitive, so it is **critical**.
- For **signatures**: if *y > z*, signatures could be forged before migration finishes, so it is **critical**.

| Level | When |
| :--- | :--- |
| critical | Mosca's inequality fails, or the algorithm is already broken classically (MD5, SHA-1, …) |
| high | Breakable within the scenario but there is time to migrate, or no published estimate for that size |
| medium | Grover halves its strength (AES-128 → move to 256-bit), or not breakable within the scenario (date unknown, not safe) |
| safe | No known efficient quantum attack |

The **harvest-now window** lists the years of recorded traffic that become readable while still sensitive.

## Hardware validation

### The circuits

- **Shor (order finding):** quantum phase estimation over `f(x) = aˣ mod N`. The controlled multipliers
  `x → a^(2^j)·x mod N` are synthesised for any constant, so the circuit never encodes the answer. For N = 15
  every unit is ±2ᵏ, so a multiplier is a bit rotation plus NOT: 171–177 two-qubit gates after compiling.
- **Grover (key search):** a toy cipher `E_k(p) = S(p ⊕ k)` with a nonlinear S-box. The oracle runs the cipher on
  every key at once and flips the phase of keys matching a known pair; the diffuser reflects about the mean.
  Success follows `sin²((2i + 1)θ)`, peaking at 2 iterations for 3-bit keys.

### Validation suite

17 circuits × 4,000 shots on each of three machines: Shor for every base of 15, Grover for all 8 keys, and two
negative controls that must fail (a = 14, which can never factor 15; Grover with 0 iterations, which must look
random). A test passes only if its whole **95% Wilson interval** is above the random / noise baseline; we also
report an exact one-sided binomial p-value and the total variation distance to the ideal distribution.

### Strict suite (`strict-v1`)

The pass rules were fixed in code **before** the runs, and Grover secrets were drawn blind at submit time:

| Rule | Requirement |
| :--- | :--- |
| C1 Signal | binomial p < 0.05 / *m* (Bonferroni over all tests) **and** the whole 95% interval above the noise baseline |
| C2 Dominance | Shor: the most frequent outcomes are exactly the ideal ones. Grover: the secret is the top key, at least 2× the runner-up |
| C3 Fidelity | Hellinger fidelity to ideal ≥ that of a 50% ideal / 50% noise mixture (a bar from theory, not data) |
| C4 Fingerprint | Grover sweep 0–4 iterations: Pearson r ≥ 0.9 with theory, and a significant drop past the optimum |
| C5 Layout | the same circuits on other physical qubits also pass C1–C3 |
| C6 Repeatability | an identical second job agrees (chi-square p > 0.001 for every circuit) |

### Independent check

Every Shor and Grover circuit is also simulated by [quantum-debugger](https://pypi.org/project/quantum-debugger/),
our own state-vector engine, and compared with Qiskit. Conversion between the two is exact or refused: a gate is
never silently dropped. Largest difference on any circuit: 3 × 10⁻¹³.

## Measuring today's error rate

The published RSA-2048 estimate assumes an error of 10⁻³ per operation. We measure ours from the Grover runs.

1. **Effective fidelity.** Each run's measured distribution *P* is modelled as the ideal distribution *I* mixed
   with uniform noise *U* (a global depolarising model): `P = F·I + (1 − F)·U`. The least-squares estimate is
   `F = ⟨P − U, I − U⟩ / ‖I − U‖²`, with its exact multinomial standard error.
2. **Error per gate.** For a circuit with *g* two-qubit gates, `ε = 1 − F^(1/g)`. Readout and single-qubit
   errors are folded in, so ε is an **upper bound** on the pure two-qubit error.
3. **Grouping.** Runs are grouped by the physical qubits they used, and each set is summarised by its median, so
   one noisy run cannot stand for a whole chip.

Grover is the probe because it measures every qubit it uses. Shor N = 15 is not: most of its gates act on the work
register, whose errors barely reach the measured counting qubits, so its success does not track gate count (it
keeps ~70% through 177 gates while Grover drops to 38–68% through 143).

### From error rate to RSA-2048

- **Without error correction**, a circuit of *G* two-qubit gates succeeds with probability ≈ `(1 − ε)^G`.
  RSA-2048 is ~3.9 × 10¹⁰ CNOT-equivalent gates (6.5 × 10⁹ Toffolis × 6), so it needs ε ≤ ln 2 / G ≈ 1.8 × 10⁻¹¹.
- **With the surface code** ([Fowler et al. 2012](https://arxiv.org/abs/1208.0928)), the logical error per qubit
  per round is `p_L = 0.1 (ε / 0.01)^((d + 1)/2)` and a logical qubit costs ~2d² physical qubits. The distance *d*
  is the smallest that keeps all 1,399 logical qubits alive for a week of 1 µs rounds. Above ε ≈ 10⁻² no distance
  helps.
- The model is simpler than the paper's (which uses yoked surface codes and magic-state cultivation), so we use it
  only for the **ratio** between our ε and the paper's 10⁻³, and scale the paper's "under one million qubits".

| Error per two-qubit gate | Distance | Physical qubits for RSA-2048 |
| :--- | ---: | ---: |
| 1.0 × 10⁻³ (published assumption) | 27 | under 1 million |
| 3.1 × 10⁻³ (our best measured) | 55 | ~4.1 million |
| 4.2 × 10⁻³ (our median) | 75 | ~7.7 million |
| 1.6 × 10⁻² (`ibm_marrakesh` default qubits) | — | impossible: above threshold |

Treat these as order-of-magnitude figures. The full per-run table is in [Hardware results](RESULTS.md).

## Limitations

- The attacks break toy instances (N = 15 and 21; 3–4-bit keys), not real keys.
- Break years rest on published estimates and IBM's stated roadmap; after 2033 the `trend` scenario is an
  extrapolation, and newer elliptic-curve estimates are lower than the 2017 bound used here.
- The error-rate measurement is a simple depolarising fit on 3-qubit circuits over one day.
- The code scanner is pattern-based: findings are leads to review, not proof of reachability.
