"""Draw the attack circuits for the README: docs/circuits/*.png, straight from the code that runs on hardware."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

from qiskit import QuantumCircuit, QuantumRegister  # noqa: E402

from qday.quantum import grover, shor  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "docs" / "circuits"
OUT.mkdir(parents=True, exist_ok=True)

# Qiskit Fall Fest palette, as in the dashboard
STYLE = {
    "name": "clifford",
    "fontsize": 15, "subfontsize": 11,
    "backgroundcolor": "#FFFFFF", "linecolor": "#392045", "textcolor": "#392045", "gatetextcolor": "#392045",
    "displaycolor": {
        "h": ["#ECE6FD", "#392045"], "x": ["#FBD3E4", "#392045"], "swap": ["#FBD3E4", "#392045"],
        "measure": ["#FBEAB8", "#392045"], "unitary": ["#FBD3E4", "#392045"], "default": ["#ECE6FD", "#392045"],
        "target": ["#FFFFFF", "#392045"],
        "qft_dg": ["#392045", "#FFFFFF"], "oracle": ["#E85291", "#FFFFFF"], "diffuser": ["#7A5CC8", "#FFFFFF"],
        "cx7 mod 15": ["#F4A8C8", "#392045"], "cx4 mod 15": ["#F4A8C8", "#392045"], "mcx": ["#392045", "#FFFFFF"],
    },
}


PAD = "  "  # room for the qubit numbers Qiskit draws inside wide boxes
LABELS = {"qft_dg": "QFT†", "oracle": "Oracle", "diffuser": "Diffuser"}


def labelled(circuit):
    """A copy with readable block labels (the circuit that runs is unchanged)."""
    out = circuit.copy()
    for i, inst in enumerate(out.data):
        op = inst.operation
        label = LABELS.get(op.name) or (op.label if op.name == "unitary" else None)  # the S-box keeps its own label
        if label:
            op = op.to_mutable()
            op.label = PAD + label + PAD
            out.data[i] = inst.replace(operation=op)
    return out


def on_key_register(circuit):
    reg = QuantumRegister(circuit.num_qubits, "key")
    return QuantumCircuit(reg).compose(circuit, qubits=reg)


def save(circuit, name, **kw):
    fig = labelled(circuit).draw("mpl", style=STYLE, fold=-1, **kw)
    fig.savefig(OUT / f"{name}.png", dpi=170, bbox_inches="tight", facecolor="white")
    print(OUT / f"{name}.png")


# Shor, N = 15, a = 7, 3 counting qubits: the circuit run on ibm_fez, ibm_kingston and ibm_marrakesh
save(shor.order_finding_circuit(7, 15, 3), "shor_n15_a7")
# Grover, 3-bit key, 2 iterations: the oracle and diffuser as blocks, then one oracle opened up
key, plaintext = 6, 5
g = grover.grover_key_search_circuit(plaintext, grover.toy_encrypt(plaintext, key, 3), iterations=2, n_bits=3)
save(g, "grover_3bit_2iter")
save(on_key_register(grover.oracle(plaintext, grover.toy_encrypt(plaintext, key, 3), 3)), "grover_oracle")
save(on_key_register(grover.diffuser(3)), "grover_diffuser")
